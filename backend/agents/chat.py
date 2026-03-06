import json
import google.generativeai as genai
from config import settings

genai.configure(api_key=settings.GEMINI_API_KEY)

CHAT_SYSTEM_PROMPT = """You are Compy AI, an elite Competitive Intelligence Analyst embedded inside the Compy platform.
You have been given a full intelligence dossier on a competitor. 
Your job is to answer strategic sales, marketing, and product questions from the user's team in a concise, direct, and actionable manner.
You are talking to a founder or a sales leader. Be sharp. No fluff. No disclaimers.

## COMPETITOR INTELLIGENCE DOSSIER
Competitor Name: {competitor_name}
Competitor URL: {competitor_url}

### Pricing
Model: {pricing_model}
Community Sentiment on Pricing: {pricing_complaints}
Community Price Perception: {community_price_perception}

### Where We Win (Feature Gaps)
{we_win}

### Where They Win (Feature Gaps)
{they_win}

### Community Sentiment
Overall Score: {sentiment_score}/100
Trend: {sentiment_trend}
Top Praise: {top_praise}
Top Complaints: {top_complaints}

### Competitor's Strategic Positioning
{positioning}

## IMPORTANT GUIDELINES
- Answer questions only based on the intelligence dossier above.
- If asked to write an email or sales script, do so. Keep it short and punchy.
- If you don't have enough data to answer, say "I don't have enough intel on that yet."
- Never make up data that is not in the dossier.
- Keep responses short (max 150 words) unless the user explicitly asks for something longer.
"""

