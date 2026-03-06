"""Scout Agent — Intelligent competitor website crawler with strategic link ranking."""

import json
import asyncio
import traceback
import google.generativeai as genai
from config import settings
from services.scraper import fetch_page, html_to_markdown, extract_title, extract_links
from services.event_bus import event_bus

genai.configure(api_key=settings.GEMINI_API_KEY)

LINK_RANKING_PROMPT = """You are a competitive intelligence analyst. Given a list of URLs from a competitor website, rank them by strategic importance for competitive analysis.

Strategic pages include: pricing, features, enterprise plans, product comparisons, case studies, about/team, integrations, API docs, security/compliance pages.

Low-value pages include: blog posts (unless strategy-related), careers, legal/terms, support docs, generic marketing.

URLS TO RANK:
{urls}

Return valid JSON ONLY — an array of objects, each with:
- "url": the URL
- "score": strategic importance 0-100
- "reason": one-line explanation

Sort by score descending. Only include URLs with score >= 30.
"""

PAGE_CLASSIFY_PROMPT = """Classify this webpage into ONE category based on its content:

TITLE: {title}
URL: {url}
CONTENT (first 2000 chars): {content}

Categories: Pricing, Features, Product, Enterprise, Integrations, API, Security, About, Case Study, Blog, Comparison, Documentation, Other

Return valid JSON ONLY:
{{"page_type": "Category", "strategic_score": 0-100, "summary": "One line summary"}}
"""


def _quick_classify_url(url: str) -> tuple:
    """Fast heuristic classification based on URL patterns — no Gemini call needed."""
    url_lower = url.lower()
    if any(kw in url_lower for kw in ["/pricing", "/plans", "/price"]):
        return "Pricing", 90
    elif any(kw in url_lower for kw in ["/features", "/product", "/solutions"]):
        return "Features", 85
    elif any(kw in url_lower for kw in ["/enterprise", "/business"]):
        return "Enterprise", 80
    elif any(kw in url_lower for kw in ["/integrations", "/apps", "/marketplace"]):
        return "Integrations", 75
    elif any(kw in url_lower for kw in ["/about", "/team", "/company"]):
        return "About", 70
    elif any(kw in url_lower for kw in ["/security", "/compliance", "/trust"]):
        return "Security", 70
    elif any(kw in url_lower for kw in ["/api", "/developers", "/docs"]):
        return "API", 65
    elif any(kw in url_lower for kw in ["/case-study", "/customers", "/stories"]):
        return "Case Study", 60
    elif any(kw in url_lower for kw in ["/compare", "/vs", "/alternative"]):
        return "Comparison", 85
    elif any(kw in url_lower for kw in ["/blog", "/post", "/article"]):
        return "Blog", 30
    elif any(kw in url_lower for kw in ["/careers", "/jobs", "/legal", "/terms", "/privacy", "/cookie"]):
        return None, 0  # Skip these entirely
    return None, None  # Unknown — needs AI classification


def _quick_rank_links(links: list) -> list:
    """Fast heuristic link ranking based on URL patterns — no Gemini call needed."""
    strategic_keywords = [
        "pricing", "features", "product", "enterprise", "plans",
        "integrations", "about", "security", "api", "solutions",
        "compare", "customers", "case-stud", "trust", "platform"
    ]
    skip_keywords = [
        "blog", "careers", "jobs", "legal", "terms", "privacy",
        "cookie", "press", "media", "login", "signup", "sign-up",
        "support", "help", "community", "forum", "status"
    ]
    
    ranked = []
    for link in links:
        link_lower = link.lower()
        
        # Skip low-value links
        if any(kw in link_lower for kw in skip_keywords):
            continue
        
        # Score based on presence of strategic keywords
        score = 40  # base score
        for kw in strategic_keywords:
            if kw in link_lower:
                score = max(score, 75)
                break
        
        ranked.append({"url": link, "score": score})
    
    # Sort by score, then by URL length (shorter = more likely to be main page)
    ranked.sort(key=lambda x: (-x["score"], len(x["url"])))
    return ranked[:15]  # Top 15 links


