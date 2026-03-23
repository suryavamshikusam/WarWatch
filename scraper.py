"""
scraper.py — Bulletproof RSS fetcher with parallel fetching + article cache.

Improvements over original:
  - ThreadPoolExecutor: all sources fetched in parallel, not sequentially
  - Per-source 12s hard timeout — one slow source never blocks others
  - Article cache: if ALL sources fail, serves last good scrape
  - og:image fetch is parallel and capped at 5 with 6s timeout
  - Never returns empty list if cache exists
"""

import re, json, warnings
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeout
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

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
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_ARTICLES   = 25
CACHE_FILE     = Path("cache/articles.json")
SOURCE_TIMEOUT = 12   # seconds per RSS source
IMAGE_TIMEOUT  = 6    # seconds per og:image fetch

RSS_SOURCES = [
    ("Al Jazeera",    "https://www.aljazeera.com/xml/rss/all.xml"),
    ("BBC",           "https://feeds.bbci.co.uk/news/world/middle_east/rss.xml"),
    ("BBC",           "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("NDTV",          "https://feeds.feedburner.com/ndtvnews-top-stories"),
    ("Indian Express","https://indianexpress.com/section/world/feed/"),
    ("Middle East Eye","https://www.middleeasteye.net/rss"),
    ("Defense One",   "https://www.defenseone.com/rss/all/"),
]

HIGH_WEIGHT_KEYWORDS = [
    "iran war","us strike","israel strike","irgc","idf strike",
    "nuclear deal","strait of hormuz","kharg island","chabahar",
    "iranian missile","iranian drone","shahed","ballistic missile",
    "khamenei","netanyahu","pentagon iran","us iran","israel iran",
]

MEDIUM_WEIGHT_KEYWORDS = [
    "iran","israel","hamas","hezbollah","gaza","middle east",
    "nuclear","idf","pentagon","missile","drone","netanyahu",
    "trump iran","tehran","tel aviv","west bank",
    "ceasefire","sanctions","hormuz","saudi arabia",
    "proxy","warship","airstrike","retaliation","escalation",
    "india iran","india oil","india gulf","indian sailors",
    "brent crude","oil price","opec","energy crisis",
]

UNSPLASH_FALLBACKS = {
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


# ── Helpers ───────────────────────────────────────────────────────────────────

def _score(title: str, desc: str) -> int:
    text = (title + " " + desc).lower()
    s = 0
    for kw in HIGH_WEIGHT_KEYWORDS:
        if kw in text: s += 3
    for kw in MEDIUM_WEIGHT_KEYWORDS:
        if kw in text: s += 1
    return s


def _unsplash(title: str) -> str:
    tl = title.lower()
    for key, pid in UNSPLASH_FALLBACKS.items():
        if key in tl:
            return f"https://images.unsplash.com/photo-{pid}?w=800&h=450&q=80&fit=crop"
    return f"https://images.unsplash.com/photo-{UNSPLASH_FALLBACKS['default']}?w=800&h=450&q=80&fit=crop"


def _proxy_image(url: str) -> str:
    if not url: return url
    if "unsplash.com" in url: return url
    clean = url.split("?")[0]
    return f"https://images.weserv.nl/?url={quote(clean, safe='')}&w=800&h=450&fit=cover&output=jpg"


def _extract_rss_image(item) -> str:
    for mc in item.findall("media:content", NAMESPACES):
        url = mc.get("url","")
        if url and any(e in url.lower() for e in [".jpg",".jpeg",".png",".webp"]):
            return url
    mg = item.find("media:group", NAMESPACES)
    if mg is not None:
        mc = mg.find("media:content", NAMESPACES)
        if mc is not None and mc.get("url"):
            return mc.get("url")
    mt = item.find("media:thumbnail", NAMESPACES)
    if mt is not None and mt.get("url"):
        return mt.get("url","")
    enc = item.find("enclosure")
    if enc is not None and "image" in enc.get("type",""):
        return enc.get("url","")
    desc = item.findtext("description","")
    if desc and "<img" in desc:
        m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', desc)
        if m: return m.group(1)
    return ""


def _fetch_og_image(url: str) -> str:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=IMAGE_TIMEOUT, verify=False)
        if resp.status_code != 200: return ""
        html = resp.text[:30000]
        for pat in [
            r'property=["\']og:image["\'][^>]*content=["\']([^"\']+)["\']',
            r'content=["\']([^"\']+)["\'][^>]*property=["\']og:image["\']',
        ]:
            m = re.search(pat, html)
            if m:
                img = m.group(1)
                if img.startswith("http") and any(
                    e in img.lower() for e in [".jpg",".jpeg",".png",".webp","image"]
                ):
                    return img
    except Exception:
        pass
    return ""


def fetch_article_content(url: str) -> str:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15, verify=False)
        if resp.status_code != 200: return ""
        soup = BeautifulSoup(resp.text, "lxml")
        for tag in soup(["script","style","nav","header","footer",
                          "aside","figure","figcaption","noscript"]):
            tag.decompose()
        for sel in [
            "article",".article-body",".story-body",".post-content",
            ".article__body",".article-text",".story-content",
            "#article-body","#story-body",".entry-content",
        ]:
            container = soup.select_one(sel)
            if container:
                paras = container.find_all("p")
                text  = " ".join(
                    p.get_text(" ",strip=True) for p in paras
                    if len(p.get_text(strip=True)) > 40
                )
                if len(text) > 200:
                    return text[:3000]
        paras = soup.find_all("p")
        text  = " ".join(p.get_text(" ",strip=True) for p in paras if len(p.get_text(strip=True)) > 40)
        return text[:3000]
    except Exception as e:
        print(f"  [WARN] Content fetch failed for {url}: {e}")
        return ""


