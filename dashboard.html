"""
dashboard.py — Generates live_data.js from saved JSON reports.
warwatch.html loads live_data.js to populate all live sections.

Run automatically by bot.py after every report, or manually:
  python dashboard.py
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

REPORTS_DIR = Path("reports")


def _level_to_pct(level: str) -> int:
    return {"LOW": 30, "MEDIUM": 52, "HIGH": 75, "CRITICAL": 92}.get(level, 50)


def _level_color(level: str) -> str:
    return {
        "LOW":      "var(--green)",
        "MEDIUM":   "var(--amber)",
        "HIGH":     "#c87830",
        "CRITICAL": "var(--red)",
    }.get(level, "var(--text3)")


def _actor_pill_class(actor: str) -> str:
    return {
        "US":        "p-blue",
        "Israel":    "p-blue",
        "Iran":      "p-red",
        "Hamas":     "p-red",
        "Hezbollah": "p-red",
        "Other":     "p-gray",
    }.get(actor, "p-gray")


def _significance_badge(sig: str) -> str:
    return {
        "HIGH":   "b-crit",
        "MEDIUM": "b-high",
        "LOW":    "b-gray",
    }.get(sig, "b-gray")


def _time_ago(ts: str) -> str:
    """Convert '2026-03-14 05:35 UTC' to '2 hrs ago' style."""
    try:
        dt = datetime.strptime(ts, "%Y-%m-%d %H:%M UTC").replace(tzinfo=timezone.utc)
        diff = int((datetime.now(timezone.utc) - dt).total_seconds())
        if diff < 60:
            return "just now"
        if diff < 3600:
            return f"{diff // 60} min ago"
        if diff < 86400:
            h = diff // 3600
            return f"{h} hr{'s' if h > 1 else ''} ago"
        d = diff // 86400
        return f"{d} day{'s' if d > 1 else ''} ago"
    except Exception:
        return ts


def _build_india_impact(report: dict) -> list:
    """Map india_impact items with all required fields for the frontend."""
    items = []
    for item in report.get("india_impact", []):
        items.append({
            "headline":    item.get("headline", ""),
            "detail":      item.get("detail", ""),
            "category":    item.get("category", ""),
            "significance":item.get("significance", "MEDIUM"),
            "full_detail": item.get("full_detail", ""),
            "sourceUrl":   item.get("sourceUrl", "#"),
            "source":      item.get("source", "Source"),
        })
    return items


def build_dashboard():
    REPORTS_DIR.mkdir(exist_ok=True)

    # Load up to 48 most recent reports (12 days @ 6hr cadence)
    reports = []
    for f in sorted(REPORTS_DIR.glob("*.json"), reverse=True)[:48]:
        try:
            with open(f) as fp:
                reports.append(json.load(fp))
        except Exception:
            pass

    latest = reports[0] if reports else {}
    level  = latest.get("escalation_level", "CRITICAL")

    # ── Alert typewriter strings (from latest report) ──────────────────────
    alerts = []
    for dev in latest.get("key_developments", [])[:5]:
        headline = dev.get("headline", "")
        detail   = dev.get("detail", "")
        actor    = dev.get("actor", "")
        if headline:
            alerts.append(f"{actor}: {headline} · {detail[:80]}{'…' if len(detail) > 80 else ''}")

    # Fallback if no developments
    if not alerts:
        alerts = [latest.get("executive_summary", "No updates yet.")]

    # ── Hero stats ──────────────────────────────────────────────────────────
    updates_today = sum(
        1 for r in reports
        if r.get("generated_at", "").startswith(
            datetime.now(timezone.utc).strftime("%Y-%m-%d")
        )
    )
    hero_stats = {
        "tension":      level,
        "updatesToday": updates_today or len(reports),
        "lastUpdated":  latest.get("generated_at", ""),
        "sourcesUsed":  latest.get("sources_used", 0),
    }

    # ── Tension meters (derived from latest report) ─────────────────────────
    # We compute the US-Iran and Israel-Iran bars from the escalation level
    # and enrich with sentiment tone.
    tone = latest.get("sentiment", {}).get("overall_tone", "")
    tone_boost = {"VOLATILE": 8, "ESCALATING": 5, "TENSE": 2, "STABLE": -10, "DE-ESCALATING": -15}.get(tone, 0)
    base = _level_to_pct(level)

    tension_meters = [
        {"label": "US vs Iran",        "pct": min(98, base + tone_boost),      "lvl": level,    "color": _level_color(level)},
        {"label": "Israel vs Iran",    "pct": min(98, base + tone_boost - 8),  "lvl": level,    "color": _level_color(level)},
        {"label": "Gaza ceasefire",    "pct": max(10, 100 - base + 5),         "lvl": "Holding","color": "var(--green)"},
        {"label": "Nuclear progress",  "pct": min(98, base - 5 + tone_boost),  "lvl": "High",   "color": "var(--amber)"},
        {"label": "Regional war risk", "pct": min(95, base - 10 + tone_boost), "lvl": "Elevated","color": "var(--red)"},
    ]

    # ── News cards from latest report ────────────────────────────────────────
    news_cards = []
    for dev in latest.get("key_developments", []):
        actor    = dev.get("actor", "Other")
        sig      = dev.get("significance", "MEDIUM")
        headline = dev.get("headline", "")
        detail   = dev.get("detail", "")
        time_str = _time_ago(latest.get("generated_at", ""))

        news_cards.append({
            "badgeClass":  _significance_badge(sig),
            "badgeLabel":  sig.capitalize(),
            "actorClass":  _actor_pill_class(actor),
            "actor":       actor,
            "time":        time_str,
            "headline":    headline,
            "summary":     detail,
            "whyTxt":      latest.get("escalation_reason", ""),
            "orgs":        [actor],
        })

    # Also add a "what to watch" card
    watch = latest.get("what_to_watch_next", "")
    if watch:
        news_cards.append({
            "badgeClass":  "b-gray",
            "badgeLabel":  "Analysis",
            "actorClass":  "p-gray",
            "actor":       "Monitor",
            "time":        _time_ago(latest.get("generated_at", "")),
            "headline":    "What to watch in the next 6 hours",
            "summary":     watch,
            "whyTxt":      latest.get("executive_summary", ""),
            "orgs":        [],
        })

    # ── Historical escalation data for a chart (last 20 reports) ────────────
    history = [
        {
            "t": r.get("generated_at", ""),
            "l": r.get("escalation_level", "MEDIUM"),
            "tone": r.get("sentiment", {}).get("overall_tone", ""),
        }
        for r in reversed(reports[:20])
    ]

    # ── Sentiment block ──────────────────────────────────────────────────────
    sentiment = latest.get("sentiment", {})

    # ── Terms glossary ──────────────────────────────────────────────────────
    terms = latest.get("terminology_explained", [])

    # ── Assemble live_data.js ────────────────────────────────────────────────
    payload = {
        "generatedAt":    latest.get("generated_at", ""),
        "escalationLevel": level,
        "alerts":         alerts,
        "heroStats":      hero_stats,
        "tensionMeters":  tension_meters,
        "newsCards":      news_cards,
        "sentiment":      sentiment,
        "terms":          terms,
        "history":        history,
        "execSummary":    latest.get("executive_summary", ""),
        "totalReports":   len(reports),
        "execSummaryRich": latest.get("execSummaryRich", latest.get("executive_summary", "")),
        "indiaSummary":   latest.get("india_summary", latest.get("indiaSummary", "")),
        "indiaImpact":    _build_india_impact(latest),
    }

    js = f"window.WARWATCH_LIVE = {json.dumps(payload, indent=2)};\n"
    # Expose Groq API key for frontend live AI analysis
    groq_key = os.environ.get("GROQ_API_KEY", "")
    if groq_key:
        js += f"window.GROQ_API_KEY = '{groq_key}';\n"

    with open("live_data.js", "w") as f:
        f.write(js)
    print("[OK] live_data.js written")

    # Also keep the legacy dashboard.html for local viewing
    _build_legacy_html(reports)


def _build_legacy_html(reports):
    """Keep a basic legacy dashboard.html as a fallback."""
    level_colors = {"LOW":"#1D9E75","MEDIUM":"#BA7517","HIGH":"#D85A30","CRITICAL":"#A32D2D"}
    cards = ""
    for r in reports[:10]:
        lvl   = r.get("escalation_level", "MEDIUM")
        color = level_colors.get(lvl, "#888")
        devs  = "".join(
            f'<li style="font-size:13px;margin:3px 0;color:#ccc">'
            f'<strong style="color:#fff">{d.get("actor","")}</strong> — {d.get("headline","")}</li>'
            for d in r.get("key_developments", [])[:3]
        )
        cards += f"""
        <div style="background:#2a2a2a;border:1px solid rgba(255,255,255,0.1);
          border-radius:12px;padding:20px;margin-bottom:14px">
          <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px">
            <span style="padding:3px 10px;border-radius:4px;font-size:11px;font-weight:700;
              background:{color}22;color:{color};border:1px solid {color};
              font-family:monospace;letter-spacing:.06em">{lvl}</span>
            <span style="font-size:12px;color:#666">{r.get('generated_at','')}</span>
            <span style="margin-left:auto;font-size:12px;color:#555">
              {r.get('sentiment',{}).get('overall_tone','')}</span>
          </div>
          <p style="font-size:14px;color:#ccc;margin:0 0 10px;line-height:1.7">
            {r.get('executive_summary','')}</p>
          <ul style="margin:0;padding-left:16px">{devs}</ul>
        </div>"""

    timeline_data = json.dumps([
        {"t": r.get("generated_at",""), "l": r.get("escalation_level","MEDIUM")}
        for r in reversed(reports[:20])
    ])

    html = f"""<!DOCTYPE html>
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
    border-radius:12px;padding:20px;margin-bottom:16px}}
  h2{{font-family:'IBM Plex Mono',monospace;font-size:10px;letter-spacing:.12em;
    text-transform:uppercase;color:#5c5c5c;margin-bottom:14px}}
  canvas{{width:100%!important}}
  a{{color:#5b9cf6;text-decoration:none}}
</style>
</head><body>
<div class="bar">
  <span style="font-family:monospace;font-size:14px;font-weight:500;
    letter-spacing:.06em;text-transform:uppercase">War<span style="color:#e05555">Watch</span> Bot</span>
  <span style="font-size:12px;color:#555">NDTV · Groq · Every 6hrs</span>
  <span style="margin-left:auto;font-size:12px;color:#555">
    Last run: {datetime.now(timezone.utc).strftime('%b %d %H:%M UTC')}</span>
</div>
<div class="main">
  <div>
    <h2>Report log — {len(reports)} reports</h2>
    {cards or '<p style="color:#555;font-size:14px">No reports yet.</p>'}
  </div>
  <div style="position:sticky;top:20px;align-self:start">
    <div class="card">
      <h2>Escalation history</h2>
      <canvas id="ch" height="180"></canvas>
    </div>
    <div class="card">
      <h2>About</h2>
      <p style="font-size:12px;color:#666;line-height:1.7">
        Bot scrapes NDTV every 6 hrs · Summarises with Groq/Llama ·
        Emails report · Updates <a href="warwatch.html">warwatch.html</a> live.<br><br>
        <strong style="color:#9a9a9a">live_data.js</strong> is regenerated every run.
      </p>
    </div>
  </div>
</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<script>
const d={timeline_data};
const lm={{"LOW":1,"MEDIUM":2,"HIGH":3,"CRITICAL":4}};
const cm={{"LOW":"#3daa72","MEDIUM":"#d4892a","HIGH":"#c87830","CRITICAL":"#e05555"}};
new Chart(document.getElementById('ch').getContext('2d'),{{
  type:'line',
  data:{{
    labels:d.map(x=>x.t.slice(5,16)),
    datasets:[{{
      data:d.map(x=>lm[x.l]||2),
      borderColor:'#e05555',backgroundColor:'rgba(224,85,85,0.08)',
      tension:0.4,fill:true,
      pointBackgroundColor:d.map(x=>cm[x.l]||'#d4892a'),
      pointRadius:4
    }}]
  }},
  options:{{
    plugins:{{legend:{{display:false}}}},
    scales:{{
      y:{{min:0,max:5,ticks:{{color:'#5c5c5c',
        callback:v=>['','Low','Med','High','Crit',''][v]||''}},
        grid:{{color:'rgba(255,255,255,0.05)'}}}},
      x:{{ticks:{{color:'#5c5c5c',maxRotation:45}},
        grid:{{color:'rgba(255,255,255,0.05)'}}}}
    }}
  }}
}});
</script>
</body></html>"""

    with open("dashboard.html", "w") as f:
        f.write(html)
    print("[OK] dashboard.html updated")


if __name__ == "__main__":
    build_dashboard()
    print("Done! Open warwatch.html in your browser.")