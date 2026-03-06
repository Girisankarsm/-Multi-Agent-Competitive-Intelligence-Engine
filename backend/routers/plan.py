"""Plan router — Generate and retrieve tactical roadmaps."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db
from models import Competitor, Signal, PlanTask, Company
from agents.planner import run_planner

router = APIRouter(prefix="/api/plan", tags=["plan"])


class PlanTaskResponse(BaseModel):
    id: int
    week: int
    title: str
    description: str
    task_type: str
    owner: str
    priority: str
    success_metric: str
    evidence_url: str

    class Config:
        from_attributes = True


@router.post("/generate/{competitor_id}")
async def generate_plan(competitor_id: int, db: AsyncSession = Depends(get_db)):
    """Generate a 4-week tactical roadmap from intelligence signals."""
    # Get competitor
    result = await db.execute(select(Competitor).where(Competitor.id == competitor_id))
    competitor = result.scalar_one_or_none()
    if not competitor:
        raise HTTPException(status_code=404, detail="Competitor not found")

    # Get company
    result = await db.execute(select(Company).where(Company.id == competitor.company_id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    # Get signals
    result = await db.execute(
        select(Signal)
        .where(Signal.competitor_id == competitor_id)
        .order_by(Signal.relevance.desc())
    )
    signals = result.scalars().all()

    if not signals:
        raise HTTPException(status_code=400, detail="No signals found — run analysis first")

    company_profile = {
        "name": company.name,
        "summary": company.summary,
        "features": company.features,
        "positioning": company.positioning,
    }

    signal_dicts = [
        {
            "signal_type": s.signal_type,
            "category": s.category,
            "title": s.title,
            "description": s.description,
            "severity": s.severity,
            "relevance": s.relevance,
            "confidence": s.confidence,
        }
        for s in signals
    ]

    # Run planner
    try:
        roadmap = await run_planner(company_profile, signal_dicts)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Planning failed: {str(e)}")

    # Delete old tasks for this competitor
    old_result = await db.execute(
        select(PlanTask).where(PlanTask.competitor_id == competitor_id)
    )
    for old_task in old_result.scalars().all():
        await db.delete(old_task)

    # Store new tasks
    stored_tasks = []
    for week_data in roadmap.get("roadmap", []):
        week_num = week_data.get("week", 1)
        for task_data in week_data.get("tasks", []):
            task = PlanTask(
                week=week_num,
                title=task_data.get("title", ""),
                description=task_data.get("description", ""),
                task_type=task_data.get("task_type", ""),
                owner=task_data.get("owner", ""),
                priority=task_data.get("priority", "medium"),
                success_metric=task_data.get("success_metric", ""),
                evidence_url=task_data.get("evidence_url", ""),
                competitor_id=competitor_id,
            )
            db.add(task)
            stored_tasks.append(task)

    competitor.status = "done"
    await db.commit()

    for t in stored_tasks:
        await db.refresh(t)

    return {"roadmap": roadmap.get("roadmap", []), "tasks": stored_tasks}


@router.get("/{competitor_id}", response_model=list[PlanTaskResponse])
async def get_plan(competitor_id: int, db: AsyncSession = Depends(get_db)):
    """Get the tactical roadmap for a competitor."""
    result = await db.execute(
        select(PlanTask)
        .where(PlanTask.competitor_id == competitor_id)
        .order_by(PlanTask.week, PlanTask.id)
    )
    return result.scalars().all()