async def chat_with_analyst(competitor_id: int, context: dict, history: list, user_message: str) -> str:
    system_prompt = CHAT_SYSTEM_PROMPT.format(
        competitor_name=context.get("competitor_name", "Unknown"),
        competitor_url=context.get("competitor_url", "Unknown"),
        pricing_model=context.get("pricing_model", "Unknown"),
        pricing_complaints=", ".join(context.get("pricing_complaints", [])),
        community_price_perception=context.get("community_price_perception", "Unknown"),
        we_win="\n".join([f"- {f}" for f in context.get("we_win", [])]) or "None identified",
        they_win="\n".join([f"- {f}" for f in context.get("they_win", [])]) or "None identified",
        sentiment_score=context.get("sentiment_score", "N/A"),
        sentiment_trend=context.get("sentiment_trend", "N/A"),
        top_praise=", ".join(context.get("top_praise", [])),
        top_complaints=", ".join(context.get("top_complaints", [])),
        positioning=context.get("positioning", "Unknown"),
    )

    # Define the Email Sending Tool
    send_email_tool = {
        "function_declarations": [
            {
                "name": "send_email",
                "description": "Send a sales or intelligence email to a specific recipient.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "recipient_email": {
                            "type": "STRING",
                            "description": "The exact email address to send to."
                        },
                        "subject": {
                            "type": "STRING",
                            "description": "A catchy, relevant subject line."
                        },
                        "body": {
                            "type": "STRING",
                            "description": "The body of the email. MUST be formatted in crisp, professional HTML. Use <p>, <b>, <i>, <ul>, <li>, and <br> tags to make it highly readable and look like a premium corporate email in Gmail. Do NOT wrap the output in markdown blockquotes or ```html tags."
                        }
                    },
                    "required": ["recipient_email", "subject", "body"]
                }
            }
        ]
    }

    # Define the Voice Calling Tool
    send_voice_tool = {
        "function_declarations": [
            {
                "name": "send_voice_briefing",
                "description": "Trigger an executive briefing phone call to the provided phone number.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "phone_number": {
                            "type": "STRING",
                            "description": "The phone number to call. MUST be in E.164 format. If the user provides a 10-digit Indian number, you MUST prepend '+91' to it (e.g., '+917539962693')."
                        }
                    },
                    "required": ["phone_number"]
                }
            }
        ]
    }

    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        system_instruction=system_prompt,
        tools=[send_email_tool["function_declarations"][0], send_voice_tool["function_declarations"][0]]
    )

    # Convert history to Gemini format
    gemini_history = []
    for msg in history:
        gemini_history.append({
            "role": "user" if msg["role"] == "user" else "model",
            "parts": [msg["content"]]
        })

    chat = model.start_chat(history=gemini_history)
    response = await chat.send_message_async(user_message)

    # Check if the model decided to call the send_email function
    if response.parts and hasattr(response.parts[0], 'function_call') and response.parts[0].function_call:
        fc = response.parts[0].function_call
        if fc.name == "send_email":
            args = fc.args
            recipient = args.get("recipient_email")
            subject = args.get("subject")
            body = args.get("body")
            
            from routers.sales import SalesSendRequest, send_sales_email
            req = SalesSendRequest(recipient_email=recipient, subject=subject, body=body)
            try:
                import sys
                print(f"\\n\\033[1;33m[AGENT] Chatbot executing send_email...\\033[0m", file=sys.stderr)
                send_result = await send_sales_email(req)
                status_msg = send_result.get("message", "Success")
                return f"📧 **Email Sent!**\\n\\nI've successfully dispatched the email to **{recipient}** with the subject *'{subject}'*.\\n\\n*(System Status: {status_msg})*"
            except Exception as e:
                return f"❌ **Email Delivery Failed:** {str(e)}"

        elif fc.name == "send_voice_briefing":
            args = fc.args
            phone_number = args.get("phone_number")
            
            try:
                import sys
                print(f"\\n\\033[1;33m[AGENT] Chatbot executing send_voice_briefing to {phone_number}...\\033[0m", file=sys.stderr)
                
                from database import async_session
                from models import Competitor, Signal
                from sqlalchemy import select
                from config import settings
                from twilio.rest import Client
                
                async with async_session() as db:
                    # 1. Fetch Competitor and Signals
                    result = await db.execute(select(Competitor).where(Competitor.id == competitor_id))
                    competitor = result.scalar_one_or_none()
                    
                    if not competitor:
                        return "❌ **Voice Call Failed:** Could not find the competitor in the database."
                        
                    signals_result = await db.execute(select(Signal).where(Signal.competitor_id == competitor_id))
                    signals = signals_result.scalars().all()
                    
                    if not signals:
                        return "❌ **Voice Call Failed:** No intelligence signals found to brief you on."
                        
                    intelligence_summary = "\\n".join([f"- {s.signal_type.upper()}: {s.title} ({s.severity})" for s in signals])
                    
                    # 2. Generate Script
                    prompt = f"You are the Compy AI Analyst calling an executive on the phone to give a quick intel briefing.\\nThe competitor is: {competitor.name}.\\n\\nHere is the raw intelligence data:\\n{intelligence_summary[:4000]}\\n\\nWrite a spoken script for a phone call. \\nRules:\\n- Start with 'Hello! This is Compy AI with your executive briefing on {competitor.name}.'\\n- Keep it under 60 seconds when spoken.\\n- Highlight their biggest weakness and their biggest strength.\\n- Be highly engaging and conversational. Do not use bullet points or markdown, just natural sentences.\\n- End with 'Thank you, and happy selling.'"
                    
                    script_model = genai.GenerativeModel("gemini-2.5-flash")
                    script_resp = await script_model.generate_content_async(prompt)
                    script = script_resp.text.replace("\\n", " ").strip()
                    
                    # 3. Call via Twilio
                    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
                    safe_script = script.replace("<", "").replace(">", "").replace("&", "and")
                    twiml = f'<Response><Say voice="alice">{safe_script}</Say></Response>'
                    
                    call = client.calls.create(
                        twiml=twiml,
                        to=phone_number,
                        from_=settings.TWILIO_PHONE_NUMBER
                    )
                
                return f"📞 **Outbound Call Initiated!**\n\nI am dialing **{phone_number}** right now to deliver the executive briefing.\n\n*(System Status: Success, Call SID: {call.sid})*"
            except Exception as e:
                import traceback
                print(f"VOICE CALL ERROR: {e}")
                traceback.print_exc()
                return f"❌ **Voice Call Failed:** {str(e)}"

    return response.text
