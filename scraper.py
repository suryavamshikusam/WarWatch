"""
scraper.py — Fetches war/conflict articles from multiple news sources via RSS.

Sources:
  - NDTV          (India)
  - BBC            (UK)
  - Iran International (Iran-focused, English)
  - TRT World      (Turkey, English)
  - i24 News       (Israel, English)
  - The Hindu      (India, international desk)
"""

import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import warnings

# Suppress SSL warnings (keep verify=False for compatibility)
warnings.filterwarnings("ignore")

KEYWORDS = [
    "iran", "israel", "hamas", "hezbollah", "gaza",
    "middle east", "nuclear", "idf", "pentagon",
    "missile", "drone", "netanyahu", "trump iran", "us strike",
    "tehran", "tel aviv", "khamenei", "irgc", "strait of hormuz",
    "west bank", "rafah", "ceasefire", "sanctions", "kharg"
]

# Each entry: (source_label, rss_url)
RSS_SOURCES = [
    # NDTV
    ("NDTV",             "https://feeds.feedburner.com/ndtvnews-world-news"),
    ("NDTV",             "https://feeds.feedburner.com/ndtvnews-top-stories"),
    ("NDTV",             "https://www.ndtv.com/rss/world"),

    # BBC
    ("BBC",              "https://feeds.bbci.co.uk/news/world/middle_east/rss.xml"),
    ("BBC",              "https://feeds.bbci.co.uk/news/world/rss.xml"),

    # Iran International
    ("Iran International", "https://www.iranintl.com/en/rss"),

    # TRT World
    ("TRT World",        "https://www.trtworld.com/rss"),
    ("TRT World",        "https://www.trtworld.com/rss/middle-east"),

    # i24 News  (no official RSS; we use their sitemap-based feed)
    ("i24 News",         "https://www.i24news.tv/en/rss"),

    # The Hindu — International section
    ("The Hindu",        "https://www.thehindu.com/news/international/feeder/default.rss"),
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}

# How many articles to return in total across all sources
MAX_ARTICLES = 30


def is_relevant(text: str) -> bool:
    return any(kw in text.lower() for kw in KEYWORDS)


def _parse_feed(source_label: str, url: str, seen: set) -> list:
    """Fetch one RSS feed and return a list of relevant article dicts."""
    results = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15, verify=False)
        resp.raise_for_status()

        # Some feeds use encoding declarations that confuse ET — strip BOM/xml decl
        content = resp.content
        root = ET.fromstring(content)

        for item in root.findall(".//item"):
            title = item.findtext("title", "").strip()
            link  = item.findtext("link", "").strip()
            desc  = item.findtext("description", "").strip()

            # Atom-style feeds sometimes use <id> instead of <link>
            if not link:
                link = item.findtext("{http://www.w3.org/2005/Atom}link", "").strip()

            if not link or link in seen or len(title) < 10:
                continue

            if is_relevant(title) or is_relevant(desc):
                seen.add(link)
                results.append({
                    "title":      title,
                    "url":        link,
                    "content":    desc,
                    "source":     source_label,
                    "fetched_at": datetime.utcnow().isoformat(),
                })

    except ET.ParseError as e:
        print(f"  [WARN] XML parse error for {source_label} ({url}): {e}")
    except requests.RequestException as e:
        print(f"  [ERROR] {source_label} ({url}): {e}")
    except Exception as e:
        print(f"  [ERROR] Unexpected error for {source_label} ({url}): {e}")

    return results


def fetch_all_articles() -> list:
    """
    Main entry point.
    Fetches articles from all configured RSS sources, deduplicates by URL,
    and returns up to MAX_ARTICLES relevant items.
    """
    articles = []
    seen     = set()
    source_counts: dict = {}

    for source_label, url in RSS_SOURCES:
        batch = _parse_feed(source_label, url, seen)
        if batch:
            source_counts[source_label] = source_counts.get(source_label, 0) + len(batch)
            articles.extend(batch)

    # Print a per-source summary
    print(f"  Total relevant articles found: {len(articles)}")
    for src, count in sorted(source_counts.items()):
        print(f"    {src}: {count}")

    return articles[:MAX_ARTICLES]


# ── Backwards-compatibility alias (bot.py calls fetch_ndtv_articles) ────────
def fetch_ndtv_articles() -> list:
    """
    Legacy name kept so bot.py works without changes.
    Now actually fetches from ALL configured sources.
    """
    return fetch_all_articles()


def fetch_article_content(url: str) -> str:
    """
    Optionally fetch the full article body.
    Currently returns empty string to keep things fast;
    the RSS description is usually enough for summarisation.
    Uncomment the block below to enable full-text fetch via BeautifulSoup.
    """
    return ""

    # ── Full-text fetch (optional, slower) ──────────────────────────────────
    # try:
    #     from bs4 import BeautifulSoup
    #     resp = requests.get(url, headers=HEADERS, timeout=15, verify=False)
    #     soup = BeautifulSoup(resp.text, "lxml")
    #     paragraphs = soup.find_all("p")
    #     text = " ".join(p.get_text(" ", strip=True) for p in paragraphs[:20])
    #     return text[:2000]
    # except Exception as e:
    #     print(f"  [WARN] Content fetch failed for {url}: {e}")
    #     return ""


if __name__ == "__main__":
    arts = fetch_all_articles()
    print(f"\nTotal returned: {len(arts)}")
    for a in arts[:10]:
        print(f"  [{a['source']}] {a['title']}")