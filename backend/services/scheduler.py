"""Scheduler Service — Runs periodic monitoring jobs using APScheduler."""

import datetime
import logging
import traceback
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select

from database import async_session
from models import MonitorJob, Competitor, Company, CrawledPage, Signal, ChangeAlert
from agents.scout import run_scout
from agents.analyst import run_analyst
from config import settings

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


def _compute_next_run(schedule: str, from_time: datetime.datetime = None) -> datetime.datetime:
    """Compute the next run time based on schedule type."""
    base = from_time or datetime.datetime.utcnow()
    if schedule == "daily":
        return base + datetime.timedelta(days=1)
    else:  # weekly
        return base + datetime.timedelta(weeks=1)


def _diff_signals(old_signals: list[dict], new_signals: list[dict]) -> dict:
    """
    Compare old vs new signals by title.
    Returns: {new_signals, disappeared_signals, severity_changes, summary}
    """
    old_by_title = {s["title"]: s for s in old_signals}
    new_by_title = {s["title"]: s for s in new_signals}

    old_titles = set(old_by_title.keys())
    new_titles = set(new_by_title.keys())

    # New signals (appeared)
    appeared = []
    for title in new_titles - old_titles:
        s = new_by_title[title]
        appeared.append({
            "title": title,
            "signal_type": s.get("signal_type", ""),
            "severity": s.get("severity", ""),
        })

    # Disappeared signals
    disappeared = []
    for title in old_titles - new_titles:
        s = old_by_title[title]
        disappeared.append({
            "title": title,
            "signal_type": s.get("signal_type", ""),
            "severity": s.get("severity", ""),
        })

    # Severity changes (signals present in both but severity changed)
    severity_changes = []
    for title in old_titles & new_titles:
        old_sev = old_by_title[title].get("severity", "")
        new_sev = new_by_title[title].get("severity", "")
        if old_sev != new_sev:
            severity_changes.append({
                "title": title,
                "old_severity": old_sev,
                "new_severity": new_sev,
            })

    # Build summary
    parts = []
    if appeared:
        parts.append(f"{len(appeared)} new signal(s) detected")
    if disappeared:
        parts.append(f"{len(disappeared)} signal(s) no longer detected")
    if severity_changes:
        parts.append(f"{len(severity_changes)} signal(s) changed severity")
    if not parts:
        parts.append("No significant changes detected")
    summary = ". ".join(parts) + "."

    return {
        "new_signals": appeared,
        "disappeared_signals": disappeared,
        "severity_changes": severity_changes,
        "summary": summary,
    }