async def classify_page_with_ai(url: str, title: str, content: str) -> dict:
    """Classify a page using Gemini (with timeout)."""
    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = await asyncio.wait_for(
            model.generate_content_async(
                PAGE_CLASSIFY_PROMPT.format(title=title, url=url, content=content[:2000]),
                generation_config=genai.GenerationConfig(
                    temperature=0.1,
                    response_mime_type="application/json",
                ),
            ),
            timeout=30.0,  # 30 second timeout
        )
        return json.loads(response.text)
    except asyncio.TimeoutError:
        print(f"[SCOUT] ⏱️ AI classify timed out for {url}")
        return {"page_type": "Other", "strategic_score": 50, "summary": "Classification timed out"}
    except Exception as e:
        print(f"[SCOUT] ❌ AI classify failed for {url}: {e}")
        return {"page_type": "Other", "strategic_score": 50, "summary": "Classification failed"}


async def _fetch_one(url: str, timeout: float = 8.0):
    """Fetch a single page with timeout, returning (url, html, status) or None."""
    try:
        html, status = await asyncio.wait_for(fetch_page(url), timeout=timeout)
        return url, html, status
    except Exception:
        return url, None, 0


async def run_scout(job_id: str, competitor_url: str, max_pages: int = 10) -> list:
    """
    Run the full scout agent: crawl, rank, classify.
    
    Streams progress via the event bus.
    Returns list of page dicts: {url, title, content_md, page_type, strategic_score}
    """
    visited = set()
    pages = []
    to_visit = [competitor_url]

    print(f"[SCOUT] Starting crawl of {competitor_url}, max_pages={max_pages}")
    
    await event_bus.publish(job_id, "status", {
        "message": f"🚀 Starting intelligent crawl of {competitor_url}",
        "phase": "init"
    })

    while to_visit and len(pages) < max_pages:
        # Batch-fetch up to 4 pages concurrently for speed
        batch_size = min(4, max_pages - len(pages), len(to_visit))
        if batch_size <= 0:
            break

        batch_urls = []
        while to_visit and len(batch_urls) < batch_size:
            url = to_visit.pop(0)
            if url.endswith("/"):
                url = url[:-1]
            if url in visited:
                continue
            visited.add(url)
            batch_urls.append(url)

        if not batch_urls:
            continue

        print(f"[SCOUT] Fetching batch of {len(batch_urls)} pages...")
        await event_bus.publish(job_id, "crawl", {
            "message": f"📡 Fetching {len(batch_urls)} pages concurrently...",
            "pages_found": len(pages)
        })

        # Concurrent fetch
        results = await asyncio.gather(*[_fetch_one(u) for u in batch_urls])

        for url, html, status in results:
            if html is None or status != 200:
                print(f"[SCOUT] ⚠️ Skip {url} (status={status})")
                continue

            title = extract_title(html)
            content_md = html_to_markdown(html)

            if len(content_md) < 50:
                continue

            page_type, strategic_score = _quick_classify_url(url)
            if page_type is None and strategic_score == 0:
                continue
            if page_type is None:
                classification = await classify_page_with_ai(url, title, content_md)
                page_type = classification.get("page_type", "Other")
                strategic_score = classification.get("strategic_score", 50)

            print(f"[SCOUT] ✅ {page_type} (score={strategic_score}): {title}")
            await event_bus.publish(job_id, "classified", {
                "message": f"🎯 {title or url}",
                "url": url,
                "page_type": f"💭 {page_type}",
                "strategic_score": f"📊 Score: {strategic_score}"
            })

            pages.append({
                "url": url,
                "title": title,
                "content_md": content_md,
                "page_type": page_type,
                "strategic_score": strategic_score,
            })

            if len(pages) >= max_pages:
                break

            # Extract links from this page
            links = extract_links(html, url)
            new_links = [l for l in links if l not in visited]
            if new_links:
                ranked = _quick_rank_links(new_links)
                for item in ranked:
                    link_url = item.get("url", "")
                    if link_url and link_url not in visited:
                        to_visit.append(link_url)

    print(f"[SCOUT] 🏁 Crawl complete: {len(pages)} pages from {competitor_url}")
    
    await event_bus.publish(job_id, "done", {
        "message": f"✅ Crawl complete! Scraped {len(pages)} strategic pages.",
        "total_pages": len(pages)
    })

    return pages
