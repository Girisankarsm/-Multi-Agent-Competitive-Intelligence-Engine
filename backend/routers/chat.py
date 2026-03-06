from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from database import get_db
from models import Competitor
from agents.chat import chat_with_analyst

router = APIRouter(prefix="/api/chat", tags=["chat"])

class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str

class ChatContext(BaseModel):
    competitor_name: str = "Unknown"
    competitor_url: str = "Unknown"
    pricing_model: str = "Unknown"
    pricing_complaints: List[str] = []
    community_price_perception: str = "Unknown"
    we_win: List[str] = []
    they_win: List[str] = []
    sentiment_score: str = "N/A"
    sentiment_trend: str = "N/A"
    top_praise: List[str] = []
    top_complaints: List[str] = []
    positioning: str = "Unknown"

class ChatRequest(BaseModel):
    competitor_id: int
    context: ChatContext
    history: List[ChatMessage] = []
    message: str

@router.post("")
async def chat(req: ChatRequest, db: AsyncSession = Depends(get_db)):
    """Chat with the AI analyst about a specific competitor."""
    # Verify competitor exists
    result = await db.execute(select(Competitor).where(Competitor.id == req.competitor_id))
    competitor = result.scalar_one_or_none()
    if not competitor:
        raise HTTPException(status_code=404, detail="Competitor not found")

    try:
        reply = await chat_with_analyst(
            competitor_id=req.competitor_id,
            context=req.context.dict(),
            history=[{"role": m.role, "content": m.content} for m in req.history],
            user_message=req.message,
        )
        return {"reply": reply}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
