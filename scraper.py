"""
scraper.py — Fetches war/conflict articles from reliable RSS sources.

Reduced to 6 working sources only:
  - Al Jazeera (working, war-focused)
  - BBC World (working, reliable)
  - NDTV Top Stories (working)
  - Indian Express World (working, India angle)
  - Middle East Eye (working, conflict-focused)
  - Defense One (working, military angle)

Removed (broken or too noisy):
  - Reuters → DNS failure in GitHub Actions
  - AP News → DNS failure
  - Times of Israel → 403 Forbidden
  - TRT World → 404 Not Found
  - Haaretz → 92 articles, mostly paywalled opinion
  - Indian Express → 127 articles, too many irrelevant
  - Hindustan Times → 403 Forbidden
  - Iran International → XML parse errors
  - i24 News → XML parse errors
  - LiveMint → low war relevance
  - The Hindu → low war relevance
  - Foreign Policy → low war relevance
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

MAX_ARTICLES = 25  # Hard cap — keeps Gemini prompt manageable

# ── Reliable RSS sources only ──────────────────────────────────────────────
RSS_SOURCES = [
    # Tier 1: Reliable wire/broadcast
    ("Al Jazeera",   "https://www.aljazeera.com/xml/rss/all.xml"),
    ("BBC",          "https://feeds.bbci.co.uk/news/world/middle_east/rss.xml"),
    ("BBC",          "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("NDTV",         "https://feeds.feedburner.com/ndtvnews-top-stories"),
    # Tier 2: Conflict/India focused
    ("Indian Express","https://indianexpress.com/section/world/feed/"),
    ("Middle East Eye","https://www.middleeasteye.net/rss"),
    ("Defense One",  "https://www.defenseone.com/rss/all/"),
]

# ── Keywords ───────────────────────────────────────────────────────────────
HIGH_WEIGHT_KEYWORDS = [
    "iran war", "us strike", "israel strike", "irgc", "idf strike",
    "nuclear deal", "strait of hormuz", "kharg island", "chabahar",
    "iranian missile", "iranian drone", "shahed", "ballistic missile",
    "khamenei", "netanyahu", "pentagon iran", "us iran", "israel iran",
]

MEDIUM_WEIGHT_KEYWORDS = [
    "iran", "israel", "hamas", "hezbollah", "gaza", "middle east",
    "nuclear", "idf", "pentagon", "missile", "drone", "netanyahu",
    "trump iran", "tehran", "tel aviv", "west bank",
    "ceasefire", "sanctions", "hormuz", "saudi arabia",
    "proxy", "warship", "airstrike", "retaliation", "escalation",
    "india iran", "india oil", "india gulf", "indian sailors",
    "brent crude", "oil price", "opec", "energy crisis",
]

UNSPLASH_PHOTO_IDS = {
    "oil":       "1474546499760-77a0b18c5e69",
    "drone":     "1585776245991-cf89dd7fc73a",
    "nuclear":   "1518709414768-a88981a4515d",
    "diplomacy": "1529107386315-e1a2ed48a1e3",
    "india":     "1582510003544-4d00b7f74220",
    "strike":    "1540575467063-178a50c2df87",
    "hormuz":    "1505118380757-91f5f5632de0",
    "ship":      "1566753323558-f4e0952af115",
    "iran":      "1604072366595-e75dc92d6bdc",
    "default":   "1579548122080-c35fd6820734",
}


def _get_relevance_score(title: str, desc: str) -> int:
    text = (title + " " + desc).lower()
    score = 0
    for kw in HIGH_WEIGHT_KEYWORDS:
        if kw in text:
            score += 3
    for kw in MEDIUM_WEIGHT_KEYWORDS:
        if kw in text:
            score += 1
    return score


def _get_unsplash_fallback(title: str) -> str:
    title_lower = title.lower()
    for key, photo_id in UNSPLASH_PHOTO_IDS.items():
        if key in title_lower:
            return f"https://images.unsplash.com/photo-{photo_id}?w=800&h=450&q=80&fit=crop"
    return f"https://images.unsplash.com/photo-{UNSPLASH_PHOTO_IDS['default']}?w=800&h=450&q=80&fit=crop"


def _proxy_image(url):
    if not url:
        return url
    if "unsplash.com" in url:
        return url
    from urllib.parse import quote
    clean = url.split("?")[0]
    return f"https://images.weserv.nl/?url={quote(clean, safe='')}&w=800&h=450&fit=cover&output=jpg"


def _extract_image_from_rss(item) -> str:
    for mc in item.findall("media:content", NAMESPACES):
        url = mc.get("url", "")
        if url and any(ext in url.lower() for ext in [".jpg", ".jpeg", ".png", ".webp"]):
            return url
    mg = item.find("media:group", NAMESPACES)
    if mg is not None:
        mc = mg.find("media:content", NAMESPACES)
        if mc is not None:
            url = mc.get("url", "")
            if url:
                return url
    mt = item.find("media:thumbnail", NAMESPACES)
    if mt is not None:
        url = mt.get("url", "")
        if url:
            return url
    enc = item.find("enclosure")
    if enc is not None and "image" in enc.get("type", ""):
        url = enc.get("url", "")
        if url:
            return url
    desc = item.findtext("description", "")
    if desc and "<img" in desc:
        m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', desc)
        if m:
            return m.group(1)
    return ""


def _fetch_og_image(url: str) -> str:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=12, verify=False)
        if resp.status_code != 200:
            return ""
        html = resp.text[:30000]
        patterns = [
            r'property=["\']og:image["\'][^>]*content=["\']([^"\']+)["\']',
            r'content=["\']([^"\']+)["\'][^>]*property=["\']og:image["\']',
        ]
        for pat in patterns:
            m = re.search(pat, html)
            if m:
                img = m.group(1)
                if img.startswith("http") and any(
                    ext in img.lower() for ext in [".jpg", ".jpeg", ".png", ".webp", "image"]
                ):
                    return img
    except Exception:
        pass
    return ""


def fetch_article_content(url: str) -> str:
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
                paragraphs = container.find_all("p")
                text = " ".join(
                    p.get_text(" ", strip=True) for p in paragraphs
                    if len(p.get_text(strip=True)) > 40
                )
                if len(text) > 200:
                    return text[:3000]
        paragraphs = soup.find_all("p")
        text = " ".join(
            p.get_text(" ", strip=True) for p in paragraphs
            if len(p.get_text(strip=True)) > 40
        )
        return text[:3000]
    except Exception as e:
        print(f"  [WARN] Content fetch failed for {url}: {e}")
        return ""


def _parse_feed(source_label: str, url: str, seen: set) -> list:
    results = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15, verify=False)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)

        for item in root.findall(".//item"):
            title = item.findtext("title", "").strip()
            link  = item.findtext("link", "").strip()
            desc  = item.findtext("description", "").strip()

            if not link:
                link_el = item.find("{http://www.w3.org/2005/Atom}link")
                if link_el is not None:
                    link = link_el.get("href", "").strip()

            if not link or link in seen or len(title) < 10:
                continue

            score = _get_relevance_score(title, desc)
            if score == 0:
                continue

            seen.add(link)
            image_url = _proxy_image(_extract_image_from_rss(item))

            results.append({
                "title":      title,
                "url":        link,
                "content":    desc,
                "source":     source_label,
                "imageUrl":   image_url,
                "score":      score,
                "fetched_at": datetime.utcnow().isoformat(),
            })

    except ET.ParseError as e:
        print(f"  [WARN] XML parse error for {source_label}: {e}")
    except requests.RequestException as e:
        print(f"  [ERROR] {source_label}: {e}")
    except Exception as e:
        print(f"  [ERROR] Unexpected for {source_label}: {e}")

    return results


def fetch_all_articles() -> list:
    articles = []
    seen = set()
    source_counts: dict = {}

    print(f"  Fetching RSS from {len(RSS_SOURCES)} sources...")
    for source_label, url in RSS_SOURCES:
        batch = _parse_feed(source_label, url, seen)
        if batch:
            source_counts[source_label] = source_counts.get(source_label, 0) + len(batch)
            articles.extend(batch)

    articles.sort(key=lambda a: a.get("score", 0), reverse=True)

    print(f"  Relevant articles found: {len(articles)}")
    for src, count in sorted(source_counts.items()):
        print(f"    {src}: {count}")

    # Hard cap — take only top MAX_ARTICLES by relevance score
    articles = articles[:MAX_ARTICLES]
    print(f"  Using top {len(articles)} articles (capped at {MAX_ARTICLES})")

    # Fetch og:image for top 8 missing images only
    missing = [a for a in articles if not a["imageUrl"]][:8]
    if missing:
        print(f"  Fetching og:image for {len(missing)} articles...")
        for art in missing:
            img = _fetch_og_image(art["url"])
            if img:
                art["imageUrl"] = _proxy_image(img)

    # Unsplash fallback
    for art in articles:
        if not art["imageUrl"]:
            art["imageUrl"] = _get_unsplash_fallback(art["title"])

    return articles


# Backwards-compatibility alias
def fetch_ndtv_articles() -> list:
    return fetch_all_articles()


if __name__ == "__main__":
    arts = fetch_all_articles()
    print(f"\nTotal returned: {len(arts)}")
    for a in arts[:10]:
        has_img = "✓ img" if a.get("imageUrl") else "✗"
        print(f"  [{a['source']}] score={a['score']} {has_img} {a['title'][:70]}")