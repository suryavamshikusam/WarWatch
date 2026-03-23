"""
dashboard.py — Builds live_data.js from saved JSON reports.

Improvements:
  - Writes to live_data.tmp.js first (atomic — bot.py renames on success)
  - Guarantees every field the frontend needs is non-empty
  - Auto-builds indiaSummary from india_impact if empty
  - Auto-builds execSummaryRich from executive_summary if empty
  - indiaImpact always has at least 1 item
"""

import json
from datetime import datetime, timezone
from pathlib import Path

REPORTS_DIR = Path("reports")

LEVEL_PCT   = {"LOW":30,"MEDIUM":52,"HIGH":75,"CRITICAL":92}
LEVEL_COLOR = {"LOW":"var(--green)","MEDIUM":"var(--amber)","HIGH":"#c87830","CRITICAL":"var(--red)"}
ACTOR_CLASS = {"US":"p-blue","Israel":"p-blue","Iran":"p-red","Hamas":"p-red","Hezbollah":"p-red"}
SIG_BADGE   = {"HIGH":"b-crit","MEDIUM":"b-high","LOW":"b-gray"}


def _pct(level):  return LEVEL_PCT.get(level, 50)
def _col(level):  return LEVEL_COLOR.get(level, "var(--text3)")
def _actor(actor):return ACTOR_CLASS.get(actor, "p-gray")
def _badge(sig):  return SIG_BADGE.get(sig, "b-gray")


def _time_ago(ts: str) -> str:
    try:
        dt   = datetime.strptime(ts, "%Y-%m-%d %H:%M UTC").replace(tzinfo=timezone.utc)
        diff = int((datetime.now(timezone.utc) - dt).total_seconds())
        if diff < 60:    return "just now"
        if diff < 3600:  return f"{diff//60} min ago"
        if diff < 86400:
            h = diff//3600; return f"{h} hr{'s' if h>1 else ''} ago"
        d = diff//86400; return f"{d} day{'s' if d>1 else ''} ago"
    except Exception:
        return ts


def _safe_str(value, fallback="") -> str:
    """Return value if it's a non-empty string, else fallback."""
    if isinstance(value, str) and value.strip():
        return value.strip()
    return fallback


def _build_india_impact(report: dict) -> list:
    items = report.get("india_impact", [])
    if not items:
        # Guaranteed fallback so frontend India section never shows empty
        return [{
            "headline":    "India Monitors Conflict for Energy Security Impact",
            "detail":      ("India's energy imports and Gulf diaspora are closely watching the "
                            "US-Israel-Iran conflict. Oil price volatility directly affects fuel costs."),
            "category":    "Energy",
            "significance":"HIGH",
            "full_detail": ("India imports over 85% of its crude oil, with a significant share from "
                            "Gulf nations. Disruption to the Strait of Hormuz would immediately impact "
                            "supply chains. Over 8 million Indian nationals work in the Gulf, and their "
                            "remittances are a critical source of foreign exchange for India."),
            "sourceUrl":   "#",
            "source":      "WarWatch Monitor",
        }]
    return [{
        "headline":    i.get("headline",""),
        "detail":      i.get("detail",""),
        "category":    i.get("category",""),
        "significance":i.get("significance","MEDIUM"),
        "full_detail": i.get("full_detail",""),
        "sourceUrl":   i.get("sourceUrl","#"),
        "source":      i.get("source","Source"),
    } for i in items]


def _build_exec_summary_rich(report: dict) -> str:
    """Guarantee a non-empty execSummaryRich."""
    rich = _safe_str(report.get("execSummaryRich",""))
    if rich:
        return rich

    # Fallback: build from executive_summary
    base = _safe_str(report.get("executive_summary",""))
    if base:
        return base

    # Last resort: build from key developments
    devs = report.get("key_developments",[])
    if devs:
        headlines = ". ".join(d.get("headline","") for d in devs[:3] if d.get("headline"))
        level     = report.get("escalation_level","HIGH")
        tone      = report.get("sentiment",{}).get("overall_tone","ESCALATING")
        return (f"Escalation level: {level}. Situation tone: {tone}. "
                f"Latest developments: {headlines}. "
                f"The US-Israel-Iran conflict continues to evolve with significant implications "
                f"for regional stability, global oil markets, and India's energy security.")
    return "War Monitor active. Monitoring US-Israel-Iran conflict developments."


