"""Planner Agent — Generates a 4-week tactical roadmap from intelligence signals."""

import json
import google.generativeai as genai
from config import settings

genai.configure(api_key=settings.GEMINI_API_KEY)

PLANNER_PROMPT = """You are a strategic product/marketing advisor. Given competitive intelligence signals and the company's DNA, create a 4-week tactical action plan.

YOUR COMPANY DNA:
{company_profile}

COMPETITIVE SIGNALS (ranked by severity):
{signals}

Create a 4-week actionable roadmap. Return valid JSON ONLY:
{{
  "roadmap": [
    {{
      "week": 1,
      "theme": "Week theme (e.g., 'Defensive: Protect Core Position')",
      "tasks": [
        {{
          "title": "Specific, actionable task title",
          "description": "What to do and why (2-3 sentences)",
          "task_type": "defensive" or "offensive",
          "owner": "Product | Marketing | Engineering | Sales | Leadership",
          "priority": "critical" | "high" | "medium" | "low",
          "success_metric": "Measurable outcome (e.g., 'Comparison page published with 500+ visits in Week 1')",
          "evidence_url": "URL of the competitor evidence that triggered this task"
        }}
      ]
    }}
  ]
}}

RULES:
- Week 1-2: Prioritize DEFENSIVE actions (protect against threats)
- Week 3-4: Shift to OFFENSIVE actions (exploit opportunities)
- Each week should have 2-4 tasks
- Every task must link back to a specific intelligence signal
- Success metrics must be specific and measurable
- Tasks should be achievable within a week
- Mix owners across Product, Marketing, Engineering, Sales"""


async def run_planner(company_profile: dict, signals: list[dict]) -> dict:
    """
    Generate a 4-week tactical roadmap based on competitive signals.
    
    Args:
        company_profile: User's company DNA dict
        signals: List of scored signal dicts from analyst engine
    
    Returns:
        Roadmap dict with weekly tasks
    """
    company_text = json.dumps({
        "name": company_profile.get("name", ""),
        "summary": company_profile.get("summary", ""),
        "features": company_profile.get("features", []),
        "positioning": company_profile.get("positioning", {}),
    }, indent=2)

    # Sort signals by severity/relevance
    severity_order = {"existential": 0, "moderate": 1, "minor": 2}
    sorted_signals = sorted(
        signals,
        key=lambda s: (severity_order.get(s.get("severity", "minor"), 2), -s.get("relevance", 0))
    )

    signals_text = json.dumps(sorted_signals, indent=2)

    # Truncate if needed
    if len(signals_text) > 30000:
        signals_text = signals_text[:30000]

    model = genai.GenerativeModel("gemini-2.5-flash")
    response = await model.generate_content_async(
        PLANNER_PROMPT.format(
            company_profile=company_text,
            signals=signals_text
        ),
        generation_config=genai.GenerationConfig(
            temperature=0.4,
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
            result = {"roadmap": []}

    return result
