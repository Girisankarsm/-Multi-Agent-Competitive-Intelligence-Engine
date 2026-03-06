"""DNA Extractor Agent — Analyzes user's company from their website URL."""

import json
import google.generativeai as genai
from config import settings

genai.configure(api_key=settings.GEMINI_API_KEY)

DNA_EXTRACTION_PROMPT = """You are a competitive intelligence analyst. Analyze the following company website content and extract a comprehensive company profile.

COMPANY WEBSITE CONTENT:
{content}

COMPANY URL: {url}

Extract the following in valid JSON format ONLY (no markdown, no explanation):
{{
  "name": "Company name",
  "summary": "2-3 paragraph summary of what the company does, their market, and value proposition",
  "features": [
    {{"name": "Feature name", "description": "What it does", "category": "Category (e.g., Core Product, Analytics, Integration, Security)"}}
  ],
  "icp": {{
    "segments": ["Target market segments"],
    "personas": ["Key buyer/user personas"],
    "pain_points": ["Problems the company solves"],
    "company_size": "Target company size range"
  }},
  "positioning": {{
    "value_proposition": "Core value prop in one sentence",
    "differentiators": ["What makes them unique"],
    "market_position": "Leader/Challenger/Niche/etc",
    "tone": "Brand voice description"
  }},
  "pricing": {{
    "model": "Freemium/Subscription/Usage-based/etc",
    "tiers": [
      {{"name": "Tier name", "price": "Price or price range", "features": ["Key features in this tier"]}}
    ],
    "notes": "Any additional pricing observations"
  }}
}}

Be thorough and specific. Base analysis ONLY on the content provided. If information is not available, use reasonable inference but note it."""


async def extract_company_dna(url: str, page_contents: list[dict]) -> dict:
    """
    Run the DNA extraction agent on scraped company pages.
    
    Args:
        url: The company's URL
        page_contents: List of {url, title, content} dicts from scraped pages
    
    Returns:
        Structured company profile dict
    """
    # Combine all page contents
    combined = ""
    for page in page_contents:
        combined += f"\n\n--- PAGE: {page['title']} ({page['url']}) ---\n{page['content']}"

    # Truncate if too long (Gemini context)
    if len(combined) > 80000:
        combined = combined[:80000]

    model = genai.GenerativeModel("gemini-2.5-flash")
    response = await model.generate_content_async(
        DNA_EXTRACTION_PROMPT.format(content=combined, url=url),
        generation_config=genai.GenerationConfig(
            temperature=0.2,
            response_mime_type="application/json",
        ),
    )

    try:
        result = json.loads(response.text)
    except json.JSONDecodeError:
        # Try to extract JSON from response
        text = response.text
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            result = json.loads(text[start:end])
        else:
            result = {"name": "Unknown", "summary": text, "features": [], "icp": {}, "positioning": {}, "pricing": {}}

    return result
