"""
scraper.py — Pure RSS scraper. No AI. No API keys.

- Fetches 8 RSS sources (war + India specific)
- Scores by keyword relevance
- Tags India articles
- Saves to today.json (auto-resets at midnight UTC)
- Keeps latest 25 articles, drops oldest
"""

import re
import json
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from bs4 import BeautifulSoup
import warnings

warnings.filterwarnings("ignore")

TODAY_FILE   = Path("today.json")
MAX_ARTICLES = 25

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

# ── RSS Sources ────────────────────────────────────────────────────────────────
WAR_SOURCES = [
    ("Al Jazeera",     "https://www.aljazeera.com/xml/rss/all.xml"),
    ("BBC",            "https://feeds.bbci.co.uk/news/world/middle_east/rss.xml"),
    ("BBC World",      "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("Middle East Eye","https://www.middleeasteye.net/rss"),
    ("Defense One",    "https://www.defenseone.com/rss/all/"),
]

INDIA_SOURCES = [
    ("NDTV",           "https://feeds.feedburner.com/ndtvnews-top-stories"),
    ("Indian Express", "https://indianexpress.com/section/world/feed/"),
    ("Indian Express", "https://indianexpress.com/section/india/feed/"),
]

# ── Keywords ──────────────────────────────────────────────────────────────────
HIGH_WAR_KEYWORDS = [
    "iran war","us strike","israel strike","irgc","idf strike",
    "strait of hormuz","kharg island","chabahar","iranian missile",
    "iranian drone","shahed","ballistic missile","khamenei","netanyahu",
    "pentagon iran","us iran","israel iran","operation midnight",
    "nuclear site","fordow","natanz","isfahan",
]

MEDIUM_WAR_KEYWORDS = [
    "iran","israel","hamas","hezbollah","gaza","middle east",
    "nuclear","idf","pentagon","missile","drone",
    "trump iran","tehran","tel aviv","ceasefire","sanctions",
    "hormuz","saudi arabia","proxy war","airstrike","retaliation",
    "escalation","warship","carrier group","houthi",
]

INDIA_KEYWORDS = [
    "india iran","india oil","india gulf","indian sailors","indian nationals",
    "mea india","ministry of external affairs","air india","indigo gulf",
    "india crude","india energy","chabahar india","india diaspora",
    "india israel","india diplomacy","modi iran","modi israel",
    "rupee","bpcl","hpcl","ioc refin","indian navy gulf",
    "kerala gulf","ndtv","indian express","india war",
    "indians in uae","indians in saudi","indians in kuwait",
    "india remittance","india petrol","india fuel",
]

CATEGORY_RULES = [
    ("Energy",    ["oil","crude","brent","hormuz","petrol","fuel","energy","opec","refin"]),
    ("Diaspora",  ["diaspora","nationals","evacuation","helpline","mea","air india","expat","kerala","remittance"]),
    ("Diplomacy", ["diplomacy","ceasefire","talks","negotiat","oman","qatar mediat","un vote","abstain","modi call"]),
    ("Trade",     ["chabahar","port","trade","mundra","cargo","shipping","supply chain","central asia"]),
    ("Economy",   ["rupee","inflation","petrol price","fuel price","market","stock","bse","nse","gdp"]),
    ("Security",  ["navy","evacuation","military","ndrf","standby","troops","defence"]),
    ("War",       ["strike","missile","drone","bomb","attack","irgc","idf","airstrike"]),
    ("Markets",   ["brent","wti","gold","crude","wheat","opec","oil price"]),
]


def _score_article(title, desc):
    text = (title + " " + desc).lower()
    score = 0
    for kw in HIGH_WAR_KEYWORDS:
        if kw in text:
            score += 3
    for kw in MEDIUM_WAR_KEYWORDS:
        if kw in text:
            score += 1
    return score


def _is_india_tagged(title, desc):
    text = (title + " " + desc).lower()
    return any(kw in text for kw in INDIA_KEYWORDS)


def _get_category(title, desc, is_india):
    text = (title + " " + desc).lower()
    for cat, keywords in CATEGORY_RULES:
        if any(kw in text for kw in keywords):
            if is_india and cat in ("War", "Markets"):
                continue
            return cat
    return "India" if is_india else "War"


def _get_significance(score):
    if score >= 6:
        return "HIGH"
    if score >= 3:
        return "MEDIUM"
    return "LOW"


def _extract_image(item):
    for mc in item.findall("media:content", NAMESPACES):
        url = mc.get("url", "")
        if url and any(ext in url.lower() for ext in [".jpg",".jpeg",".png",".webp"]):
            return url
    mt = item.find("media:thumbnail", NAMESPACES)
    if mt is not None:
        url = mt.get("url","")
        if url:
            return url
    enc = item.find("enclosure")
    if enc is not None and "image" in enc.get("type",""):
        return enc.get("url","")
    desc = item.findtext("description","")
    if desc and "<img" in desc:
        m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', desc)
        if m:
            return m.group(1)
    return ""


def _clean_html(text):
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:400]