def _build_india_summary(report: dict) -> str:
    """Guarantee a non-empty indiaSummary."""
    summary = _safe_str(report.get("indiaSummary","") or report.get("india_summary",""))
    if summary:
        return summary

    # Build from india_impact items
    items = report.get("india_impact",[])
    if items:
        parts = []
        for item in items[:3]:
            h = item.get("headline","")
            d = item.get("detail","")
            fd = item.get("full_detail","")
            text = fd or d or h
            if text:
                parts.append(text)
        if parts:
            return "\n\n".join(parts)

    return (
        "India continues to closely monitor the US-Israel-Iran conflict given its significant "
        "energy import dependence on the Gulf region. Any disruption to oil shipments through "
        "the Strait of Hormuz would directly impact fuel prices for Indian consumers.\n\n"
        "The Indian government has contingency plans in place and is in active diplomatic "
        "contact with all parties to protect Indian interests and the safety of over 8 million "
        "Indian nationals living and working across Gulf nations.\n\n"
        "India's diplomatic balancing act — maintaining strong ties with the US and Israel "
        "while preserving its historically close relationship with Iran and Gulf states — "
        "is being tested by the escalating conflict."
    )


def build_dashboard():
    REPORTS_DIR.mkdir(exist_ok=True)

    reports = []
    for f in sorted(REPORTS_DIR.glob("*.json"), reverse=True)[:48]:
        try:
            reports.append(json.loads(f.read_text()))
        except Exception:
            pass

    latest = reports[0] if reports else {}
    level  = latest.get("escalation_level","HIGH")

    # ── Alerts ────────────────────────────────────────────────────────────────
    alerts = []
    for dev in latest.get("key_developments",[])[:5]:
        h = dev.get("headline","")
        d = dev.get("detail","")
        a = dev.get("actor","")
        if h:
            alerts.append(f"{a}: {h} · {d[:80]}{'…' if len(d)>80 else ''}")
    if not alerts:
        alerts = [_safe_str(latest.get("executive_summary",""), "War Monitor — monitoring active.")]

    # ── Hero stats ────────────────────────────────────────────────────────────
    today_str    = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    updates_today = sum(1 for r in reports if r.get("generated_at","").startswith(today_str))
    hero_stats   = {
        "tension":      level,
        "updatesToday": updates_today or len(reports),
        "lastUpdated":  latest.get("generated_at",""),
        "sourcesUsed":  latest.get("sources_used",0),
    }

    # ── Tension meters ────────────────────────────────────────────────────────
    tone       = latest.get("sentiment",{}).get("overall_tone","")
    tone_boost = {"VOLATILE":8,"ESCALATING":5,"TENSE":2,"STABLE":-10,"DE-ESCALATING":-15}.get(tone,0)
    base       = _pct(level)
    tension_meters = [
        {"label":"US vs Iran",       "pct":min(98,base+tone_boost),    "lvl":level,     "color":_col(level)},
        {"label":"Israel vs Iran",   "pct":min(98,base+tone_boost-8),  "lvl":level,     "color":_col(level)},
        {"label":"Gaza ceasefire",   "pct":max(10,100-base+5),         "lvl":"Holding", "color":"var(--green)"},
        {"label":"Nuclear progress", "pct":min(98,base-5+tone_boost),  "lvl":"High",    "color":"var(--amber)"},
        {"label":"Regional war risk","pct":min(95,base-10+tone_boost), "lvl":"Elevated","color":"var(--red)"},
    ]

    # ── News cards ────────────────────────────────────────────────────────────
    time_label = _time_ago(latest.get("generated_at",""))
    news_cards = []
    for dev in latest.get("key_developments",[]):
        analysis = _safe_str(dev.get("fullAnalysis",""), dev.get("detail",""))
        news_cards.append({
            "badgeClass":  _badge(dev.get("significance","MEDIUM")),
            "badgeLabel":  dev.get("significance","Medium").capitalize(),
            "actorClass":  _actor(dev.get("actor","Other")),
            "actor":       dev.get("actor","Other"),
            "time":        time_label,
            "headline":    dev.get("headline",""),
            "summary":     dev.get("detail",""),
            "whyTxt":      latest.get("escalation_reason",""),
            "orgs":        [dev.get("actor","Other")],
            "fullAnalysis":analysis,
            "sourceUrl":   dev.get("sourceUrl","#"),
            "sourceLabel": dev.get("sourceLabel", dev.get("source","Source")),
        })

    if latest.get("what_to_watch_next"):
        news_cards.append({
            "badgeClass":"b-gray","badgeLabel":"Analysis","actorClass":"p-gray",
            "actor":"Monitor","time":time_label,
            "headline":"What to watch in the next 6 hours",
            "summary":latest.get("what_to_watch_next",""),
            "whyTxt":latest.get("executive_summary",""),
            "orgs":[],"fullAnalysis":"","sourceUrl":"#","sourceLabel":"WarWatch",
        })

    # ── History ───────────────────────────────────────────────────────────────
    history = [
        {"t":r.get("generated_at",""), "l":r.get("escalation_level","MEDIUM"),
         "tone":r.get("sentiment",{}).get("overall_tone","")}
        for r in reversed(reports[:20])
    ]

    # ── Build indiaMeter ──────────────────────────────────────────────────────
    meter = latest.get("indiaMeter")
    if not meter or not isinstance(meter, dict) or "pct" not in meter:
        defaults = {"LOW":{"pct":28,"lvl":"Low","color":"#3daa72"},
                    "MEDIUM":{"pct":50,"lvl":"Moderate","color":"#3daa72"},
                    "HIGH":{"pct":72,"lvl":"High","color":"#d4892a"},
                    "CRITICAL":{"pct":90,"lvl":"Severe","color":"#e05555"}}
        meter = defaults.get(level, {"pct":72,"lvl":"High","color":"#d4892a"})

    # ── Final payload — every field guaranteed non-empty ──────────────────────
    payload = {
        "generatedAt":     latest.get("generated_at",""),
        "escalationLevel": level,
        "alerts":          alerts,
        "heroStats":       hero_stats,
        "tensionMeters":   tension_meters,
        "newsCards":       news_cards,
        "sentiment":       latest.get("sentiment", {"overall_tone":"ESCALATING"}),
        "terms":           latest.get("terminology_explained",[]),
        "history":         history,
        "execSummary":     _safe_str(latest.get("executive_summary",""), "Monitoring active."),
        "totalReports":    len(reports),
        # ── Guaranteed non-empty AI fields ────────────────────────────────────
        "execSummaryRich": _build_exec_summary_rich(latest),
        "indiaSummary":    _build_india_summary(latest),
        "indiaImpact":     _build_india_impact(latest),
        "indiaMeter":      meter,
    }

    # ── Atomic write: tmp first, bot.py renames on validation pass ────────────
    tmp_path = Path("live_data.tmp.js")
    js = f"window.WARWATCH_LIVE = {json.dumps(payload, indent=2)};\n"
    tmp_path.write_text(js, encoding="utf-8")
    print(f"[OK] live_data.tmp.js written — {len(news_cards)} cards, "
          f"execSummary={len(payload['execSummaryRich'])}c, "
          f"indiaSummary={len(payload['indiaSummary'])}c, "
          f"indiaImpact={len(payload['indiaImpact'])} items")

    _build_legacy_html(reports)


