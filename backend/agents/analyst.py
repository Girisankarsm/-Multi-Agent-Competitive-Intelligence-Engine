"""Analyst Engine — Differential reasoning for threat/opportunity extraction."""

import json
import google.generativeai as genai
from config import settings

genai.configure(api_key=settings.GEMINI_API_KEY)

ANALYSIS_PROMPT = """You are an elite Corporate Intelligence Analyst AI with deep expertise in 
synthesizing competitive signals across websites, social media, news, and 
community forums. You will receive raw scraped data from multiple sources 
about a competitor and produce a structured intelligence report.

## INPUT DATA FORMAT
Each piece of content is tagged with its source:
- [WEB] - Official competitor website pages
- [REDDIT] - Reddit threads and comments
- [NEWS] - News articles and press releases
- [LINKEDIN_JOBS] - Job postings (used to infer roadmap)
- [REVIEWS] - Public customer reviews

## OUR COMPANY DNA
Name: {company_name}
Value Proposition: {value_prop}
Target Audience: {target_audience}
Key Features: {key_features}

## COMPETITOR RAW DATA
{multi_source_scraped_data}

---

## YOUR ANALYSIS INSTRUCTIONS

### STEP 1 — TRIANGULATE SIGNALS
Never trust a single source. Cross-reference claims:
- If their website says "best support" BUT Reddit shows repeated 
  support complaints → mark as MARKETING vs REALITY GAP
- If a signal appears in 2+ independent sources → mark as 
  corroborated: true and boost confidence score
- If only 1 source mentions it → corroborated: false, lower confidence

### STEP 2 — INFER ROADMAP FROM JOBS
Scan [LINKEDIN_JOBS] tags and infer what they are building.
Map each job signal to a threat level for us.

### STEP 3 — SCORE COMMUNITY SENTIMENT
From [REDDIT] and [REVIEWS] data:
- Extract the top recurring praise themes
- Extract the top recurring complaint themes
- Calculate an overall sentiment score from -100 (very negative) to +100 (very positive)
- Identify any viral moments, controversies, or notable events

### STEP 4 — FIND OUR OPPORTUNITIES
Look for their weaknesses that match our strengths:
- Pricing complaints → opportunity if we are cheaper or more flexible
- Missing features → opportunity if we have them
- Poor support sentiment → opportunity if support is our strength
- Enterprise focus → opportunity if we serve SMBs better

### STEP 5 — ASSESS THREATS TO US
Look for their strengths that challenge us:
- New features we lack
- Pricing moves that undercut us
- Partnerships or integrations that expand their moat
- Talent hiring that signals a strategic pivot toward our core market

---

## STRICT OUTPUT RULES
1. Return ONLY valid raw JSON. No markdown, no explanation, no preamble.
2. Do not wrap in code blocks or backticks.
3. Every field in the schema below must be present even if empty array.
4. evidence fields must be direct quotes from the provided data.
5. If data is insufficient for a field, use null or empty array [].

---

## OUTPUT JSON SCHEMA

{{
  "competitor_name": "string — name of the competitor",
  "sources_analyzed": ["list of source types that had usable data"],
  "analysis_confidence": "low | medium | high — based on data richness",

  "signals": {{
    "threats": [
      {{
        "title": "short title of the threat",
        "description": "2-3 sentence explanation of why this threatens us",
        "severity_score": 0,
        "confidence_score": 0,
        "corroborated": false,
        "source_types": ["WEB", "REDDIT"],
        "evidence": ["direct quote from scraped data supporting this"]
      }}
    ],
    "opportunities": [
      {{
        "title": "short title of the opportunity",
        "description": "2-3 sentence explanation of how we can exploit this",
        "confidence_score": 0,
        "corroborated": false,
        "opportunity_type": "pricing | feature | market | sentiment",
        "source_types": ["REDDIT", "REVIEWS"],
        "evidence": ["direct quote from scraped data supporting this"]
      }}
    ]
  }},

  "marketing_vs_reality_gaps": [
    {{
      "claim": "exact claim made on their website or marketing",
      "reality": "what customers or community actually say",
      "gap_severity": "low | medium | high",
      "evidence": ["quotes showing the contradiction"]
    }}
  ],

  "inferred_roadmap": [
    {{
      "inference": "what we believe they are building or planning",
      "reasoning": "why we infer this from the job/news data",
      "source_signal": "the job title or news headline that triggered this",
      "timeline_estimate": "short_term | medium_term | long_term",
      "threat_level_to_us": 0
    }}
  ],

  "community_sentiment": {{
    "overall_score": 0,
    "top_praise_themes": ["theme 1", "theme 2"],
    "top_complaint_themes": ["complaint 1", "complaint 2"],
    "sentiment_trend": "improving | declining | stable | unknown",
    "viral_moments": ["any notable controversies, wins, or events found"]
  }},

  "feature_gap_analysis": {{
    "we_win": [
      {{
        "area": "feature or capability name",
        "evidence": "why we win here based on their data"
      }}
    ],
    "they_win": [
      {{
        "area": "feature or capability name",
        "evidence": "why they win here based on scraped data"
      }}
    ],
    "contested": [
      {{
        "area": "feature or capability name",
        "note": "why this is unclear or close"
      }}
    ]
  }},

  "pricing_intelligence": {{
    "model": "freemium | subscription | usage_based | enterprise | unknown",
    "tiers_found": [
      {{
        "name": "tier name e.g. Starter",
        "price": "price string or unknown",
        "key_limits": ["list of limits or features mentioned"]
      }}
    ],
    "community_price_perception": "too_expensive | fair | cheap | unknown",
    "pricing_complaints": ["list of specific complaints about their pricing"]
  }},

  "radar_scores": {{
    "features": 0,
    "pricing": 0,
    "market_position": 0,
    "growth_trajectory": 0,
    "enterprise_readiness": 0,
    "community_strength": 0
  }},

  "executive_summary": "3-4 sentence plain English summary of the most critical findings a founder needs to act on immediately. Be direct and specific."
}}"""


