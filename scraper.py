"""
scraper.py — Fetches war/conflict articles from RSS feeds.

Key design:
  - fetch_all_articles() always returns fresh articles from RSS
  - fetch_article_content() fetches full text for individual articles
  - No caching here — caching is bot.py's responsibility
"""

import re
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from bs4 import BeautifulSoup
import warnings

warnings.filterwarnings("ignore")

NAMESPACES = {
    "media":   "http://search.yahoo.com/mrss/",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "dc":      "http://purl.org/dc/elements/1.1/",
    "atom":    "http://www.w3.org/2005/Atom",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_ARTICLES = 30  # Max to pass to AI pipeline

# ── RSS sources ──────────────────────────────────────────────────────────────
RSS_SOURCES = [
    # Tier 1: Always reliable
    ("Al Jazeera",     "https://www.aljazeera.com/xml/rss/all.xml"),
    ("BBC",            "https://feeds.bbci.co.uk/news/world/middle_east/rss.xml"),
    ("BBC",            "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("Middle East Eye","https://www.middleeasteye.net/rss"),

    # Tier 2: India-focused
    ("NDTV",           "https://www.ndtv.com/rss/2.0/world-news"),
    ("Indian Express", "https://indianexpress.com/section/world/feed/"),
    ("The Hindu",      "https://www.thehindu.com/news/international/feeder/default.rss"),
    ("Times of India", "https://timesofindia.indiatimes.com/rssfeeds/296589292.cms"),

    # Tier 3: Global wire
    ("Reuters",        "https://feeds.reuters.com/reuters/worldNews"),
    ("Defense One",    "https://www.defenseone.com/rss/all/"),
    ("Jerusalem Post", "https://www.jpost.com/Rss/RssFeedsHeadlines.aspx"),
]

# ── Keyword scoring ──────────────────────────────────────────────────────────
HIGH_KEYWORDS = [
    "iran war", "us strike", "israel strike", "irgc", "idf strike",
    "strait of hormuz", "kharg island", "chabahar",
    "iranian missile", "iranian drone", "shahed", "ballistic missile",
    "khamenei", "netanyahu iran", "pentagon iran", "us iran", "israel iran",
    "operation midnight hammer", "operation epic fury",
]

MEDIUM_KEYWORDS = [
    "iran", "israel", "hamas", "hezbollah", "gaza", "middle east",
    "nuclear", "idf", "pentagon", "missile", "drone", "netanyahu",
    "trump iran", "tehran", "tel aviv", "west bank",
    "ceasefire", "sanctions", "hormuz", "saudi arabia",
    "proxy", "warship", "airstrike", "retaliation", "escalation",
    "india iran", "india oil", "india gulf", "indian sailors",
    "brent crude", "oil price", "opec", "energy crisis",
]

UNSPLASH_FALLBACKS = {
    "oil":       "1474546499760-77a0b18c5e69",
    "drone":     "1585776245991-cf89dd7fc73a",
    "nuclear":   "1518709414768-a88981a4515d",
    "diplomacy": "1529107386315-e1a2ed48a1e3",
    "india":     "1582510003544-4d00b7f74220",
    "strike":    "1540575467063-178a50c2df87",
    "hormuz":    "1505118380757-91f5f5632de0",
    "iran":      "1604072366595-e75dc92d6bdc",
    "default":   "1579548122080-c35fd6820734",
}


def _score(title: str, desc: str) -> int:
    text = (title + " " + desc).lower()
    score = 0
    for kw in HIGH_KEYWORDS:
        if kw in text:
            score += 3
    for kw in MEDIUM_KEYWORDS:
        if kw in text:
            score += 1
    return score


def _fallback_image(title: str) -> str:
    t = title.lower()
    for key, pid in UNSPLASH_FALLBACKS.items():
        if key in t:
            return f"https://images.unsplash.com/photo-{pid}?w=800&h=450&q=80&fit=crop"
    return f"https://images.unsplash.com/photo-{UNSPLASH_FALLBACKS['default']}?w=800&h=450&q=80&fit=crop"


def _proxy(url: str) -> str:
    if not url or "unsplash.com" in url:
        return url
    from urllib.parse import quote
    clean = url.split("?")[0]
    return f"https://images.weserv.nl/?url={quote(clean, safe='')}&w=800&h=450&fit=cover&output=jpg"


def _extract_rss_image(item) -> str:
    """Try several RSS image fields in order."""
    for mc in item.findall("media:content", NAMESPACES):
        url = mc.get("url", "")
        if url and any(x in url.lower() for x in [".jpg", ".jpeg", ".png", ".webp"]):
            return url
    mg = item.find("media:group", NAMESPACES)
    if mg is not None:
        mc = mg.find("media:content", NAMESPACES)
        if mc is not None and mc.get("url"):
            return mc.get("url")
    mt = item.find("media:thumbnail", NAMESPACES)
    if mt is not None and mt.get("url"):
        return mt.get("url")
    enc = item.find("enclosure")
    if enc is not None and "image" in enc.get("type", "") and enc.get("url"):
        return enc.get("url")
    # Try pulling from description HTML
    desc = item.findtext("description", "")
    if desc and "<img" in desc:
        m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', desc)
        if m:
            return m.group(1)
    return ""


def _parse_feed(source: str, url: str) -> list:
    """Fetch and parse a single RSS feed. Returns list of article dicts."""
    results = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15, verify=False)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)

        for item in root.findall(".//item"):
            title = item.findtext("title", "").strip()
            link  = item.findtext("link",  "").strip()
            desc  = item.findtext("description", "").strip()

            # Some feeds use atom:link
            if not link:
                al = item.find("{http://www.w3.org/2005/Atom}link")
                if al is not None:
                    link = al.get("href", "").strip()

            if not link or len(title) < 10:
                continue

            score = _score(title, desc)
            if score == 0:
                continue

            image = _proxy(_extract_rss_image(item))
            if not image:
                image = _fallback_image(title)

            results.append({
                "title":      title,
                "url":        link,
                "content":    "",        # filled later by fetch_article_content
                "source":     source,
                "imageUrl":   image,
                "score":      score,
                "fetched_at": datetime.utcnow().isoformat(),
            })

    except ET.ParseError as e:
        print(f"  [WARN] XML error {source}: {e}")
    except requests.RequestException as e:
        print(f"  [ERROR] {source}: {e}")
    except Exception as e:
        print(f"  [ERROR] Unexpected {source}: {e}")

    return results


