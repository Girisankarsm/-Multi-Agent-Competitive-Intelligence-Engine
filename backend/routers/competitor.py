"""Competitor router — Add competitors, trigger scout, stream progress."""

import asyncio
import json
import uuid
import traceback
from typing import Dict, Optional
from urllib.parse import urlparse
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sse_starlette.sse import EventSourceResponse

from database import get_db
from models import Competitor, CrawledPage, Company
from agents.scout import run_scout
from services.event_bus import event_bus
from config import settings

router = APIRouter(prefix="/api/competitor", tags=["competitor"])


class CompetitorRequest(BaseModel):
    url: str
    company_id: int


class CompetitorResponse(BaseModel):
    id: int
    name: str
    url: str
    status: str
    page_count: int
    company_id: int
    job_id: Optional[str] = None

    class Config:
        from_attributes = True


_running_jobs: Dict[int, str] = {}


@router.post("/add", response_model=CompetitorResponse)
async def add_competitor(req: CompetitorRequest, db: AsyncSession = Depends(get_db)):
    """Add a competitor and start crawling."""
    result = await db.execute(select(Company).where(Company.id == req.company_id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    url = req.url.strip()
    if not url.startswith("http"):
        url = "https://" + url

    competitor = Competitor(
        url=url,
        name="",
        status="crawling",
        company_id=req.company_id,
    )
    db.add(competitor)
    await db.commit()
    await db.refresh(competitor)

    job_id = str(uuid.uuid4())
    comp_id = competitor.id
    _running_jobs[comp_id] = job_id

    async def _background_crawl(comp_name_guess=""):
        print("[CRAWL] Starting background crawl for competitor %d, url=%s, job=%s" % (comp_id, url, job_id))
        from database import async_session
        from services.scraper import fetch_reddit_data, fetch_news_data, fetch_jobs_data
        
        async with async_session() as session:
            try:
                # To search Reddit/News/Jobs effectively we need a name, we'll try to guess it from the URL
                # e.g., https://www.stripe.com -> stripe
                name_query = urlparse(url).netloc.replace("www.", "").split(".")[0]
                
                await event_bus.publish(job_id, "log", {"message": f"Fetching multi-source intelligence for '{name_query}'..."})

                # Run web scout and external fetchers concurrently
                scout_task = asyncio.create_task(run_scout(job_id, url, max_pages=settings.MAX_CRAWL_PAGES))
                reddit_task = asyncio.create_task(fetch_reddit_data(name_query))
                news_task = asyncio.create_task(fetch_news_data(name_query))
                jobs_task = asyncio.create_task(fetch_jobs_data(name_query))

                pages, reddit_md, news_md, jobs_md = await asyncio.gather(
                    scout_task, reddit_task, news_task, jobs_task, return_exceptions=True
                )

                # Handle potential exceptions in gather
                if isinstance(pages, Exception):
                    raise pages
                
                print("[CRAWL] Scout returned %d pages for competitor %d" % (len(pages), comp_id))

                comp_name = ""
                # Save normal web pages
                for page_data in pages:
                    page = CrawledPage(
                        url=page_data["url"],
                        title=page_data["title"],
                        content_md=page_data["content_md"],
                        page_type=page_data["page_type"],
                        strategic_score=page_data["strategic_score"],
                        competitor_id=comp_id,
                    )
                    session.add(page)
                    if not comp_name and page_data["title"]:
                        # A better guess based on the actual homepage title
                        comp_name = page_data["title"].split("|")[0].split("-")[0].strip()

                # Save external data as high-priority pages so Analyst guarantees to see them
                if isinstance(reddit_md, str) and reddit_md:
                    session.add(CrawledPage(
                        url=f"reddit://search/{name_query}",
                        title=f"{name_query} Reddit Discussions",
                        content_md=reddit_md,
                        page_type="REDDIT_SOURCE",
                        strategic_score=95,
                        competitor_id=comp_id,
                    ))
                if isinstance(news_md, str) and news_md:
                    session.add(CrawledPage(
                        url=f"news://search/{name_query}",
                        title=f"{name_query} Recent News",
                        content_md=news_md,
                        page_type="NEWS_SOURCE",
                        strategic_score=95,
                        competitor_id=comp_id,
                    ))
                if isinstance(jobs_md, str) and jobs_md:
                    session.add(CrawledPage(
                        url=f"jobs://search/{name_query}",
                        title=f"{name_query} Open Jobs",
                        content_md=jobs_md,
                        page_type="JOB_SOURCE",
                        strategic_score=95,
                        competitor_id=comp_id,
                    ))

                result = await session.execute(
                    select(Competitor).where(Competitor.id == comp_id)
                )
                comp = result.scalar_one()
                comp.status = "crawled"
                comp.page_count = len(pages) + 3 # approx incl external
                if comp_name:
                    comp.name = comp_name

                await session.commit()
                print("[CRAWL] Crawl complete for competitor %d: %d pages, name=%s" % (comp_id, len(pages), comp_name))
                await event_bus.publish(job_id, "done", {
                    "message": "Crawl complete",
                    "total_pages": len(pages)
                })
            except Exception as e:
                print("[CRAWL] Crawl FAILED for competitor %d: %s" % (comp_id, str(e)))
                traceback.print_exc()
                await event_bus.publish(job_id, "error", {
                    "message": "Crawl failed: " + str(e)
                })
                await event_bus.publish(job_id, "done", {
                    "message": "Crawl failed",
                    "total_pages": 0
                })
                try:
                    result = await session.execute(
                        select(Competitor).where(Competitor.id == comp_id)
                    )
                    comp = result.scalar_one()
                    comp.status = "failed"
                    await session.commit()
                except Exception:
                    pass
            finally:
                _running_jobs.pop(comp_id, None)

    asyncio.create_task(_background_crawl())

    return CompetitorResponse(
        id=competitor.id,
        name=competitor.name or "",
        url=competitor.url,
        status=competitor.status,
        page_count=competitor.page_count or 0,
        company_id=competitor.company_id,
        job_id=job_id,
    )


@router.get("/{competitor_id}/stream")
async def stream_competitor(competitor_id: int):
    """SSE endpoint for live crawl progress."""
    job_id = _running_jobs.get(competitor_id)
    if not job_id:
        done_payload = json.dumps({"event": "done", "data": {"message": "Crawl already completed", "total_pages": 0}})
        async def _completed_stream():
            yield {"data": done_payload}
        return EventSourceResponse(_completed_stream())

    return EventSourceResponse(event_bus.subscribe(job_id))


@router.get("/job/{job_id}/stream")
async def stream_job(job_id: str):
    """SSE endpoint using job_id directly (more reliable)."""
    return EventSourceResponse(event_bus.subscribe(job_id))


@router.get("/job/{job_id}/events")
async def get_job_events(job_id: str):
    """Polling fallback — get all buffered events for a job."""
    return event_bus.get_buffer(job_id)


@router.get("/{competitor_id}", response_model=CompetitorResponse)
async def get_competitor(competitor_id: int, db: AsyncSession = Depends(get_db)):
    """Get competitor details."""
    result = await db.execute(select(Competitor).where(Competitor.id == competitor_id))
    competitor = result.scalar_one_or_none()
    if not competitor:
        raise HTTPException(status_code=404, detail="Competitor not found")
    job_id = _running_jobs.get(competitor_id)
    return CompetitorResponse(
        id=competitor.id,
        name=competitor.name or "",
        url=competitor.url,
        status=competitor.status,
        page_count=competitor.page_count or 0,
        company_id=competitor.company_id,
        job_id=job_id,
    )


@router.get("/company/{company_id}")
async def list_competitors(company_id: int, db: AsyncSession = Depends(get_db)):
    """List all competitors for a company."""
    result = await db.execute(
        select(Competitor)
        .where(Competitor.company_id == company_id)
        .order_by(Competitor.created_at.desc())
    )
    competitors = result.scalars().all()
    return [
        CompetitorResponse(
            id=c.id,
            name=c.name or "",
            url=c.url,
            status=c.status,
            page_count=c.page_count or 0,
            company_id=c.company_id,
            job_id=_running_jobs.get(c.id),
        )
        for c in competitors
    ]
