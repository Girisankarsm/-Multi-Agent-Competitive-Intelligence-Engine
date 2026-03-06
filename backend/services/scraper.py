"""Web scraping utilities: HTTP fetch, HTML cleaning, link extraction, and Multi-Source APIs."""

import re
import urllib.parse
from urllib.parse import urljoin, urlparse
import feedparser
import httpx
from bs4 import BeautifulSoup


# Reusable client — avoids creating a new TCP connection per request
_client = None


async def _get_client() -> httpx.AsyncClient:
    """Get or create a shared async HTTP client for connection reuse."""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            follow_redirects=True,
            timeout=8.0,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
    return _client


# ==========================================
# CORE WEB SCRAPING ALGORITHMS
# ==========================================

async def fetch_page(url: str, timeout: float = 8.0) -> tuple[str, int]:
    """Fetch a URL and return (html_content, status_code)."""
    client = await _get_client()
    try:
        resp = await client.get(url, timeout=timeout)
        return resp.text, resp.status_code
    except Exception as e:
        print(f"[SCRAPER] Error fetching {url}: {e}")
        return "", 500


def html_to_markdown(html: str) -> str:
    """Convert HTML to clean, readable text/markdown."""
    soup = BeautifulSoup(html, "lxml")

    # Remove non-content elements
    for tag in soup.find_all(["script", "style", "nav", "footer", "header", "iframe", "noscript"]):
        tag.decompose()

    lines = []
    for elem in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "td", "th", "blockquote"]):
        text = elem.get_text(strip=True)
        if not text:
            continue
        tag = elem.name
        if tag == "h1":
            lines.append(f"# {text}")
        elif tag == "h2":
            lines.append(f"## {text}")
        elif tag == "h3":
            lines.append(f"### {text}")
        elif tag in ("h4", "h5", "h6"):
            lines.append(f"#### {text}")
        elif tag == "li":
            lines.append(f"- {text}")
        elif tag == "blockquote":
            lines.append(f"> {text}")
        else:
            lines.append(text)

    content = "\n\n".join(lines)
    # Collapse excessive whitespace
    content = re.sub(r"\n{3,}", "\n\n", content)
    return content.strip()


def extract_title(html: str) -> str:
    """Extract the page title from HTML."""
    soup = BeautifulSoup(html, "lxml")
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    h1 = soup.find("h1")
    if h1:
        return h1.get_text(strip=True)
    return ""


def extract_links(html: str, base_url: str) -> list[str]:
    """Extract and normalize all internal links from a page."""
    soup = BeautifulSoup(html, "lxml")
    base_domain = urlparse(base_url).netloc
    links = set()

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"].strip()
        # Skip anchors, mailto, javascript, etc.
        if href.startswith(("#", "mailto:", "javascript:", "tel:")):
            continue
        full_url = urljoin(base_url, href)
        parsed = urlparse(full_url)
        # Only keep same-domain links
        if parsed.netloc == base_domain:
            # Normalize: strip fragment, keep path
            clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            if clean.endswith("/"):
                clean = clean[:-1]
            links.add(clean)

    return sorted(links)


# ==========================================
# MULTI-SOURCE SCRAPING (REDDIT, NEWS, JOBS)
# ==========================================

async def fetch_reddit_data(competitor_name: str) -> str:
    """Search Reddit for the competitor and return formatted community sentiment."""
    if not competitor_name:
        return ""
    
    query = urllib.parse.quote(competitor_name)
    url = f"https://www.reddit.com/search.json?q={query}&sort=relevance&t=year&limit=10"
    
    client = await _get_client()
    try:
        resp = await client.get(url, timeout=10.0)
        if resp.status_code != 200:
            return ""
            
        data = resp.json()
        posts = data.get("data", {}).get("children", [])
        
        md_lines = [f"# Reddit Discussions about {competitor_name}"]
        for p in posts:
            post_data = p.get("data", {})
            title = post_data.get("title", "")
            selftext = post_data.get("selftext", "")[:300] # Limit selftext
            subreddit = post_data.get("subreddit_name_prefixed", "")
            score = post_data.get("score", 0)
            
            if title:
                md_lines.append(f"## {title} ({subreddit} - Score: {score})")
                if selftext:
                    md_lines.append(f"{selftext}...")
                md_lines.append("")
                
        return "\n".join(md_lines)
    except Exception as e:
        print(f"[SCRAPER] Reddit fetch failed: {e}")
        return ""


async def fetch_news_data(competitor_name: str) -> str:
    """Fetch recent news articles from Google News RSS."""
    if not competitor_name:
        return ""
        
    query = urllib.parse.quote(competitor_name)
    url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
    
    try:
        # feedparser uses sync urllib, but it's fast enough for RSS
        d = feedparser.parse(url)
        
        md_lines = [f"# Recent News for {competitor_name}"]
        # Take top 8 recent articles
        for entry in d.entries[:8]:
            title = entry.get("title", "")
            pub_date = entry.get("published", "")
            if title:
                # Basic cleaning of the source name often appended at the end e.g. " - TechCrunch"
                clean_title = title.split(" - ")[0] 
                md_lines.append(f"- **{clean_title}** ({pub_date})")
                
        return "\n".join(md_lines)
    except Exception as e:
        print(f"[SCRAPER] News fetch failed: {e}")
        return ""


async def fetch_jobs_data(competitor_name: str) -> str:
    """Fetch job postings to infer roadmap via Google RSS search on ATS platforms."""
    if not competitor_name:
        return ""
        
    # Search common ATS endpoints like lever/greenhouse/ashby
    q = f'(site:lever.co OR site:greenhouse.io OR site:boards.greenhouse.io OR site:jobs.ashbyhq.com) "{competitor_name}"'
    query = urllib.parse.quote(q)
    url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
    
    try:
        d = feedparser.parse(url)
        
        md_lines = [f"# Open Job Roles for {competitor_name}"]
        roles_found = 0
        
        for entry in d.entries[:10]:
            title = entry.get("title", "")
            # Clean up the ATS title e.g. "Senior Software Engineer - Stripe - Lever" -> "Senior Software Engineer"
            clean_title = title.split(" - ")[0].strip()
            
            if clean_title and "lever" not in clean_title.lower() and "greenhouse" not in clean_title.lower():
                md_lines.append(f"- {clean_title}")
                roles_found += 1
                
        if roles_found == 0:
            md_lines.append("- No specific job listings found on common ATS platforms.")
            
        return "\n".join(md_lines)
    except Exception as e:
        print(f"[SCRAPER] Jobs fetch failed: {e}")
        return ""