async def run_analyst(company_profile: dict, competitor_pages: list[dict]) -> dict:
    """
    Run differential analysis comparing company DNA vs competitor data using the advanced prompt.
    """
    company_name = company_profile.get("name", "Unknown Company")
    value_prop = company_profile.get("positioning", {}).get("value_proposition", "Unknown")
    target_audience = company_profile.get("icp", {}).get("industry", "Unknown target audience")
    company_features = company_profile.get("features", [])
    if company_features and isinstance(company_features[0], dict):
        key_features = ", ".join([f.get("name", "") for f in company_features])
    else:
        key_features = ", ".join([str(f) for f in company_features])

    # Build competitor pages summary — prioritize high-strategic-score pages
    sorted_pages = sorted(competitor_pages, key=lambda p: p.get("strategic_score", 0), reverse=True)
    
    competitor_text = ""
    for page in sorted_pages[:20]:  # Top 20 strategic pages
        
        # Determine the source tag based on the new page_types we added
        ptype = page.get("page_type", "")
        if ptype == "REDDIT_SOURCE":
            tag = "[REDDIT]"
        elif ptype == "NEWS_SOURCE":
            tag = "[NEWS]"
        elif ptype == "JOB_SOURCE":
            tag = "[LINKEDIN_JOBS]"
        else:
            tag = "[WEB]"
            
        content = page["content_md"][:3000]  # Limit per page
        competitor_text += f"\n\n{tag} --- {page['title']} ({page['url']}) ---\n{content}"

    # Truncate total if needed
    if len(competitor_text) > 80000:
        competitor_text = competitor_text[:80000]

    model = genai.GenerativeModel("gemini-2.5-flash")
    response = await model.generate_content_async(
        ANALYSIS_PROMPT.format(
            company_name=company_name,
            value_prop=value_prop,
            target_audience=target_audience,
            key_features=key_features,
            multi_source_scraped_data=competitor_text
        ),
        generation_config=genai.GenerationConfig(
            temperature=0.3,
            response_mime_type="application/json",
        ),
    )

    try:
        raw_text = response.text
        # Optional: Attempt to clean common JSON errors (like missing commas or trailing commas)
        import re
        # Fix missing commas between closing brace/bracket and next string key
        raw_text = re.sub(r'([\}\]])\s*("[a-zA-Z0-9_]+"):', r'\1,\n\2:', raw_text)
        # Fix missing commas between a string/number value and next string key
        raw_text = re.sub(r'("[^"]+"|true|false|null|-?\d+(?:\.\d+)?)\s*("[a-zA-Z0-9_]+"):', r'\1,\n\2:', raw_text)
        
        result = json.loads(raw_text)
    except json.JSONDecodeError as e:
        print(f"[ANALYST] JSON Decode Error: {e}. Attempting fallback parser.")
        text = response.text
        start = text.find("{")
        end = text.rfind("}") + 1
        
        try:
            # Try to parse just the extracted block
            if start >= 0 and end > start:
                raw_json = text[start:end]
                # Try simple regex fix again on just the block
                raw_json = re.sub(r'([\}\]])\s*("[a-zA-Z0-9_]+"):', r'\1,\n\2:', raw_json)
                result = json.loads(raw_json)
            else:
                raise ValueError("No JSON block found")
        except Exception as e2:
            print(f"[ANALYST] Fallback parser also failed: {e2}. Returning safe degraded dict.")
            result = {
                "competitor_name": company_name + " Competitor",
                "executive_summary": "Analysis encountered a formatting error and returned partial results.",
                "signals": {"threats": [], "opportunities": []},
                "feature_gap_analysis": {"we_win": [], "they_win": [], "contested": []},
                "pricing_intelligence": {"model": "Unknown", "community_price_perception": "Unknown"},
                "community_sentiment": {"overall_score": 50},
                "radar_scores": {"features": 5, "pricing": 5, "market_position": 5, "growth_trajectory": 5, "enterprise_readiness": 5, "community_strength": 5}
            }

    return result