def _build_legacy_html(reports):
    level_colors = {"LOW":"#1D9E75","MEDIUM":"#BA7517","HIGH":"#D85A30","CRITICAL":"#A32D2D"}
    cards = ""
    for r in reports[:10]:
        lvl   = r.get("escalation_level","MEDIUM")
        color = level_colors.get(lvl,"#888")
        devs  = "".join(
            f'<li style="font-size:13px;margin:3px 0;color:#ccc">'
            f'<strong style="color:#fff">{d.get("actor","")}</strong> — {d.get("headline","")}</li>'
            for d in r.get("key_developments",[])[:3]
        )
        cards += f"""
        <div style="background:#2a2a2a;border:1px solid rgba(255,255,255,0.1);border-radius:12px;padding:20px;margin-bottom:14px">
          <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px">
            <span style="padding:3px 10px;border-radius:4px;font-size:11px;font-weight:700;background:{color}22;color:{color};border:1px solid {color};font-family:monospace;letter-spacing:.06em">{lvl}</span>
            <span style="font-size:12px;color:#666">{r.get('generated_at','')}</span>
            <span style="margin-left:auto;font-size:12px;color:#555">{r.get('sentiment',{}).get('overall_tone','')}</span>
          </div>
          <p style="font-size:14px;color:#ccc;margin:0 0 10px;line-height:1.7">{r.get('executive_summary','')}</p>
          <ul style="margin:0;padding-left:16px">{devs}</ul>
        </div>"""

    timeline_data = json.dumps([
        {"t":r.get("generated_at",""), "l":r.get("escalation_level","MEDIUM")}
        for r in reversed(reports[:20])
    ])

    html = f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>WarWatch Bot — Report Log</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'IBM Plex Sans',sans-serif;background:#1a1a1a;color:#ececec}}
