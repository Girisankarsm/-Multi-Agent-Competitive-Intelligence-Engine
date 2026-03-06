import json
import google.generativeai as genai
from config import settings

genai.configure(api_key=settings.GEMINI_API_KEY)

SALES_PROMPT = """You are an elite B2B Outbound Sales Copywriter. 
Your goal is to write a highly converting, 3-touch cold email sequence targeting customers of our competitor.

## OUR COMPANY
Name: {company_name}
Value Proposition: {value_prop}
Features: {our_features}

## THE COMPETITOR
Name: {competitor_name}
Competitor Pricing Model: {pricing_model}
What the Community is saying about their pricing: {pricing_complaints}
Where WE Win against them: {we_win_features}

## INSTRUCTIONS
Write a 3-touch sequence targeting someone currently using {competitor_name}. 
Focus heavily on the pain points we know they have (pricing complaints, missing features).
Keep emails short, punchy, and under 150 words. No buzzwords. Use a casual, founder-to-founder tone.

CRITICAL: 
1. You MUST explicitly mention our company name ({company_name}) as the better alternative in the body of the emails.
2. Sign off the emails as a representative of {company_name} (e.g., "Best,\\n[Your Name]\\n{company_name}").

Return valid JSON ONLY matching this exact schema:
{{
  "sequence": [
    {{
      "touch": 1,
      "subject": "Catchy subject line",
      "body": "Hi First Name,\\n\\nBody text here...\\n\\nSignoff,"
    }},
    {{
      "touch": 2,
      "subject": "Re: previous subject or new",
      "body": "Hi First Name,\\n\\nBody text here...\\n\\nSignoff,"
    }},
    {{
      "touch": 3,
      "subject": "Breakup subject",
      "body": "Hi First Name,\\n\\nBody text here...\\n\\nSignoff,"
    }}
  ]
}}
"""

async def generate_sales_sequence(
    company_name: str, 
    value_prop: str, 
    our_features: str, 
    competitor_name: str, 
    pricing_model: str, 
    pricing_complaints: str, 
    we_win_features: str
) -> dict:
    model = genai.GenerativeModel("gemini-2.5-flash")
    prompt = SALES_PROMPT.format(
        company_name=company_name,
        value_prop=value_prop,
        our_features=our_features,
        competitor_name=competitor_name,
        pricing_model=pricing_model,
        pricing_complaints=pricing_complaints,
        we_win_features=we_win_features
    )

    response = await model.generate_content_async(
        prompt,
        generation_config=genai.GenerationConfig(
            temperature=0.7, # Higher temp for more creative copy
            response_mime_type="application/json",
        ),
    )

    try:
        result = json.loads(response.text)
    except json.JSONDecodeError:
        text = response.text
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            result = json.loads(text[start:end])
        else:
            result = {"sequence": []}

    return result
