"""Analysis router — Run analyst engine and retrieve signals."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db
from models import Competitor, CrawledPage, Signal, Company
from agents.analyst import run_analyst

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


class SignalResponse(BaseModel):
    id: int
    signal_type: str
    category: str
    title: str
    description: str
    severity: str
    relevance: float
    confidence: float
    evidence: list

    class Config:
        from_attributes = True


class AnalysisResult(BaseModel):
    competitor_name: str
    signals: list[SignalResponse]
    feature_comparison: dict
    pricing_comparison: dict
    market_insights: dict


@router.post("/run/{competitor_id}")
async def run_analysis(competitor_id: int, db: AsyncSession = Depends(get_db)):
    """Run the full analyst engine on a competitor's crawled data."""
    # Get competitor
    result = await db.execute(select(Competitor).where(Competitor.id == competitor_id))
    competitor = result.scalar_one_or_none()
    if not competitor:
        raise HTTPException(status_code=404, detail="Competitor not found")
    if competitor.status not in ("crawled", "done"):
        raise HTTPException(status_code=400, detail="Competitor must be fully crawled first")

    # Get company profile
    result = await db.execute(select(Company).where(Company.id == competitor.company_id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    # Get crawled pages
    result = await db.execute(
        select(CrawledPage)
        .where(CrawledPage.competitor_id == competitor_id)
        .order_by(CrawledPage.strategic_score.desc())
    )
    pages = result.scalars().all()

    if not pages:
        raise HTTPException(status_code=400, detail="No crawled pages found")

    # Build inputs
    company_profile = {
        "name": company.name,
        "summary": company.summary,
        "features": company.features,
        "icp": company.icp,
        "positioning": company.positioning,
        "pricing": company.pricing,
    }

    page_dicts = [
        {
            "url": p.url,
            "title": p.title,
            "content_md": p.content_md,
            "page_type": p.page_type,
            "strategic_score": p.strategic_score,
        }
        for p in pages
    ]

    # Run analysis
    try:
        analysis = await run_analyst(company_profile, page_dicts)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

    # Update competitor name if detected
    comp_name = analysis.get("competitor_name", "")
    if comp_name and not competitor.name:
        competitor.name = comp_name

    # Store signals mapped from threats and opportunities
    signals_data = analysis.get("signals", {})
    threats = signals_data.get("threats", [])
    opportunities = signals_data.get("opportunities", [])
    
    stored_signals = []
    
    # Process threats
    for t in threats:
        sev_score = t.get("severity_score", 50)
        sev_str = "existential" if sev_score >= 80 else ("minor" if sev_score <= 30 else "moderate")
        signal = Signal(
            signal_type="threat",
            category="",
            title=t.get("title", ""),
            description=t.get("description", ""),
            severity=sev_str,
            relevance=sev_score,
            confidence=t.get("confidence_score", 50),
            evidence=t.get("evidence", []),
            competitor_id=competitor_id,
        )
        db.add(signal)
        stored_signals.append(signal)

    # Process opportunities
    for o in opportunities:
        signal = Signal(
            signal_type="opportunity",
            category=o.get("opportunity_type", ""),
            title=o.get("title", ""),
            description=o.get("description", ""),
            severity="moderate",
            relevance=o.get("confidence_score", 50), # opportunities use confidence as relevance proxy
            confidence=o.get("confidence_score", 50),
            evidence=o.get("evidence", []),
            competitor_id=competitor_id,
        )
        db.add(signal)
        stored_signals.append(signal)

    competitor.status = "analyzed"
    await db.commit()

    # Pass the full raw analysis straight back to the frontend so it can render the new UI beautifully,
    # but also add the stored DB signals for components that might need the IDs.
    analysis["stored_signals"] = [
        {"id": s.id, "title": s.title, "type": s.signal_type} for s in stored_signals
    ]
    
    return analysis


@router.get("/{competitor_id}/signals", response_model=list[SignalResponse])
async def get_signals(competitor_id: int, db: AsyncSession = Depends(get_db)):
    """Get all signals for a competitor."""
    result = await db.execute(
        select(Signal)
        .where(Signal.competitor_id == competitor_id)
        .order_by(Signal.relevance.desc())
    )
    return result.scalars().all()
