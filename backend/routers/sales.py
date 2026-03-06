from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db
from models import Competitor, Company
from agents.sales import generate_sales_sequence

# We need a way to get the analysis data. The `AnalysisResult` isn't saved directly as JSON, 
# but we can re-create a brief summary or in this hackathon context, we might accept the data from the frontend 
# or run a quick inference. The easiest way for a stateless hackathon feature is to accept the context in the POST body.

router = APIRouter(prefix="/api/sales", tags=["sales"])

class SalesGenRequest(BaseModel):
    competitor_name: str
    pricing_model: str
    pricing_complaints: list[str]
    we_win_features: list[str]

@router.post("/generate/{competitor_id}")
async def fetch_sales_sequence(competitor_id: int, req: SalesGenRequest, db: AsyncSession = Depends(get_db)):
    """Generate a 3-touch sales email sequence."""
    result = await db.execute(select(Competitor).where(Competitor.id == competitor_id))
    competitor = result.scalar_one_or_none()
    if not competitor:
        raise HTTPException(status_code=404, detail="Competitor not found")

    result = await db.execute(select(Company).where(Company.id == competitor.company_id))
    company = result.scalar_one_or_none()

    comp_name = company.name if company else "Our Company"
    val_prop = company.positioning.get("value_proposition", "") if company else ""
    features = ", ".join([f.get("name", str(f)) for f in company.features]) if company and company.features else ""

    try:
        emails = await generate_sales_sequence(
            company_name=comp_name,
            value_prop=val_prop,
            our_features=features,
            competitor_name=req.competitor_name,
            pricing_model=req.pricing_model,
            pricing_complaints=", ".join(req.pricing_complaints),
            we_win_features=", ".join(req.we_win_features)
        )
        return emails
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class SalesSendRequest(BaseModel):
    recipient_email: str
    subject: str
    body: str

@router.post("/send")
async def send_sales_email(req: SalesSendRequest):
    """Send an email using SMTP (for the hackathon demo) or simulate if no creds."""
    import asyncio
    import smtplib
    from email.mime.text import MIMEText
    from config import settings
    
    # 1. Log exactly what we "sent" to the terminal to prove it to the judges
    print("\n\033[1;35m" + "═" * 60 + "\033[0m")
    print(f"\033[1;35m🚀 DISPATCHING SALES EMAIL\033[0m")
    print(f"\033[1;36mTO:\033[0m {req.recipient_email}")
    print(f"\033[1;36mSUBJECT:\033[0m {req.subject}")
    print(f"\033[1;36mBODY:\033[0m\n{req.body}")
    print("\033[1;35m" + "═" * 60 + "\033[0m\n")
    
    # 2. Try sending real email if SMTP credentials exist
    try:
        if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
            # Ensure it is parsed as HTML in Gmail
            html_body = req.body
            # Fallback just in case Gemini forgot to use HTML tags
            if "<p>" not in html_body and "<br>" not in html_body:
                html_body = html_body.replace('\n', '<br>')
                
            msg = MIMEText(html_body, 'html')
            msg['Subject'] = req.subject
            msg['From'] = settings.FROM_EMAIL
            msg['To'] = req.recipient_email

            # Connect to SMTP server
            with smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT) as server:
                server.starttls()
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                server.send_message(msg)
            
            return {"status": "success", "message": f"Successfully sent real email to {req.recipient_email}"}
        else:
            # 3. Simulate network latency if no keys
            await asyncio.sleep(1.5)
            return {"status": "success", "message": f"Simulated send to {req.recipient_email}. (Add SMTP keys to .env)"}
    except Exception as e:
        print(f"SMTP Error: {e}")
        raise HTTPException(status_code=500, detail=f"Email failed to send. Check SMTP credentials. Error: {str(e)}")
