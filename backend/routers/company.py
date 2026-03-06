"""Company router — DNA extraction and profile management."""

import asyncio
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db
from models import Company
from agents.dna_extractor import extract_company_dna
from services.scraper import fetch_page, html_to_markdown, extract_title, extract_links

router = APIRouter(prefix="/api/company", tags=["company"])


class CompanyRequest(BaseModel):
    url: str


class CompanyResponse(BaseModel):
    id: int
    name: str
    url: str
    summary: str
    features: list
    icp: dict
    positioning: dict
    pricing: dict

    class Config:
        from_attributes = True


@router.post("/analyze", response_model=CompanyResponse)
async def analyze_company(req: CompanyRequest, db: AsyncSession = Depends(get_db)):
    """Scrape a company's website and extract DNA profile."""
    url = req.url.strip()
    if not url.startswith("http"):
        url = f"https://{url}"

    # Scrape key pages
    pages_to_scrape = []
    try:
        html, status = await fetch_page(url)
        if status != 200:
            raise HTTPException(status_code=400, detail=f"Could not fetch {url} (status {status})")

        title = extract_title(html)
        content = html_to_markdown(html)
        pages_to_scrape.append({"url": url, "title": title, "content": content})

        # Find and scrape key subpages (pricing, features, about) — concurrently
        links = extract_links(html, url)
        key_keywords = ["pricing", "features", "about", "product", "plans", "enterprise", "solutions"]
        key_links = [l for l in links if any(kw in l.lower() for kw in key_keywords)][:3]

        async def _fetch_subpage(link):
            try:
                sub_html, sub_status = await asyncio.wait_for(fetch_page(link), timeout=8.0)
                if sub_status == 200:
                    return {
                        "url": link,
                        "title": extract_title(sub_html),
                        "content": html_to_markdown(sub_html),
                    }
            except Exception:
                pass
            return None

        if key_links:
            results = await asyncio.gather(*[_fetch_subpage(l) for l in key_links])
            for result in results:
                if result:
                    pages_to_scrape.append(result)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to scrape: {str(e)}")

    # Run DNA extraction
    try:
        profile = await extract_company_dna(url, pages_to_scrape)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI analysis failed: {str(e)}")

    # Store in database
    company = Company(
        name=profile.get("name", "Unknown"),
        url=url,
        summary=profile.get("summary", ""),
        features=profile.get("features", []),
        icp=profile.get("icp", {}),
        positioning=profile.get("positioning", {}),
        pricing=profile.get("pricing", {}),
        raw_profile=str(profile),
    )
    db.add(company)
    await db.commit()
    await db.refresh(company)

    return company


@router.get("/{company_id}", response_model=CompanyResponse)
async def get_company(company_id: int, db: AsyncSession = Depends(get_db)):
    """Get a stored company profile."""
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


@router.get("/", response_model=list[CompanyResponse])
async def list_companies(db: AsyncSession = Depends(get_db)):
    """List all analyzed companies."""
    result = await db.execute(select(Company).order_by(Company.created_at.desc()))
    return result.scalars().all()
