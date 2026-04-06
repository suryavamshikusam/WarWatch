"""
scraper.py — Fetches war/conflict articles from RSS feeds.
No AI. Rule-based categorisation only.
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

MAX_ARTICLES = 40

RSS_SOURCES = [
    ("Al Jazeera",     "https://www.aljazeera.com/xml/rss/all.xml"),
    ("BBC",            "https://feeds.bbci.co.uk/news/world/middle_east/rss.xml"),
    ("BBC",            "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("Middle East Eye","https://www.middleeasteye.net/rss"),
    ("NDTV",           "https://www.ndtv.com/rss/2.0/world-news"),
    ("Indian Express", "https://indianexpress.com/section/world/feed/"),
    ("The Hindu",      "https://www.thehindu.com/news/international/feeder/default.rss"),
    ("Times of India", "https://timesofindia.indiatimes.com/rssfeeds/296589292.cms"),
    ("Reuters",        "https://feeds.reuters.com/reuters/worldNews"),
    ("Defense One",    "https://www.defenseone.com/rss/all/"),
    ("Jerusalem Post", "https://www.jpost.com/Rss/RssFeedsHeadlines.aspx"),
]

# ── Category rules — first match wins ────────────────────────────────────────
CATEGORY_RULES = [
    ("india", [
        "india", "indian", "modi", "chabahar", "rupee", " inr",
        "diaspora", "gulf indian", "mea india", "new delhi",
        "indian navy", "indian oil", "ioc ", "ongc", "indian express",
        "ndtv", "times of india", "the hindu",
    ]),
    ("markets", [
        "oil price", "brent", "crude oil", "opec", "petrol price",
        "fuel price", "gold price", "stock market", "economy",
        "energy crisis", "shipping lane", "inflation",
    ]),
    ("diplomacy", [
        "ceasefire", "peace talks", "negotiat", "diplomatic",
        "deal", "agreement", "united nations", "un security council",
        "qatar mediat", "oman mediat", "pakistan mediat",
        "back-channel", "envoy", "sanction",
    ]),
    ("wider_war", [
        "houthi", "red sea", "hezbollah", "lebanon attack",
        "baghdad attack", "iraq attack", "russia warns",
        "china warns", "nato", "saudi attack", "uae attack",
        "bahrain attack", "kuwait attack", "sleeper cell",
    ]),
    ("military", [
        "airstrike", "air strike", "bomber", "f-35", "aircraft carrier",
        "idf strike", "irgc attack", "missile defense", "iron dome",
        "b-2 ", "b-1b", "warship", "ground troops", "pentagon says",
        "operation midnight", "operation epic", "military operation",
        "defense one",
    ]),
    ("war", [
        "iran", "israel", "strike", "attack", "missile", "drone",
        "nuclear", "hormuz", "tehran", "tel aviv", "war", "conflict",
        "explosion", "killed", "bombed", "hamas", "gaza",
    ]),
]

HIGH_KEYWORDS = [
    "iran war", "us strike iran", "israel strike iran", "irgc attack",
    "strait of hormuz", "kharg island", "chabahar strike",
    "iranian missile", "iranian drone", "khamenei",
    "operation midnight hammer", "operation epic fury",
]

MEDIUM_KEYWORDS = [
    "iran", "israel", "hamas", "hezbollah", "gaza", "middle east",
    "nuclear", "idf", "pentagon", "missile", "drone", "netanyahu",
    "trump iran", "tehran", "tel aviv", "ceasefire", "hormuz",
    "india iran", "india oil", "brent crude", "oil price",
]

UNSPLASH = {
    "oil":     "1474546499760-77a0b18c5e69",
    "drone":   "1585776245991-cf89dd7fc73a",
    "nuclear": "1518709414768-a88981a4515d",
    "india":   "1582510003544-4d00b7f74220",
    "iran":    "1604072366595-e75dc92d6bdc",
    "default": "1579548122080-c35fd6820734",
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


def _categorise(title: str, desc: str, source: str) -> str:
    text = (title + " " + desc + " " + source).lower()
    for category, keywords in CATEGORY_RULES:
        for kw in keywords:
            if kw in text:
                return category
    return "war"


def _fallback_image(title: str) -> str:
    t = title.lower()
    for key, pid in UNSPLASH.items():
        if key in t:
            return f"https://images.unsplash.com/photo-{pid}?w=800&h=450&q=80&fit=crop"
    return f"https://images.unsplash.com/photo-{UNSPLASH['default']}?w=800&h=450&q=80&fit=crop"


def _proxy(url: str) -> str:
    if not url or "unsplash.com" in url:
        return url
    from urllib.parse import quote
    clean = url.split("?")[0]
    return f"https://images.weserv.nl/?url={quote(clean, safe='')}&w=800&h=450&fit=cover&output=jpg"


def _extract_rss_image(item) -> str:
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
    desc = item.findtext("description", "")
    if desc and "<img" in desc:
        m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', desc)
        if m:
            return m.group(1)
    return ""


def _clean_desc(raw: str) -> str:
    if not raw:
        return ""
    clean = re.sub(r"<[^>]+>", " ", raw)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean[:300]


def _parse_feed(source: str, url: str) -> list:
    results = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15, verify=False)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)

        for item in root.findall(".//item"):
            title = item.findtext("title", "").strip()
            link  = item.findtext("link",  "").strip()
            desc  = item.findtext("description", "").strip()

            if not link:
                al = item.find("{http://www.w3.org/2005/Atom}link")
                if al is not None:
                    link = al.get("href", "").strip()

            if not link or len(title) < 10:
                continue

            score = _score(title, desc)
            if score == 0:
                continue

            results.append({
                "title":      title,
                "url":        link,
                "summary":    _clean_desc(desc),
                "source":     source,
                "imageUrl":   _proxy(_extract_rss_image(item)) or _fallback_image(title),
                "score":      score,
                "type":       _categorise(title, desc, source),
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
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15, verify=False)
        if resp.status_code != 200:
            return ""
        soup = BeautifulSoup(resp.text, "lxml")
        for tag in soup(["script","style","nav","header","footer","aside","figure","noscript"]):
            tag.decompose()
        for sel in ["article",".article-body",".story-body",".post-content","#article-body",".entry-content"]:
            container = soup.select_one(sel)
            if container:
                paras = container.find_all("p")
                text = " ".join(p.get_text(" ", strip=True) for p in paras if len(p.get_text(strip=True)) > 40)
                if len(text) > 200:
                    return text[:2000]
        paras = soup.find_all("p")
        return " ".join(p.get_text(" ", strip=True) for p in paras if len(p.get_text(strip=True)) > 40)[:2000]
    except Exception:
        return ""


def fetch_all_articles() -> list:
    all_articles = []
    seen_urls = set()
    source_counts = {}

    print(f"  Fetching from {len(RSS_SOURCES)} RSS sources...")
    for source, url in RSS_SOURCES:
        for art in _parse_feed(source, url):
            if art["url"] not in seen_urls:
                seen_urls.add(art["url"])
                source_counts[source] = source_counts.get(source, 0) + 1
                all_articles.append(art)

    all_articles.sort(key=lambda a: a.get("score", 0), reverse=True)

    cats = {}
    for a in all_articles:
        cats[a["type"]] = cats.get(a["type"], 0) + 1

    print(f"  Total relevant: {len(all_articles)}")
    for src, c in sorted(source_counts.items(), key=lambda x: -x[1]):
        print(f"    {src}: {c}")
    print(f"  Categories: {cats}")

    return all_articles[:MAX_ARTICLES]