# ── Per-source fetcher (runs in thread) ───────────────────────────────────────

def _fetch_source(source_label: str, url: str, seen: set) -> list:
    results = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=SOURCE_TIMEOUT, verify=False)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)

        for item in root.findall(".//item"):
            title = item.findtext("title","").strip()
            link  = item.findtext("link","").strip()
            desc  = item.findtext("description","").strip()

            if not link:
                link_el = item.find("{http://www.w3.org/2005/Atom}link")
                if link_el is not None:
                    link = link_el.get("href","").strip()

            if not link or link in seen or len(title) < 10:
                continue

            s = _score(title, desc)
            if s == 0:
                continue

            seen.add(link)
            results.append({
                "title":      title,
                "url":        link,
                "content":    desc,
                "source":     source_label,
                "imageUrl":   _proxy_image(_extract_rss_image(item)),
                "score":      s,
                "fetched_at": datetime.utcnow().isoformat(),
            })

    except ET.ParseError as e:
        print(f"  [WARN] XML parse error {source_label}: {e}")
    except requests.RequestException as e:
        print(f"  [WARN] Request failed {source_label}: {e}")
    except Exception as e:
        print(f"  [WARN] Unexpected error {source_label}: {e}")

    return results


# ── Cache helpers ─────────────────────────────────────────────────────────────

def _save_cache(articles: list):
    try:
        CACHE_FILE.parent.mkdir(exist_ok=True)
        CACHE_FILE.write_text(json.dumps(articles, indent=2))
    except Exception as e:
        print(f"  [WARN] Cache save failed: {e}")


def _load_cache() -> list:
    try:
        if CACHE_FILE.exists():
            data = json.loads(CACHE_FILE.read_text())
            print(f"  [INFO] Loaded {len(data)} articles from cache")
            return data
    except Exception as e:
        print(f"  [WARN] Cache load failed: {e}")
    return []


# ── Main fetch ────────────────────────────────────────────────────────────────

def fetch_all_articles() -> list:
    """
    Fetch all RSS sources in parallel. Falls back to cache if all fail.
    Never returns empty list if cache exists.
    """
    articles: list = []
    seen:     set  = set()
    source_counts: dict = {}

    print(f"  Fetching {len(RSS_SOURCES)} RSS sources in parallel...")

    # Parallel fetch — each source in its own thread
    with ThreadPoolExecutor(max_workers=len(RSS_SOURCES)) as executor:
        futures = {
            executor.submit(_fetch_source, label, url, seen): label
            for label, url in RSS_SOURCES
        }
        for future in as_completed(futures, timeout=20):
            label = futures[future]
            try:
                batch = future.result(timeout=1)
                if batch:
                    source_counts[label] = source_counts.get(label, 0) + len(batch)
                    articles.extend(batch)
            except FuturesTimeout:
                print(f"  [WARN] {label} timed out")
            except Exception as e:
                print(f"  [WARN] {label} future error: {e}")

    articles.sort(key=lambda a: a.get("score", 0), reverse=True)

    print(f"  Relevant articles: {len(articles)}")
    for src, cnt in sorted(source_counts.items()):
        print(f"    {src}: {cnt}")

    # If scraper got nothing, fall back to cache
    if not articles:
        print("  [WARN] All sources returned 0 articles — loading from cache")
        return _load_cache()

    # Save good scrape to cache
    articles = articles[:MAX_ARTICLES]
    _save_cache(articles)

    # Parallel og:image fetch for top 5 missing images
    missing = [a for a in articles if not a["imageUrl"]][:5]
    if missing:
        print(f"  Fetching og:image for {len(missing)} articles in parallel...")
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(_fetch_og_image, a["url"]): a for a in missing}
            for future in as_completed(futures, timeout=15):
                art = futures[future]
                try:
                    img = future.result(timeout=1)
                    if img:
                        art["imageUrl"] = _proxy_image(img)
                except Exception:
                    pass

    # Unsplash fallback for anything still missing
    for art in articles:
        if not art["imageUrl"]:
            art["imageUrl"] = _unsplash(art["title"])

    print(f"  Using top {len(articles)} articles (capped at {MAX_ARTICLES})")
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