def _parse_feed(source_label, url, seen_urls, force_india=False):
    results = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15, verify=False)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)

        for item in root.findall(".//item"):
            title = item.findtext("title","").strip()
            link  = item.findtext("link","").strip()
            desc  = _clean_html(item.findtext("description",""))

            if not link:
                link_el = item.find("{http://www.w3.org/2005/Atom}link")
                if link_el is not None:
                    link = link_el.get("href","").strip()

            if not link or link in seen_urls or len(title) < 10:
                continue

            score = _score_article(title, desc)
            if not force_india and score == 0:
                continue

            is_india = force_india or _is_india_tagged(title, desc)
            category = _get_category(title, desc, is_india)
            significance = _get_significance(score)

            seen_urls.add(link)
            results.append({
                "url":          link,
                "title":        title,
                "snippet":      desc or title,
                "source":       source_label,
                "image":        _extract_image(item),
                "score":        score,
                "india":        is_india,
                "category":     category,
                "significance": significance,
                "fetched_at":   datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                "time_ago":     "just now",
            })

    except ET.ParseError as e:
        print(f"  [WARN] XML parse error {source_label}: {e}")
    except requests.RequestException as e:
        print(f"  [ERROR] {source_label}: {e}")
    except Exception as e:
        print(f"  [ERROR] Unexpected {source_label}: {e}")

    return results


def _load_today():
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if TODAY_FILE.exists():
        try:
            data = json.loads(TODAY_FILE.read_text())
            if data.get("date") == today_str:
                return data
            else:
                print(f"  New day ({today_str}) — wiping previous data ({data.get('date','?')})")
        except Exception:
            pass
    return {"date": today_str, "articles": [], "seen_urls": []}


def _save_today(data):
    TODAY_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def fetch_and_update():
    today     = _load_today()
    seen_urls = set(today.get("seen_urls", []))
    existing  = today.get("articles", [])

    print(f"  Today: {today['date']} | Existing: {len(existing)} | Seen URLs: {len(seen_urls)}")

    new_articles = []

    for source_label, url in WAR_SOURCES:
        print(f"  Fetching {source_label}...")
        batch = _parse_feed(source_label, url, seen_urls, force_india=False)
        new_articles.extend(batch)
        print(f"    → {len(batch)} new articles")

    for source_label, url in INDIA_SOURCES:
        print(f"  Fetching {source_label} (India)...")
        batch = _parse_feed(source_label, url, seen_urls, force_india=True)
        new_articles.extend(batch)
        print(f"    → {len(batch)} India articles")

    new_articles.sort(key=lambda a: a["score"], reverse=True)

    print(f"  New articles found: {len(new_articles)}")

    merged = new_articles + existing
    merged = merged[:MAX_ARTICLES]

    all_seen = list(seen_urls) + [a["url"] for a in new_articles]
    all_seen = list(dict.fromkeys(all_seen))[-500:]

    today["articles"]  = merged
    today["seen_urls"] = all_seen
    today["last_run"]  = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    today["total"]     = len(merged)

    _save_today(today)
    print(f"  Saved today.json — {len(merged)} articles total")
    return today


def fetch_all_articles():
    data = fetch_and_update()
    return data.get("articles", [])


if __name__ == "__main__":
    data = fetch_and_update()
    arts = data["articles"]
    india = [a for a in arts if a["india"]]
    print(f"\nTotal: {len(arts)} | India: {len(india)} | War: {len(arts)-len(india)}")
    for a in arts[:5]:
        tag = "[IN]" if a["india"] else "[WR]"
        print(f"  {tag} [{a['source']}] score={a['score']} {a['title'][:65]}")
