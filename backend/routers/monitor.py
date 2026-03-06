"""Monitor router — Manage monitoring jobs and retrieve change alerts."""

import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db
from models import MonitorJob, ChangeAlert, Competitor
from services.scheduler import _compute_next_run

router = APIRouter(prefix="/api/monitor", tags=["monitor"])


class MonitorRequest(BaseModel):
    schedule: str = "weekly"   # 'daily' or 'weekly'
    is_active: bool = True


class MonitorResponse(BaseModel):
    id: int
    competitor_id: int
    schedule: str
    last_run: Optional[datetime.datetime] = None
    next_run: Optional[datetime.datetime] = None
    is_active: bool
    created_at: Optional[datetime.datetime] = None

    class Config:
        from_attributes = True


class ChangeAlertResponse(BaseModel):
    id: int
    competitor_id: int
    detected_at: Optional[datetime.datetime] = None
    new_signals: list
    disappeared_signals: list
    severity_changes: list
    summary: str
    created_at: Optional[datetime.datetime] = None

    class Config:
        from_attributes = True


@router.post("/{competitor_id}", response_model=MonitorResponse)
async def set_monitor(competitor_id: int, req: MonitorRequest, db: AsyncSession = Depends(get_db)):
    """Create or update a monitoring job for a competitor."""
    # Validate schedule
    if req.schedule not in ("daily", "weekly"):
        raise HTTPException(status_code=400, detail="Schedule must be 'daily' or 'weekly'")

    # Verify competitor exists
    comp_result = await db.execute(select(Competitor).where(Competitor.id == competitor_id))
    competitor = comp_result.scalar_one_or_none()
    if not competitor:
        raise HTTPException(status_code=404, detail="Competitor not found")

    # Check for existing monitor job
    result = await db.execute(
        select(MonitorJob).where(MonitorJob.competitor_id == competitor_id)
    )
    job = result.scalar_one_or_none()

    now = datetime.datetime.utcnow()

    if job:
        # Update existing
        job.schedule = req.schedule
        job.is_active = 1 if req.is_active else 0
        if req.is_active and not job.next_run:
            job.next_run = _compute_next_run(req.schedule, now)
        elif not req.is_active:
            job.next_run = None
    else:
        # Create new
        job = MonitorJob(
            competitor_id=competitor_id,
            schedule=req.schedule,
            is_active=1 if req.is_active else 0,
            next_run=_compute_next_run(req.schedule, now) if req.is_active else None,
        )
        db.add(job)

    await db.commit()
    await db.refresh(job)

    return MonitorResponse(
        id=job.id,
        competitor_id=job.competitor_id,
        schedule=job.schedule,
        last_run=job.last_run,
        next_run=job.next_run,
        is_active=bool(job.is_active),
        created_at=job.created_at,
    )


@router.get("/{competitor_id}", response_model=MonitorResponse)
async def get_monitor(competitor_id: int, db: AsyncSession = Depends(get_db)):
    """Get the current monitoring settings for a competitor."""
    result = await db.execute(
        select(MonitorJob).where(MonitorJob.competitor_id == competitor_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="No monitoring job found for this competitor")

    return MonitorResponse(
        id=job.id,
        competitor_id=job.competitor_id,
        schedule=job.schedule,
        last_run=job.last_run,
        next_run=job.next_run,
        is_active=bool(job.is_active),
        created_at=job.created_at,
    )


@router.get("/{competitor_id}/alerts", response_model=list[ChangeAlertResponse])
async def get_alerts(competitor_id: int, db: AsyncSession = Depends(get_db)):
    """Get all change alerts for a competitor, newest first."""
    result = await db.execute(
        select(ChangeAlert)
        .where(ChangeAlert.competitor_id == competitor_id)
        .order_by(ChangeAlert.detected_at.desc())
    )
    alerts = result.scalars().all()

    return [
        ChangeAlertResponse(
            id=a.id,
            competitor_id=a.competitor_id,
            detected_at=a.detected_at,
            new_signals=a.new_signals or [],
            disappeared_signals=a.disappeared_signals or [],
            severity_changes=a.severity_changes or [],
            summary=a.summary or "",
            created_at=a.created_at,
        )
        for a in alerts
    ]
