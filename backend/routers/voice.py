from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from config import settings
from database import get_db
from models import Competitor, Signal
import google.generativeai as genai
from twilio.rest import Client
import urllib.parse
import sys

router = APIRouter(prefix="/api/voice", tags=["voice"])

class VoiceCallRequest(BaseModel):
    competitor_id: int

@router.post("/call")
async def trigger_executive_briefing(req: VoiceCallRequest, db: AsyncSession = Depends(get_db)):
    """Trigger an outbound phone call to the executive with an AI-generated briefing."""
    
    # 1. Check Twilio Configuration
    if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
        raise HTTPException(status_code=500, detail="Twilio credentials are not configured in .env.")
    if not settings.TWILIO_PHONE_NUMBER or not settings.DESTINATION_PHONE_NUMBER:
        raise HTTPException(
            status_code=400, 
            detail="Missing Phone Numbers: Please add TWILIO_PHONE_NUMBER and DESTINATION_PHONE_NUMBER to the .env file."
        )

    # 2. Fetch Competitor Data
    result = await db.execute(select(Competitor).where(Competitor.id == req.competitor_id))
    competitor = result.scalar_one_or_none()
    if not competitor:
        raise HTTPException(status_code=404, detail="Competitor not found.")

    signals_result = await db.execute(select(Signal).where(Signal.competitor_id == req.competitor_id))
    signals = signals_result.scalars().all()
    
    if not signals:
        raise HTTPException(status_code=400, detail="Cannot generate a briefing without completed intelligence signals.")

    intelligence_summary = "\n".join([f"- {s.signal_type.upper()}: {s.title} ({s.severity})" for s in signals])

    # 3. Generate the Spoken Summary using Gemini
    # We want a very conversational, natural-sounding summary optimized for TTS.
    prompt = f"""You are the Compy AI Analyst calling an executive on the phone to give a quick intel briefing.
The competitor is: {competitor.name}.

Here is the raw intelligence data:
{intelligence_summary[:4000]}

Write a spoken script for a phone call. 
Rules:
- Start with "Hello! This is Compy AI with your executive briefing on {competitor.name}."
- Keep it under 60 seconds when spoken (about 120 words maximum).
- Highlight their biggest weakness and their biggest strength.
- Be highly engaging and conversational. Do not use bullet points or markdown, just natural sentences.
- End with "Thank you, and happy selling."
"""

    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = await model.generate_content_async(prompt)
        script = response.text.replace("\n", " ").strip()
    except Exception as e:
        print(f"[VOICE] Failed to generate script: {e}")
        script = f"Hello! This is Compy AI. We encountered an error generating the detailed briefing for {competitor.name}. Please check the dashboard for the full report. Happy selling."

    # 4. Trigger the Outbound Call via Twilio
    try:
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        
        # We use TwiML directly via the twiml parameter to avoid needing a public webhook URL
        # The 'alice' voice sounds professional. We escape the script for XML.
        safe_script = script.replace("<", "").replace(">", "").replace("&", "and")
        twiml = f'<Response><Say voice="alice">{safe_script}</Say></Response>'

        print(f"\n\033[1;36m[VOICE] Dialing {settings.DESTINATION_PHONE_NUMBER} from {settings.TWILIO_PHONE_NUMBER}...\033[0m")
        print(f"\033[1;36m[VOICE] Script: {safe_script}\033[0m\n")

        call = client.calls.create(
            twiml=twiml,
            to=settings.DESTINATION_PHONE_NUMBER,
            from_=settings.TWILIO_PHONE_NUMBER
        )
        
        return {
            "status": "success", 
            "message": "Call initiated successfully.", 
            "call_sid": call.sid
        }
    except Exception as e:
        print(f"[VOICE] Twilio Error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to initiate call via Twilio. Error: {str(e)}")
