"""
scraper.py — Fetches war/conflict articles from 17 news sources via RSS.
Extracts real article images via og:image, media:content, and Unsplash fallback.
Returns articles sorted by relevance score with full article content.

Sources (4 tiers):
  Tier 1 — Wire services:    Reuters, AP News, Al Jazeera, BBC, NDTV
  Tier 2 — Conflict-focused: Times of Israel, Middle East Eye, Haaretz,
                              Iran International, TRT World, i24 News
  Tier 3 — India angle:      Indian Express, LiveMint, Hindustan Times, The Hindu
  Tier 4 — Policy/Military:  Foreign Policy, Defense One
"""

import re
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from bs4 import BeautifulSoup
import warnings

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# XML namespaces
# ---------------------------------------------------------------------------
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

MAX_ARTICLES = 40

# ---------------------------------------------------------------------------
# RSS sources — (label, url)
# ---------------------------------------------------------------------------
RSS_SOURCES = [
    # Tier 1: Wire services
    ("NDTV",              "https://feeds.feedburner.com/ndtvnews-world-news"),
    ("NDTV",              "https://feeds.feedburner.com/ndtvnews-top-stories"),
    ("NDTV",              "https://www.ndtv.com/rss/world"),
    ("BBC",               "https://feeds.bbci.co.uk/news/world/middle_east/rss.xml"),
    ("BBC",               "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("Reuters",           "https://feeds.reuters.com/reuters/worldNews"),
    ("Reuters",           "https://feeds.reuters.com/reuters/topNews"),
    ("AP News",           "https://feeds.apnews.com/rss/apf-worldnews"),
    ("Al Jazeera",        "https://www.aljazeera.com/xml/rss/all.xml"),
    ("Al Jazeera",        "https://www.aljazeera.com/xml/rss/middle-east.xml"),
    # Tier 2: Conflict-focused
    ("Times of Israel",   "https://www.timesofisrael.com/feed"),
    ("Middle East Eye",   "https://www.middleeasteye.net/rss"),
    ("Haaretz",           "https://www.haaretz.com/srv/haaretz-latest-headlines"),
    ("Iran International","https://www.iranintl.com/en/rss"),
    ("TRT World",         "https://www.trtworld.com/rss"),
    ("TRT World",         "https://www.trtworld.com/rss/middle-east"),
    ("i24 News",          "https://www.i24news.tv/en/rss"),
    # Tier 3: India angle
    ("Indian Express",    "https://indianexpress.com/section/world/feed/"),
    ("LiveMint",          "https://www.livemint.com/rss/news"),
    ("Hindustan Times",   "https://www.hindustantimes.com/feeds/rss/world-news/rssfeed.xml"),
    ("The Hindu",         "https://www.thehindu.com/news/international/feeder/default.rss"),
    # Tier 4: Policy/Military
    ("Foreign Policy",    "https://foreignpolicy.com/feed/"),
    ("Defense One",       "https://www.defenseone.com/rss/all/"),
]

# ---------------------------------------------------------------------------
# Keywords and scoring
# ---------------------------------------------------------------------------
HIGH_WEIGHT_KEYWORDS = [
    "iran war", "us strike", "israel strike", "irgc", "idf strike",
    "nuclear deal", "strait of hormuz", "kharg island", "chabahar",
    "iranian missile", "iranian drone", "shahed", "ballistic missile",
    "khamenei", "netanyahu", "pentagon iran", "us iran", "israel iran",
]

MEDIUM_WEIGHT_KEYWORDS = [
    "iran", "israel", "hamas", "hezbollah", "gaza", "middle east",
    "nuclear", "idf", "pentagon", "missile", "drone", "netanyahu",
    "trump iran", "tehran", "tel aviv", "west bank", "rafah",
    "ceasefire", "sanctions", "hormuz", "saudi arabia",
    "proxy", "warship", "airstrike", "retaliation", "escalation",
    "india iran", "india oil", "india gulf", "indian sailors", "indian diaspora",
    "brent crude", "oil price", "opec", "energy crisis",
]

# Unsplash direct CDN fallback (source.unsplash.com redirect API is dead — use photo IDs)
UNSPLASH_PHOTO_IDS = {
    "oil":       "1474546499760-77a0b18c5e69",
    "drone":     "1585776245991-cf89dd7fc73a",
    "missile":   "1614728263952-84ea256f9d1d",
    "nuclear":   "1518709414768-a88981a4515d",
    "diplomacy": "1529107386315-e1a2ed48a1e3",
    "india":     "1582510003544-4d00b7f74220",
    "ceasefire": "1541872703-74c5e44368f9",
    "strike":    "1540575467063-178a50c2df87",
    "hormuz":    "1505118380757-91f5f5632de0",
    "ship":      "1566753323558-f4e0952af115",
    "dubai":     "1512453979798-5ea266f8880c",
    "iran":      "1604072366595-e75dc92d6bdc",
    "default":   "1579548122080-c35fd6820734",
}


def _get_relevance_score(title: str, desc: str) -> int:
    """Score an article by keyword relevance. Higher = more relevant."""
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
    """Pick a topically-matched Unsplash direct CDN URL as fallback image."""
    title_lower = title.lower()
    for key, photo_id in UNSPLASH_PHOTO_IDS.items():
        if key in title_lower:
            return f"https://images.unsplash.com/photo-{photo_id}?w=800&h=450&q=80&fit=crop"
    return f"https://images.unsplash.com/photo-{UNSPLASH_PHOTO_IDS['default']}?w=800&h=450&q=80&fit=crop"


def _extract_image_from_rss(item) -> str:
    """Try all known RSS image patterns. Returns best URL or empty string."""

    # 1. <media:content url="...">
    for mc in item.findall("media:content", NAMESPACES):
        url = mc.get("url", "")
        if url and any(ext in url.lower() for ext in [".jpg", ".jpeg", ".png", ".webp"]):
            return url

    # 2. <media:group><media:content>
    mg = item.find("media:group", NAMESPACES)
    if mg is not None:
        mc = mg.find("media:content", NAMESPACES)
        if mc is not None:
            url = mc.get("url", "")
            if url:
                return url

    # 3. <media:thumbnail url="...">
    mt = item.find("media:thumbnail", NAMESPACES)
    if mt is not None:
        url = mt.get("url", "")
        if url:
            return url

    # 4. <enclosure>
    enc = item.find("enclosure")
    if enc is not None and "image" in enc.get("type", ""):
        url = enc.get("url", "")
        if url:
            return url

    # 5. <img> inside <description>
    desc = item.findtext("description", "")
    if desc and "<img" in desc:
        m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', desc)
        if m:
            return m.group(1)

    # 6. <content:encoded>
    encoded = item.findtext("content:encoded", "", NAMESPACES)
    if encoded and "<img" in encoded:
        m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', encoded)
        if m:
            return m.group(1)

    return ""


def _fetch_og_image(url: str) -> str:
    """Fetch article page and extract og:image or twitter:image."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=12, verify=False)
        if resp.status_code != 200:
            return ""
        html = resp.text[:30000]
        patterns = [
            r'property=["\']og:image["\'][^>]*content=["\']([^"\']+)["\']',
            r'content=["\']([^"\']+)["\'][^>]*property=["\']og:image["\']',
            r'name=["\']twitter:image["\'][^>]*content=["\']([^"\']+)["\']',
            r'content=["\']([^"\']+)["\'][^>]*name=["\']twitter:image["\']',
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
    """
    Fetch full article body text (up to 3000 chars).
    Used by summarizer.py to give the AI more context per article.
    """
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15, verify=False)
        if resp.status_code != 200:
            return ""

        soup = BeautifulSoup(resp.text, "lxml")

        # Remove noise elements
        for tag in soup(["script", "style", "nav", "header", "footer",
                          "aside", "figure", "figcaption", "noscript"]):
            tag.decompose()

        # Try article-specific containers
        selectors = [
            "article", ".article-body", ".story-body", ".post-content",
            ".article__body", ".article-text", ".story-content",
            "#article-body", "#story-body", ".news-body",
            '[itemprop="articleBody"]', ".entry-content",
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

        # Fallback: all <p> tags
        paragraphs = soup.find_all("p")
        text = " ".join(
            p.get_text(" ", strip=True) for p in paragraphs
            if len(p.get_text(strip=True)) > 40
        )
        return text[:3000]

    except Exception as e:
        print(f"  [WARN] Content fetch failed for {url}: {e}")
        return ""


def is_relevant(text: str) -> bool:
    return _get_relevance_score(text, "") > 0


def _parse_feed(source_label: str, url: str, seen: set) -> list:
    """Fetch one RSS feed and return relevant article dicts."""
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
            image_url = _extract_image_from_rss(item)

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
        print(f"  [WARN] XML parse error for {source_label} ({url}): {e}")
    except requests.RequestException as e:
        print(f"  [ERROR] {source_label} ({url}): {e}")
    except Exception as e:
        print(f"  [ERROR] Unexpected for {source_label} ({url}): {e}")

    return results


def fetch_all_articles() -> list:
    """
    Main entry point.
    1. Fetches all RSS sources and scores by relevance
    2. Sorts best articles to top
    3. Fetches og:image for top 15 articles missing images
    4. Applies Unsplash fallback for any still-missing images
    5. Returns up to MAX_ARTICLES articles
    """
    articles = []
    seen = set()
    source_counts: dict = {}

    print("  Fetching RSS feeds from 17 sources...")
    for source_label, url in RSS_SOURCES:
        batch = _parse_feed(source_label, url, seen)
        if batch:
            source_counts[source_label] = source_counts.get(source_label, 0) + len(batch)
            articles.extend(batch)

    # Sort by relevance score descending
    articles.sort(key=lambda a: a.get("score", 0), reverse=True)

    print(f"  Total relevant articles found: {len(articles)}")
    for src, count in sorted(source_counts.items()):
        print(f"    {src}: {count}")

    # Trim before expensive og: fetches
    articles = articles[:MAX_ARTICLES]

    # Fetch og:image for articles still missing images (top 15 only)
    missing = [a for a in articles if not a["imageUrl"]][:15]
    if missing:
        print(f"  Fetching og:image for {len(missing)} articles...")
        for art in missing:
            img = _fetch_og_image(art["url"])
            if img:
                art["imageUrl"] = img
                print(f"    ✓ {art['source']}: {art['title'][:50]}")

    # Unsplash fallback for any still missing
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