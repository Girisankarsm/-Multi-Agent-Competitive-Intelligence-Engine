"""Compare router — Multi-competitor side-by-side comparison."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db
from models import Competitor, Signal, CrawledPage
from agents.analyst import score_competitor_dimensions

router = APIRouter(prefix="/api/compare", tags=["compare"])


def _compute_intensity_score(signals: list[dict]) -> int:
    """
    Compute competitive intensity score (0-100) from signals.
    critical/existential × 3, moderate/high × 2, minor × 1, normalized to 100.
    """
    raw = 0
    for s in signals:
        sev = s.get("severity", "minor")
        if sev == "existential":
            raw += 3
        elif sev == "moderate":
            raw += 2
        else:
            raw += 1
    # Normalize: assume ~20 signals at max severity (60) = 100
    score = min(100, int((raw / 60) * 100)) if raw > 0 else 0
    return score


@router.get("")
async def compare_competitors(
    competitor_ids: str = Query(..., description="Comma-separated competitor IDs, e.g. 1,2,3"),
    db: AsyncSession = Depends(get_db),
):
    """Compare multiple competitors side-by-side."""
    # Parse IDs
    try:
        ids = [int(x.strip()) for x in competitor_ids.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid competitor_ids format. Use comma-separated integers.")

    if not ids:
        raise HTTPException(status_code=400, detail="No competitor IDs provided")
    if len(ids) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 competitors for comparison")

    competitors_data = []

    for comp_id in ids:
        # Fetch competitor
        comp_result = await db.execute(select(Competitor).where(Competitor.id == comp_id))
        competitor = comp_result.scalar_one_or_none()
        if not competitor:
            continue  # Skip missing competitors silently

        # Fetch signals
        sig_result = await db.execute(
            select(Signal).where(Signal.competitor_id == comp_id)
        )
        signals_orm = sig_result.scalars().all()
        signals_list = [
            {
                "title": s.title,
                "signal_type": s.signal_type,
                "severity": s.severity,
                "category": s.category,
                "description": s.description,
                "relevance": s.relevance,
                "confidence": s.confidence,
            }
            for s in signals_orm
        ]

        # Compute intensity
        intensity_score = _compute_intensity_score(signals_list)

        # Score on 6 axes via Gemini
        radar = await score_competitor_dimensions(signals_list)

        # Fetch crawled pages to extract feature gaps
        pages_result = await db.execute(
            select(CrawledPage)
            .where(CrawledPage.competitor_id == comp_id)
            .order_by(CrawledPage.strategic_score.desc())
        )
        pages = pages_result.scalars().all()

        # Build feature evidence from page types
        feature_gaps = {}
        page_types = {p.page_type.lower() for p in pages if p.page_type}
        page_content_combined = " ".join([p.content_md or "" for p in pages[:5]]).lower()

        # Check common features
        common_features = [
            "API", "SSO", "Analytics", "Integrations", "Mobile App",
            "Custom Reports", "Webhooks", "White Label", "Multi-tenant",
            "AI/ML Features", "Collaboration", "Audit Logs",
        ]
        for feature in common_features:
            feature_lower = feature.lower().replace("/", " ")
            has_it = (
                feature_lower in page_content_combined
                or any(feature_lower in pt for pt in page_types)
            )
            feature_gaps[feature] = has_it

        competitors_data.append({
            "id": competitor.id,
            "name": competitor.name or competitor.url,
            "url": competitor.url,
            "intensity_score": intensity_score,
            "radar": radar,
            "feature_gaps": feature_gaps,
            "signal_count": len(signals_list),
            "threats": len([s for s in signals_list if s["signal_type"] == "threat"]),
            "opportunities": len([s for s in signals_list if s["signal_type"] == "opportunity"]),
        })

    if not competitors_data:
        raise HTTPException(status_code=404, detail="No valid competitors found for the given IDs")

    return {"competitors": competitors_data}
