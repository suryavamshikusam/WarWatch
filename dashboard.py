"""
dashboard.py — Builds live_data.js from today.json. Zero AI.

Reads today.json written by scraper.py.
Splits articles into war feed and india feed.
Writes live_data.js consumed by index.html.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

TODAY_FILE = Path("today.json")


def _time_ago(ts):
    try:
        dt = datetime.strptime(ts, "%Y-%m-%d %H:%M UTC").replace(tzinfo=timezone.utc)
        diff = int((datetime.now(timezone.utc) - dt).total_seconds())
        if diff < 60:    return "just now"
        if diff < 3600:  return f"{diff // 60}m ago"
        if diff < 86400:
            h = diff // 3600
            return f"{h}h ago"
        return f"{diff // 86400}d ago"
    except Exception:
        return ts


def _sig_color(sig):
    return {"HIGH":"#a32d2d","MEDIUM":"#7a530a","LOW":"#1d6e42"}.get(sig,"#7a530a")


def _extract_key_facts(art):
    facts = []
    snippet  = art.get("snippet","")
    source   = art.get("source","")
    cat      = art.get("category","")
    sig      = art.get("significance","MEDIUM")

    facts.append(f"Reported by {source} · Significance: {sig.lower().capitalize()}")

    cat_context = {
        "Energy":    "India imports 60%+ of crude — Hormuz transit affects ₹200B+ annual oil bill",
        "Diaspora":  "8.9M Indians in Gulf — $125B/year remittances. MEA 24hr helpline active.",
        "Diplomacy": "India maintains ties with US, Israel and Iran simultaneously — non-aligned stance",
        "Trade":     "Chabahar port ($85M Indian investment) and Central Asia trade route affected",
        "Economy":   "Weak rupee raises cost of all imports. RBI monitoring situation.",
        "Security":  "Indian Navy on readiness for potential Gulf evacuation scenario",
        "War":       "US-Israel-Iran conflict — escalation level HIGH. Day count rising.",
        "Markets":   "Brent crude +36% since war · Gold +62% · Safe-haven demand surging",
    }
    if cat in cat_context:
        facts.append(cat_context[cat])

    sentences = [s.strip() for s in snippet.split(". ") if len(s.strip()) > 30]
    for s in sentences[:2]:
        if s and s not in facts:
            facts.append(s if s.endswith(".") else s + ".")

    return facts[:4]


def _build_card(art):
    return {
        "url":          art.get("url","#"),
        "title":        art.get("title",""),
        "snippet":      art.get("snippet",""),
        "source":       art.get("source","Source"),
        "image":        art.get("image",""),
        "score":        art.get("score",0),
        "india":        art.get("india",False),
        "category":     art.get("category","War"),
        "significance": art.get("significance","MEDIUM"),
        "sigColor":     _sig_color(art.get("significance","MEDIUM")),
        "timeAgo":      _time_ago(art.get("fetched_at","")),
        "fetchedAt":    art.get("fetched_at",""),
        "keyFacts":     _extract_key_facts(art),
    }


def _build_tension_meters(level):
    base  = {"CRITICAL":92,"HIGH":78,"MEDIUM":52,"LOW":30}.get(level,52)
    color = {"CRITICAL":"#e05555","HIGH":"#c87830","MEDIUM":"#d4892a","LOW":"#3daa72"}.get(level,"#d4892a")
    return [
        {"label":"US vs Iran",       "pct":min(98,base+10),"lvl":level,    "color":color},
        {"label":"Israel vs Iran",   "pct":min(98,base+2), "lvl":level,    "color":color},
        {"label":"Gaza ceasefire",   "pct":max(10,100-base),"lvl":"Holding","color":"#3daa72"},
        {"label":"Nuclear progress", "pct":min(98,base-5), "lvl":"High",   "color":"#d4892a"},
        {"label":"Regional war risk","pct":min(95,base-10),"lvl":"Elevated","color":"#e05555"},
    ]


def _build_india_meter(india_articles):
    if not india_articles:
        return {"pct":52,"lvl":"Moderate","color":"#3daa72"}
    high = sum(1 for a in india_articles if a.get("significance")=="HIGH")
    if high >= 3: return {"pct":85,"lvl":"Severe",  "color":"#e05555"}
    if high >= 1: return {"pct":70,"lvl":"High",    "color":"#d4892a"}
    return          {"pct":52,"lvl":"Moderate","color":"#3daa72"}


def build_dashboard():
    today = {}
    if TODAY_FILE.exists():
        try:
            today = json.loads(TODAY_FILE.read_text())
        except Exception:
            pass

    articles = today.get("articles",[])
    date_str = today.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    last_run = today.get("last_run","")
    total    = today.get("total", len(articles))

    war_articles   = [a for a in articles if not a.get("india")]
    india_articles = [a for a in articles if a.get("india")]

    war_cards   = [_build_card(a) for a in war_articles]
    india_cards = [_build_card(a) for a in india_articles]

    top    = sorted(articles, key=lambda a: a.get("score",0), reverse=True)[:8]
    alerts = [f"{a['source']}: {a['title']}" for a in top]

    max_score = max((a.get("score",0) for a in articles), default=0)
    if   max_score >= 9: level = "CRITICAL"
    elif max_score >= 6: level = "HIGH"
    elif max_score >= 3: level = "MEDIUM"
    else:                level = "LOW"

    payload = {
        "date":            date_str,
        "lastRun":         last_run,
        "generatedAt":     last_run,
        "totalArticles":   total,
        "escalationLevel": level,
        "alerts":          alerts,
        "warCards":        war_cards,
        "indiaCards":      india_cards,
        "newsCards":       war_cards + india_cards,   # legacy
        "heroStats": {
            "tension":      level,
            "updatesToday": total,
            "lastUpdated":  last_run,
            "sourcesUsed":  len(set(a.get("source","") for a in articles)),
        },
        "tensionMeters":   _build_tension_meters(level),
        "indiaMeter":      _build_india_meter(india_articles),
        "indiaSummary":    "\n\n".join(
            f"{a.get('title','')}\n\n{a.get('snippet','')[:200]}"
            for a in india_articles[:4]
        ) or "No India-specific developments in the current news cycle.",
        "execSummaryRich": (
            f"Escalation level: {level}. "
            + " · ".join(
                f"{a.get('source','')}: {a.get('title','')}"
                for a in sorted(war_articles, key=lambda x: x.get("score",0), reverse=True)[:3]
            )
        ) if war_articles else "Monitoring conflict developments.",
        "indiaImpact": [
            {
                "headline":     a.get("title",""),
                "detail":       a.get("snippet","")[:180],
                "category":     a.get("category","India"),
                "significance": a.get("significance","MEDIUM"),
                "sourceUrl":    a.get("url","#"),
                "source":       a.get("source","Source"),
                "full_detail":  a.get("snippet",""),
            }
            for a in india_articles[:6]
        ],
        "sentiment": {
            "overall_tone": "ESCALATING" if level in ("HIGH","CRITICAL") else "TENSE",
        },
    }

    js = f"window.WARWATCH_LIVE = {json.dumps(payload, indent=2, ensure_ascii=False)};\n"
    Path("live_data.js").write_text(js, encoding="utf-8")

    print(f"[OK] live_data.js written — {len(war_cards)} war + {len(india_cards)} India articles")
    print(f"     Level: {level} | Last run: {last_run}")


if __name__ == "__main__":
    build_dashboard()