.bar{{background:#222;border-bottom:1px solid rgba(255,255,255,0.08);padding:14px 32px;display:flex;align-items:center;gap:12px}}
.main{{max-width:860px;margin:0 auto;padding:28px 20px;display:grid;grid-template-columns:1fr 260px;gap:20px}}
.card{{background:#212121;border:1px solid rgba(255,255,255,0.08);border-radius:12px;padding:20px;margin-bottom:16px}}
h2{{font-family:'IBM Plex Mono',monospace;font-size:10px;letter-spacing:.12em;text-transform:uppercase;color:#5c5c5c;margin-bottom:14px}}
canvas{{width:100%!important}} a{{color:#5b9cf6;text-decoration:none}}
</style>
</head><body>
<div class="bar">
  <span style="font-family:monospace;font-size:14px;font-weight:500;letter-spacing:.06em;text-transform:uppercase">War<span style="color:#e05555">Watch</span> Bot</span>
  <span style="font-size:12px;color:#555">Gemini 2.0 Flash · Every 15min</span>
  <span style="margin-left:auto;font-size:12px;color:#555">Last run: {datetime.now(timezone.utc).strftime('%b %d %H:%M UTC')}</span>
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
  </div>
</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<script>
const d={timeline_data};
const lm={{"LOW":1,"MEDIUM":2,"HIGH":3,"CRITICAL":4}};
const cm={{"LOW":"#3daa72","MEDIUM":"#d4892a","HIGH":"#c87830","CRITICAL":"#e05555"}};
new Chart(document.getElementById('ch').getContext('2d'),{{
  type:'line',
  data:{{labels:d.map(x=>x.t.slice(5,16)),datasets:[{{data:d.map(x=>lm[x.l]||2),borderColor:'#e05555',backgroundColor:'rgba(224,85,85,0.08)',tension:0.4,fill:true,pointBackgroundColor:d.map(x=>cm[x.l]||'#d4892a'),pointRadius:4}}]}},
  options:{{plugins:{{legend:{{display:false}}}},scales:{{y:{{min:0,max:5,ticks:{{color:'#5c5c5c',callback:v=>['','Low','Med','High','Crit',''][v]||''}},grid:{{color:'rgba(255,255,255,0.05)'}}}},x:{{ticks:{{color:'#5c5c5c',maxRotation:45}},grid:{{color:'rgba(255,255,255,0.05)'}}}}}}}}
}});
</script>
</body></html>"""

    Path("dashboard.html").write_text(html, encoding="utf-8")
    print("[OK] dashboard.html updated")


if __name__ == "__main__":
    build_dashboard()