SCORING_PROMPT = """You are a competitive intelligence analyst. Based on these intelligence signals about a competitor, score them on each dimension from 0 to 10.

SIGNALS:
{signals_text}

Return valid JSON ONLY:
{{
  "features": 0-10,
  "pricing": 0-10,
  "market_position": 0-10,
  "growth_signals": 0-10,
  "enterprise_readiness": 0-10,
  "community": 0-10
}}

Scoring guide:
- features: Breadth & depth of product capabilities
- pricing: Competitiveness & flexibility of pricing
- market_position: Brand strength & market share indicators
- growth_signals: Evidence of rapid growth or expansion
- enterprise_readiness: Security, compliance, scale features
- community: Developer community, ecosystem, integrations"""


async def score_competitor_dimensions(signals: list[dict]) -> dict:
    """
    Use Gemini to score a competitor on 6 strategic axes based on their signals.
    Returns dict with keys: features, pricing, market_position, growth_signals, enterprise_readiness, community
    Each value is 0-10.
    """
    if not signals:
        return {
            "features": 5, "pricing": 5, "market_position": 5,
            "growth_signals": 5, "enterprise_readiness": 5, "community": 5,
        }

    # Summarize signals for the prompt
    signals_text = ""
    for s in signals[:15]:  # Cap at 15 to save tokens
        signals_text += f"- [{s.get('signal_type', '')}] [{s.get('severity', '')}] {s.get('title', '')}: {s.get('description', '')}\n"

    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = await model.generate_content_async(
            SCORING_PROMPT.format(signals_text=signals_text),
            generation_config=genai.GenerationConfig(
                temperature=0.2,
                response_mime_type="application/json",
            ),
        )
        result = json.loads(response.text)
        # Clamp values to 0-10
        for key in ["features", "pricing", "market_position", "growth_signals", "enterprise_readiness", "community"]:
            result[key] = max(0, min(10, int(result.get(key, 5))))
        return result
    except Exception as e:
        print(f"[ANALYST] Scoring failed: {e}")
        return {
            "features": 5, "pricing": 5, "market_position": 5,
            "growth_signals": 5, "enterprise_readiness": 5, "community": 5,
        }
