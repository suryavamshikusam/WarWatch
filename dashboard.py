"""
dashboard.py — Builds live_data.js from the latest report JSON files.

Called by bot.py after each pipeline run:
    from dashboard import build_dashboard
    build_dashboard()

Also regenerates dashboard_log.html (the report history page).

live_data.js schema consumed by index.html, india.html, history.html, warwatch.html:
  generatedAt       str
  escalationLevel   str  (LOW / MEDIUM / HIGH / CRITICAL)
  alerts            list[str]
  heroStats         { tension, updatesToday, lastUpdated, sourcesUsed }
  tensionMeters     list[{ label, pct, lvl, color }]
  newsCards         list[{ badgeClass, badgeLabel, actorClass, actor, time,
                           headline, summary, whyTxt, orgs, fullAnalysis,
                           sourceUrl, imageUrl, sourceLabel }]   ← sourceUrl + imageUrl REQUIRED
  sentiment         { overall_tone, us_stance, israel_stance, iran_stance }
  terms             list[{ term, simple_explanation }]
  history           list[{ t, l, tone }]
  execSummary       str
  totalReports      int
  indiaImpact       list[{ headline, detail, category, significance,
                           full_detail, imageUrl, sourceUrl }]   ← imageUrl + sourceUrl REQUIRED
  indiaSummary      str
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

REPORTS_DIR   = Path("reports")
LIVE_DATA_JS  = Path("live_data.js")
DASHBOARD_LOG = Path("dashboard_log.html")

# ── Escalation → tension-meter config ────────────────────────────────────────
LEVEL_META = {
    "CRITICAL": {"color": "var(--red)",   "badge": "b-crit", "pct_boost": 0},
    "HIGH":     {"color": "var(--red)",   "badge": "b-high", "pct_boost": 0},
    "MEDIUM":   {"color": "var(--amber)", "badge": "b-med",  "pct_boost": 0},
    "LOW":      {"color": "var(--green)", "badge": "b-low",  "pct_boost": 0},
}

ACTOR_CLASS = {
    "US":      "p-blue",
    "Israel":  "p-blue",
    "IDF":     "p-blue",
    "Iran":    "p-red",
    "IRGC":    "p-red",
    "Hamas":   "p-red",
    "Hezbollah": "p-red",
    "Monitor": "p-gray",
    "India":   "p-green",
}

# Curated Unsplash photo IDs by topic (direct CDN — not source.unsplash.com redirect API)
# Format: https://images.unsplash.com/photo-{id}?w=800&q=80&fit=crop
UNSPLASH_PHOTO_IDS = {
    "oil":       "1474546499760-77a0b18c5e69",   # oil refinery
    "drone":     "1585776245991-cf89dd7fc73a",   # military aircraft
    "missile":   "1614728263952-84ea256f9d1d",   # military
    "nuclear":   "1518709414768-a88981a4515d",   # nuclear power
    "diplomacy": "1529107386315-e1a2ed48a1e3",   # diplomacy/meeting
    "india":     "1582510003544-4d00b7f74220",   # India parliament
    "ceasefire": "1541872703-74c5e44368f9",      # peace/negotiation
    "strike":    "1540575467063-178a50c2df87",   # military aircraft
    "hormuz":    "1505118380757-91f5f5632de0",   # ocean strait
    "ship":      "1566753323558-f4e0952af115",   # ship at sea
    "dubai":     "1512453979798-5ea266f8880c",   # Dubai skyline
    "iran":      "1604072366595-e75dc92d6bdc",   # Middle East
    "israel":    "1548116022-c8c56de428d5",      # Middle East city
    "default":   "1579548122080-c35fd6820734",   # conflict/military generic
}


def _unsplash(text: str, w: int = 800, h: int = 450) -> str:
    """Return a working Unsplash CDN image URL matched to the topic."""
    text_lower = text.lower()
    for key, photo_id in UNSPLASH_PHOTO_IDS.items():
        if key in text_lower:
            return f"https://images.unsplash.com/photo-{photo_id}?w={w}&h={h}&q=80&fit=crop"
    return f"https://images.unsplash.com/photo-{UNSPLASH_PHOTO_IDS['default']}?w={w}&h={h}&q=80&fit=crop"


def _load_reports() -> list:
    """Load all report JSON files, sorted newest-first."""
    if not REPORTS_DIR.exists():
        return []
    reports = []
    for p in sorted(REPORTS_DIR.glob("report_*.json"), reverse=True):
        try:
            reports.append(json.loads(p.read_text()))
        except Exception as e:
            print(f"  [WARN] Could not load {p}: {e}")
    return reports


def _actor_class(actor: str) -> str:
    for key, cls in ACTOR_CLASS.items():
        if key.lower() in actor.lower():
            return cls
    return "p-gray"


def _badge(significance: str) -> tuple:
    sig = (significance or "").upper()
    if sig == "HIGH":
        return "b-crit", "High"
    if sig == "MEDIUM":
        return "b-high", "Medium"
    return "b-gray", "Low"


def _time_ago(generated_at: str) -> str:
    """Convert a UTC timestamp string to a rough '2 hrs ago' label."""
    try:
        then = datetime.strptime(generated_at, "%Y-%m-%d %H:%M UTC").replace(tzinfo=timezone.utc)
        diff = (datetime.now(timezone.utc) - then).total_seconds()
        if diff < 3600:
            return f"{int(diff // 60)} min ago"
        if diff < 86400:
            return f"{int(diff // 3600)} hrs ago"
        return f"{int(diff // 86400)} days ago"
    except Exception:
        return "recently"


def _build_tension_meters(report: dict) -> list:
    """Build tension meter data from the latest report."""
    level = report.get("escalation_level", "MEDIUM")
    sentiment = report.get("sentiment", {})

    # Base percentages mapped from escalation level
    base = {"CRITICAL": 90, "HIGH": 72, "MEDIUM": 50, "LOW": 25}.get(level, 50)

    def tone_bump(tone: str) -> int:
        t = (tone or "").lower()
        if "hostile" in t or "aggressive" in t: return 8
        if "defensive" in t: return -5
        return 0

    return [
        {"label": "US vs Iran",        "pct": min(99, base + tone_bump(sentiment.get("us_stance", ""))),   "lvl": level.capitalize(), "color": "var(--red)"    if level in ("CRITICAL","HIGH") else "var(--amber)"},
        {"label": "Israel vs Iran",    "pct": min(99, base - 8 + tone_bump(sentiment.get("israel_stance",""))), "lvl": level.capitalize(), "color": "var(--red)"},
        {"label": "Gaza ceasefire",    "pct": 38, "lvl": "Holding",  "color": "var(--green)"},
        {"label": "Nuclear progress",  "pct": min(99, base - 20),    "lvl": "High" if base > 60 else "Moderate", "color": "var(--amber)"},
        {"label": "Regional war risk", "pct": min(99, base - 12),    "lvl": "Elevated" if base > 55 else "Moderate", "color": "var(--red)" if base > 65 else "var(--amber)"},
    ]


def _build_news_cards(report: dict) -> list:
    """
    Map key_developments from the report into newsCards for live_data.js.
    Ensures sourceUrl and imageUrl are always populated.
    """
    cards = []
    generated_at = report.get("generated_at", "")

    for dev in report.get("key_developments", []):
        badge_class, badge_label = _badge(dev.get("significance", "MEDIUM"))
        actor = dev.get("actor", "Monitor")

        # imageUrl: use what summarizer stored, or generate a fallback
        image_url = dev.get("imageUrl", "")
        if not image_url or "source.unsplash.com" in image_url:
            image_url = _unsplash(dev.get("headline", "") + " " + actor)

        # sourceUrl: use what summarizer stored, fall back to "#"
        source_url   = dev.get("sourceUrl", "") or "#"
        source_label = dev.get("source", "Source")

        cards.append({
            "badgeClass":   badge_class,
            "badgeLabel":   badge_label,
            "actorClass":   _actor_class(actor),
            "actor":        actor,
            "time":         _time_ago(generated_at),
            "headline":     dev.get("headline", ""),
            "summary":      dev.get("detail", ""),
            "whyTxt":       dev.get("why_it_matters", ""),
            "orgs":         [actor],
            "fullAnalysis": dev.get("fullAnalysis", ""),
            "sourceUrl":    source_url,
            "sourceLabel":  source_label,
            "imageUrl":     image_url,
        })

    return cards


def _build_india_impact(report: dict) -> list:
    """
    Map india_impact items, ensuring imageUrl and sourceUrl are always set.
    """
    items = []
    for item in report.get("india_impact", []):
        image_url = item.get("imageUrl", "")
        if not image_url or "source.unsplash.com" in image_url:
            image_url = _unsplash(
                item.get("headline", "india") + " " + item.get("category", "india"),
                w=600, h=200
            )
        source_url   = item.get("sourceUrl", "") or "#"
        source_label = item.get("source", "Source")

        items.append({
            "headline":    item.get("headline", ""),
            "detail":      item.get("detail", ""),
            "category":    item.get("category", ""),
            "significance":item.get("significance", "MEDIUM"),
            "full_detail": item.get("full_detail", ""),
            "imageUrl":    image_url,
            "sourceUrl":   source_url,
            "source":      source_label,
        })
    return items


def _build_alerts(report: dict) -> list:
    """Generate alert ticker strings from key developments."""
    alerts = []
    for dev in report.get("key_developments", [])[:5]:
        actor   = dev.get("actor", "Monitor")
        headline = dev.get("headline", "")
        time_str = _time_ago(report.get("generated_at", ""))
        alerts.append(f"{actor}: {headline} · {time_str}")
    return alerts or ["Monitor: No new alerts at this time"]


def _build_history(reports: list) -> list:
    """Build escalation history entries from all report files."""
    history = []
    for r in reversed(reports[:48]):  # oldest first, cap at 48
        history.append({
            "t":    r.get("generated_at", ""),
            "l":    r.get("escalation_level", "MEDIUM"),
            "tone": r.get("escalation_reason", r.get("sentiment", {}).get("overall_tone", "TENSE"))[:20],
        })
    return history


def _count_today_updates(reports: list) -> int:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return sum(1 for r in reports if r.get("generated_at", "").startswith(today))


# ── HTML log builder ──────────────────────────────────────────────────────────

def _build_log_html(reports: list) -> str:
    """Regenerate dashboard_log.html from all report JSONs."""
    level_colors = {
        "LOW":      {"bg": "#1D9E7522", "fg": "#1D9E75", "border": "#1D9E75"},
        "MEDIUM":   {"bg": "#BA751722", "fg": "#BA7517", "border": "#BA7517"},
        "HIGH":     {"bg": "#D85A3022", "fg": "#D85A30", "border": "#D85A30"},
        "CRITICAL": {"bg": "#A32D2D22", "fg": "#A32D2D", "border": "#A32D2D"},
    }

    cards_html = ""
    for r in reports:
        level  = r.get("escalation_level", "MEDIUM")
        lc     = level_colors.get(level, level_colors["MEDIUM"])
        ts     = r.get("generated_at", "—")
        tone   = r.get("escalation_reason", r.get("sentiment", {}).get("overall_tone", ""))[:30]
        summary = r.get("executive_summary", "")[:300]

        devs_html = ""
        for dev in r.get("key_developments", [])[:4]:
            actor   = dev.get("actor", "")
            headline = dev.get("headline", "")
            src_url  = dev.get("sourceUrl", "")
            src_lbl  = dev.get("source", "")
            link_html = f' <a href="{src_url}" style="color:#5b9cf6;font-size:11px" target="_blank">↗</a>' if src_url and src_url != "#" else ""
            devs_html += f'<li style="font-size:13px;margin:3px 0;color:#ccc"><strong style="color:#fff">{actor}</strong> — {headline}{link_html}</li>'

        cards_html += f"""
        <div style="background:#2a2a2a;border:1px solid rgba(255,255,255,0.1);
          border-radius:6px;padding:20px;margin-bottom:14px">
          <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px">
            <span style="padding:3px 10px;border-radius:4px;font-size:11px;font-weight:700;
              background:{lc['bg']};color:{lc['fg']};border:1px solid {lc['border']};
              font-family:monospace;letter-spacing:.06em">{level}</span>
            <span style="font-size:12px;color:#666">{ts}</span>
            <span style="margin-left:auto;font-size:12px;color:#555">{tone.upper()}</span>
          </div>
          <p style="font-size:14px;color:#ccc;margin:0 0 10px;line-height:1.7">{summary}</p>
          <ul style="margin:0;padding-left:16px">{devs_html}</ul>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>WarWatch Bot — Report Log</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:'IBM Plex Sans',sans-serif;background:#1a1a1a;color:#ececec}}
  .bar{{background:#222;border-bottom:1px solid rgba(255,255,255,0.08);
    padding:14px 32px;display:flex;align-items:center;gap:12px}}
  .main{{max-width:860px;margin:0 auto;padding:28px 20px;
    display:grid;grid-template-columns:1fr 260px;gap:20px}}
  .card{{background:#212121;border:1px solid rgba(255,255,255,0.08);
    border-radius:6px;padding:20px;margin-bottom:16px}}
  h2{{font-family:'IBM Plex Mono',monospace;font-size:10px;letter-spacing:.12em;
    text-transform:uppercase;color:#5c5c5c;margin-bottom:14px}}
  canvas{{width:100%!important}}
  a{{color:#5b9cf6;text-decoration:none}}
  .info-box{{background:#212121;border:1px solid rgba(255,255,255,0.08);
    border-radius:6px;padding:20px;font-size:13px;color:#888;line-height:1.8}}
  .info-box strong{{color:#9a9a9a}}
</style>
</head><body>
<div class="bar">
  <span style="font-family:monospace;font-size:14px;font-weight:500;
    letter-spacing:.06em;text-transform:uppercase">War<span style="color:#e05555">Watch</span> Bot</span>
  <span style="font-size:12px;color:#555">17 RSS Sources · Groq/Llama · Every 15 min</span>
  <span style="margin-left:auto;font-size:12px;color:#555">
    Last run: {reports[0].get('generated_at', '—') if reports else '—'}</span>
</div>
<div class="main">
  <div>
    <h2>Report log — {len(reports)} reports</h2>
    {cards_html or '<p style="color:#555;font-size:14px">No reports yet.</p>'}
  </div>
  <div>
    <div class="card">
      <h2>About</h2>
      <div class="info-box">
        <strong>bot.py</strong> runs every 15 minutes via GitHub Actions.<br><br>
        <strong>scraper.py</strong> pulls from 17 RSS sources across 4 tiers.<br><br>
        <strong>summarizer.py</strong> uses Groq/Llama to generate deep-analysis reports.<br><br>
        <strong>dashboard.py</strong> converts reports to <strong style="color:#9a9a9a">live_data.js</strong> for all HTML pages.<br><br>
        <strong>emailer.py</strong> sends reports via Gmail SMTP on each update.
      </div>
    </div>
  </div>
</div>
</body></html>"""


# ── Main entry point ──────────────────────────────────────────────────────────

def build_dashboard():
    """
    Reads all reports from reports/ directory, builds live_data.js and
    regenerates dashboard_log.html.
    Called by bot.py after each pipeline run.
    """
    reports = _load_reports()

    if not reports:
        print("  [dashboard] No reports found — skipping live_data.js update.")
        return

    latest  = reports[0]
    level   = latest.get("escalation_level", "MEDIUM")
    ts      = latest.get("generated_at", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))

    news_cards   = _build_news_cards(latest)
    india_impact = _build_india_impact(latest)
    tension_meters = _build_tension_meters(latest)
    alerts       = _build_alerts(latest)
    history      = _build_history(reports)

    india_summary = (
        latest.get("india_summary") or
        latest.get("indiaSummary") or
        ""
    )
    exec_summary = (
        latest.get("execSummaryRich") or
        latest.get("execSummary") or
        latest.get("executive_summary") or
        ""
    )

    live_data = {
        "generatedAt":    ts,
        "escalationLevel": level,
        "alerts":         alerts,
        "heroStats": {
            "tension":      level,
            "updatesToday": _count_today_updates(reports),
            "lastUpdated":  ts,
            "sourcesUsed":  latest.get("sources_used", len(reports)),
        },
        "tensionMeters":  tension_meters,
        "newsCards":      news_cards,
        "sentiment":      latest.get("sentiment", {}),
        "terms":          latest.get("terminology_explained", []),
        "history":        history,
        "execSummary":    exec_summary,
        "totalReports":   len(reports),
        "indiaImpact":    india_impact,
        "indiaSummary":   india_summary,
    }

    js_content = "window.WARWATCH_LIVE = " + json.dumps(live_data, indent=2, ensure_ascii=False) + ";"
    LIVE_DATA_JS.write_text(js_content, encoding="utf-8")
    print(f"  [dashboard] live_data.js written — {len(news_cards)} newsCards, {len(india_impact)} India items")

    # Regenerate the log HTML
    log_html = _build_log_html(reports)
    DASHBOARD_LOG.write_text(log_html, encoding="utf-8")
    print(f"  [dashboard] dashboard_log.html updated — {len(reports)} reports logged")


if __name__ == "__main__":
    build_dashboard()
    print("Done.")