async def _run_monitor_job(job: MonitorJob):
    """Execute a single monitoring job: re-crawl, re-analyze, diff, save alert."""
    async with async_session() as session:
        try:
            # Load competitor + company
            comp_result = await session.execute(
                select(Competitor).where(Competitor.id == job.competitor_id)
            )
            competitor = comp_result.scalar_one_or_none()
            if not competitor:
                logger.error(f"[MONITOR] Competitor {job.competitor_id} not found, skipping")
                return

            company_result = await session.execute(
                select(Company).where(Company.id == competitor.company_id)
            )
            company = company_result.scalar_one_or_none()
            if not company:
                logger.error(f"[MONITOR] Company {competitor.company_id} not found, skipping")
                return

            logger.info(f"[MONITOR] 🔄 Starting re-crawl for {competitor.name or competitor.url}")

            # 1. Re-run Scout
            job_id = f"monitor-{competitor.id}-{datetime.datetime.utcnow().strftime('%Y%m%d%H%M')}"
            pages = await run_scout(job_id, competitor.url, max_pages=settings.MAX_CRAWL_PAGES)
            logger.info(f"[MONITOR] Crawled {len(pages)} pages for {competitor.name}")

            if not pages:
                logger.warning(f"[MONITOR] No pages crawled for {competitor.name}, skipping analysis")
                return

            # 2. Build company profile
            company_profile = {
                "name": company.name,
                "summary": company.summary,
                "features": company.features,
                "icp": company.icp,
                "positioning": company.positioning,
                "pricing": company.pricing,
            }

            # 3. Re-run Analyst
            analysis = await run_analyst(company_profile, pages)
            new_signal_dicts = analysis.get("signals", [])
            logger.info(f"[MONITOR] Got {len(new_signal_dicts)} new signals for {competitor.name}")

            # 4. Load old signals for diffing
            old_result = await session.execute(
                select(Signal).where(Signal.competitor_id == competitor.id)
            )
            old_signals_orm = old_result.scalars().all()
            old_signal_dicts = [
                {
                    "title": s.title,
                    "signal_type": s.signal_type,
                    "severity": s.severity,
                    "category": s.category,
                    "relevance": s.relevance,
                    "confidence": s.confidence,
                }
                for s in old_signals_orm
            ]

            # 5. Diff
            diff = _diff_signals(old_signal_dicts, new_signal_dicts)

            # 6. Only create alert if something changed
            has_changes = (
                diff["new_signals"]
                or diff["disappeared_signals"]
                or diff["severity_changes"]
            )

            if has_changes:
                alert = ChangeAlert(
                    competitor_id=competitor.id,
                    detected_at=datetime.datetime.utcnow(),
                    new_signals=diff["new_signals"],
                    disappeared_signals=diff["disappeared_signals"],
                    severity_changes=diff["severity_changes"],
                    summary=diff["summary"],
                )
                session.add(alert)
                logger.info(f"[MONITOR] ✅ Change alert created: {diff['summary']}")
            else:
                logger.info(f"[MONITOR] No changes detected for {competitor.name}")

            # 7. Replace old signals with new ones
            for old_sig in old_signals_orm:
                await session.delete(old_sig)

            for sig_data in new_signal_dicts:
                new_sig = Signal(
                    signal_type=sig_data.get("signal_type", "opportunity"),
                    category=sig_data.get("category", ""),
                    title=sig_data.get("title", ""),
                    description=sig_data.get("description", ""),
                    severity=sig_data.get("severity", "moderate"),
                    relevance=sig_data.get("relevance", 50),
                    confidence=sig_data.get("confidence", 50),
                    evidence=sig_data.get("evidence", []),
                    competitor_id=competitor.id,
                )
                session.add(new_sig)

            # 8. Replace old crawled pages with new ones
            old_pages_result = await session.execute(
                select(CrawledPage).where(CrawledPage.competitor_id == competitor.id)
            )
            for old_page in old_pages_result.scalars().all():
                await session.delete(old_page)

            for page_data in pages:
                new_page = CrawledPage(
                    url=page_data["url"],
                    title=page_data["title"],
                    content_md=page_data["content_md"],
                    page_type=page_data["page_type"],
                    strategic_score=page_data["strategic_score"],
                    competitor_id=competitor.id,
                )
                session.add(new_page)

            # 9. Update monitor job timing
            monitor_result = await session.execute(
                select(MonitorJob).where(MonitorJob.id == job.id)
            )
            monitor_job = monitor_result.scalar_one()
            now = datetime.datetime.utcnow()
            monitor_job.last_run = now
            monitor_job.next_run = _compute_next_run(monitor_job.schedule, now)

            await session.commit()
            logger.info(f"[MONITOR] ✅ Monitor job complete for {competitor.name}, next run: {monitor_job.next_run}")

        except Exception as e:
            logger.error(f"[MONITOR] ❌ Monitor job failed for competitor {job.competitor_id}: {e}")
            traceback.print_exc()


async def check_due_jobs():
    """Check for due monitor jobs and run them."""
    async with async_session() as session:
        now = datetime.datetime.utcnow()
        result = await session.execute(
            select(MonitorJob).where(
                MonitorJob.is_active == 1,
                MonitorJob.next_run <= now,
            )
        )
        due_jobs = result.scalars().all()

        if due_jobs:
            logger.info(f"[MONITOR] Found {len(due_jobs)} due monitoring job(s)")

        for job in due_jobs:
            await _run_monitor_job(job)


def start_scheduler():
    """Start the APScheduler background scheduler."""
    scheduler.add_job(
        check_due_jobs,
        trigger=IntervalTrigger(minutes=5),
        id="monitor_check",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("[MONITOR] 📡 Scheduler started — checking for due jobs every 5 minutes")


def stop_scheduler():
    """Gracefully shut down the scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("[MONITOR] Scheduler stopped")