def fetch_article_content(url: str) -> str:
    """Fetch and extract main text from an article URL."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15, verify=False)
        if resp.status_code != 200:
            return ""
        soup = BeautifulSoup(resp.text, "lxml")
        for tag in soup(["script", "style", "nav", "header", "footer",
                         "aside", "figure", "figcaption", "noscript"]):
            tag.decompose()
        selectors = [
            "article", ".article-body", ".story-body", ".post-content",
            ".article__body", ".article-text", ".story-content",
            "#article-body", "#story-body", ".entry-content",
        ]
        for sel in selectors:
            container = soup.select_one(sel)
            if container:
                paras = container.find_all("p")
                text = " ".join(
                    p.get_text(" ", strip=True) for p in paras
                    if len(p.get_text(strip=True)) > 40
                )
                if len(text) > 200:
                    return text[:3000]
        paras = soup.find_all("p")
        text = " ".join(
            p.get_text(" ", strip=True) for p in paras
            if len(p.get_text(strip=True)) > 40
        )
        return text[:3000]
    except Exception as e:
        print(f"  [WARN] Content fetch failed {url}: {e}")
        return ""


def fetch_all_articles() -> list:
    """
    Fetch all relevant articles from all RSS feeds.
    Returns deduplicated list sorted by relevance score.
    Does NOT filter by seen cache — that's bot.py's job.
    """
    all_articles = []
    seen_urls = set()
    source_counts = {}

    print(f"  Fetching from {len(RSS_SOURCES)} RSS sources...")

    for source, url in RSS_SOURCES:
        batch = _parse_feed(source, url)
        new_batch = []
        for art in batch:
            if art["url"] not in seen_urls:
                seen_urls.add(art["url"])
                new_batch.append(art)
        if new_batch:
            source_counts[source] = source_counts.get(source, 0) + len(new_batch)
            all_articles.extend(new_batch)

    all_articles.sort(key=lambda a: a.get("score", 0), reverse=True)

    print(f"  Total relevant articles: {len(all_articles)}")
    for src, count in sorted(source_counts.items(), key=lambda x: -x[1]):
        print(f"    {src}: {count}")

    # Cap at MAX_ARTICLES
    return all_articles[:MAX_ARTICLES]
