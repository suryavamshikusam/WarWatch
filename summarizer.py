"""
summarizer.py — Generates ALL AI content in CI using Gemini 2.0 Flash.

Everything pre-generated server-side, baked into live_data.js.
Frontend reads static data — zero API calls, zero exposed keys, instant loads.

Per CI run generates:
  - Structured report JSON
  - Panel summary (3 paragraphs)     → report["execSummaryRich"]
  - Per-card analysis (3 paragraphs) → dev["fullAnalysis"] for each card
  - India summary (5 paragraphs)     → report["indiaSummary"]
  - India tension meter              → report["indiaMeter"] {pct, lvl, color}
"""

import os, json, time, certifi
from datetime import datetime

os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

import google.generativeai as genai

MODEL = "gemini-2.0-flash"


def _get_client():
    genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
    return genai.GenerativeModel(MODEL)


def _call(model, prompt: str, max_tokens: int = 2000, temperature: float = 0.4) -> str:
    config = genai.types.GenerationConfig(max_output_tokens=max_tokens, temperature=temperature)
    for attempt in range(3):
        try:
            return model.generate_content(prompt, generation_config=config).text.strip()
        except Exception as e:
            err = str(e).lower()
            if "429" in err or "quota" in err or "rate" in err:
                wait = (attempt + 1) * 30
                print(f"[WARN] Rate limit, waiting {wait}s...")
                time.sleep(wait)
            else:
                raise
    return ""


def _card_analysis(model, dev: dict, report: dict) -> str:
    """3-paragraph analysis for one news card. Stored in dev['fullAnalysis']."""
    prompt = f"""You are a senior geopolitical analyst covering the US-Israel-Iran war of 2026.

Headline: {dev.get('headline', '')}
Detail: {dev.get('detail', '')}
Actor: {dev.get('actor', '')}
Context: {report.get('escalation_reason', '')}

Write exactly 3 paragraphs. No headings, no bullets, plain prose only.

Para 1 — WHAT HAPPENED: Immediate military/political facts. Who, what, where, when.
Para 2 — WHY IT MATTERS: Strategic significance, regional impact, India angle (oil/diaspora/diplomacy).
Para 3 — WHAT'S NEXT: Two most likely scenarios in the next 24-48 hours.

50-70 words each. Specific and direct. Explain acronyms on first use."""

    try:
        return _call(model, prompt, max_tokens=600, temperature=0.4)
    except Exception as e:
        print(f"        [WARN] Card analysis failed: {e}")
        return dev.get("detail", "")


def _panel_summary(model, report: dict) -> str:
    """3-paragraph panel summary shown to every visitor on the left side."""
    devs = "\n".join([
        f"- {d.get('actor','')}: {d.get('headline','')} — {d.get('detail','')}"
        for d in report.get("key_developments", [])[:6]
    ])
    prompt = f"""You are the senior editor of a conflict monitoring service.

Escalation: {report.get('escalation_level','')} · Tone: {report.get('sentiment',{}).get('overall_tone','')}

Key developments:
{devs}

Write exactly 3 paragraphs. No headings, no bullets, plain prose. Blank line between paragraphs.

Para 1: What is happening RIGHT NOW — most critical developments last 12-24 hrs. Specific. Max 4 sentences.
Para 2: Broader consequences — region, oil markets, India specifically. Max 4 sentences.
Para 3: What is most likely next 24 hours. What to watch. Max 4 sentences.

Under 220 words total. No jargon without explanation."""

    try:
        return _call(model, prompt, max_tokens=700, temperature=0.35)
    except Exception as e:
        print(f"      [WARN] Panel summary failed: {e}")
        return report.get("executive_summary", "")


def _india_summary(model, report: dict) -> str:
    """5-paragraph India impact summary."""
    items = report.get("india_impact", [])
    if not items:
        return ""
    items_text = "\n".join([
        f"- [{i.get('category','')}] {i.get('headline','')}: {i.get('detail','')}"
        for i in items
    ])
    prompt = f"""You are a senior journalist writing for an Indian audience.

India developments:
{items_text}

Overall situation: {report.get('executive_summary','')}

Write exactly 5 paragraphs. No bullets. Only flowing prose.

Para 1: What's happening RIGHT NOW affecting India — oil routes, ports, investments at risk.
Para 2: The petrol pump and kitchen — how this hits ordinary Indian families. Real ₹ numbers.
Para 3: Indians abroad — UAE, Saudi Arabia, Kuwait, Qatar, Oman. Impact on them and families back home.
Para 4: India's diplomatic tightrope — Iran (Chabahar), Israel (defence), US (Quad). India's position.
Para 5: What India should watch — two or three key developments in coming days.

Warm, direct tone. Use ₹. Explain acronyms. Minimum 400 words."""

    try:
        return _call(model, prompt, max_tokens=1400, temperature=0.4)
    except Exception as e:
        print(f"      [WARN] India summary failed: {e}")
        return ""


def _india_meter(model, report: dict) -> dict:
    """India tension meter — {pct, lvl, color} stored in live_data.js."""
    items = report.get("india_impact", [])
    context = " ".join([i.get("headline", "") for i in items])
    context += " " + report.get("indiaSummary", "")[:200]

    prompt = f"""Situation: "{context}"
Escalation: {report.get('escalation_level','MEDIUM')}

Return ONLY valid JSON, no markdown:
{{"pct": 72, "lvl": "High", "color": "#d4892a"}}

pct = 0-100 integer India impact score.
lvl = one word: Low, Moderate, High, Severe, or Critical
color = "#3daa72" if Low/Moderate, "#d4892a" if High, "#e05555" if Severe/Critical"""

    try:
        raw = _call(model, prompt, max_tokens=60, temperature=0.1)
        return json.loads(raw.replace("```json","").replace("```","").strip())
    except Exception as e:
        print(f"      [WARN] India meter failed: {e}")
        defaults = {
            "LOW":{"pct":30,"lvl":"Low","color":"#3daa72"},
            "MEDIUM":{"pct":52,"lvl":"Moderate","color":"#3daa72"},
            "HIGH":{"pct":72,"lvl":"High","color":"#d4892a"},
            "CRITICAL":{"pct":88,"lvl":"Severe","color":"#e05555"},
        }
        return defaults.get(report.get("escalation_level","MEDIUM"), {"pct":52,"lvl":"Moderate","color":"#3daa72"})


def generate_report(articles: list) -> dict:
    """
    Full CI pipeline — generates everything, stores in report dict.
    dashboard.py then bakes it all into live_data.js.
    Frontend reads statically — no browser API calls at all.
    """
    if not articles:
        return {"error": "No articles", "timestamp": datetime.utcnow().isoformat()}

    model = _get_client()

    # ── 1. Parse articles into structured JSON ────────────────────────────────
    print("      [1/5] Parsing articles...")
    article_text = ""
    for i, art in enumerate(articles[:20], 1):
        article_text += f"\n[{i}] SOURCE: {art.get('source','?')} | URL: {art['url']}\n"
        article_text += f"    HEADLINE: {art['title']}\n"
        if art.get("content"):
            article_text += f"    CONTENT: {art['content'][:600]}\n"

    prompt = f"""Analyze these war news articles. Return ONLY a JSON object. No markdown, no backticks.

ARTICLES:
{article_text}

Return this EXACT structure:
{{
  "report_title": "War Monitor Report — {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
  "executive_summary": "3-4 sentence plain English summary",
  "escalation_level": "LOW or MEDIUM or HIGH or CRITICAL",
  "escalation_reason": "one sentence explaining the level",
  "key_developments": [
    {{
      "headline": "8-12 word headline",
      "detail": "3-4 sentence explanation of what happened, who, why it matters",
      "actor": "US or Israel or Iran or Hamas or Hezbollah or Pakistan or Russia or China or Houthis or Markets or Other",
      "type": "war or wider_war or markets or diplomacy or military or india",
      "significance": "LOW or MEDIUM or HIGH",
      "source": "source name",
      "sourceUrl": "article URL"
    }}
  ],
  "sentiment": {{
    "overall_tone": "TENSE or ESCALATING or DE-ESCALATING or VOLATILE or STABLE",
    "us_stance": "one sentence",
    "israel_stance": "one sentence",
    "iran_stance": "one sentence"
  }},
  "terminology_explained": [
    {{"term": "word", "simple_explanation": "plain English"}}
  ],
  "what_to_watch_next": "2-3 things to watch in next 6-12 hours",
  "india_impact": [
    {{
      "headline": "India-specific headline",
      "detail": "3 sentence explanation",
      "category": "Economy or Diaspora or Diplomacy or Security or Energy or Trade",
      "source": "source name",
      "sourceUrl": "article URL",
      "significance": "LOW or MEDIUM or HIGH",
      "full_detail": "5-6 sentence deeper explanation"
    }}
  ],
  "sources_used": {len(articles)},
  "generated_at": "{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
}}

8-10 key_developments, 2-4 india_impact, 8-10 terminology_explained."""

    raw = _call(model, prompt, max_tokens=4000, temperature=0.3)
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()
    if not raw:
        raise ValueError("Empty Gemini response — rate limited, will retry.")

    report = json.loads(raw)

    # Match source URLs
    used_urls = set()
    for dev in report.get("key_developments", []):
        words = [w for w in dev.get("headline","").lower().split() if len(w) > 3]
        best, best_score = None, -1
        for art in articles:
            score = sum(1 for w in words if w in art["title"].lower())
            if art["url"] not in used_urls: score += 0.5
            if score > best_score: best_score, best = score, art
        if best:
            dev["sourceUrl"]   = best["url"]
            dev["sourceLabel"] = best.get("source", dev.get("source", "Source"))
            used_urls.add(best["url"])
        dev["fullAnalysis"] = ""  # filled in step 3

    india_used = set()
    for item in report.get("india_impact", []):
        words = [w for w in item.get("headline","").lower().split() if len(w) > 3]
        best, best_score = None, -1
        for art in articles:
            score = sum(1 for w in words if w in art["title"].lower())
            if art["url"] not in india_used: score += 0.5
            if score > best_score: best_score, best = score, art
        if best:
            item["sourceUrl"] = best["url"]
            item["source"]    = best.get("source", item.get("source","Source"))
            india_used.add(best["url"])

    # ── 2. Panel summary ──────────────────────────────────────────────────────
    print("      [2/5] Panel summary...")
    report["execSummaryRich"] = _panel_summary(model, report)

    # ── 3. Per-card analyses ──────────────────────────────────────────────────
    cards = report.get("key_developments", [])[:8]
    print(f"      [3/5] Card analyses ({len(cards)} cards)...")
    for i, dev in enumerate(cards):
        print(f"        {i+1}/{len(cards)}: {dev.get('headline','')[:55]}...")
        dev["fullAnalysis"] = _card_analysis(model, dev, report)
        time.sleep(0.5)

    # ── 4. India summary ──────────────────────────────────────────────────────
    if report.get("india_impact"):
        print("      [4/5] India summary...")
        s = _india_summary(model, report)
        report["india_summary"] = s
        report["indiaSummary"]  = s

    # ── 5. India meter ────────────────────────────────────────────────────────
    print("      [5/5] India tension meter...")
    report["indiaMeter"] = _india_meter(model, report)

    return report


def format_report_html(report: dict) -> str:
    level_colors = {"LOW":"#1D9E75","MEDIUM":"#BA7517","HIGH":"#D85A30","CRITICAL":"#A32D2D"}
    level = report.get("escalation_level","MEDIUM")
    color = level_colors.get(level,"#888")
    sentiment = report.get("sentiment",{})

    devs_html = ""
    for dev in report.get("key_developments",[]):
        sc = {"HIGH":"#D85A30","MEDIUM":"#BA7517","LOW":"#1D9E75"}.get(dev.get("significance","LOW"),"#888")
        link = f'<a href="{dev["sourceUrl"]}" style="font-size:11px;color:#5b9cf6;text-decoration:none">Read → {dev.get("sourceLabel","Source")} ↗</a>' if dev.get("sourceUrl") else ""
        devs_html += f'<tr><td style="padding:10px 12px;border-bottom:1px solid #eee;"><strong style="color:#111">{dev.get("headline","")}</strong><span style="margin-left:8px;padding:2px 8px;border-radius:4px;font-size:11px;background:{sc}22;color:{sc}">{dev.get("actor","")}</span><p style="margin:4px 0 4px;color:#555;font-size:13px">{dev.get("detail","")}</p>{link}</td></tr>'

    india_html = ""
    for item in report.get("india_impact",[]):
        india_html += f'<tr><td style="padding:10px 12px;border-bottom:1px solid #eee;"><strong style="color:#111">{item.get("headline","")}</strong><span style="margin-left:8px;padding:2px 8px;border-radius:4px;font-size:10px;background:#1D9E7522;color:#1D9E75">{item.get("category","")}</span><p style="margin:4px 0 0;color:#555;font-size:13px">{item.get("detail","")}</p></td></tr>'

    india_section = f'<div style="padding:20px 28px;border-bottom:1px solid #eee"><h3 style="font-size:13px;letter-spacing:.08em;text-transform:uppercase;color:#999;margin:0 0 12px">India Impact</h3><table style="width:100%;border-collapse:collapse">{india_html}</table></div>' if india_html else ""

    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"></head>
<body style="font-family:Georgia,serif;background:#f5f5f0;margin:0;padding:20px">
<div style="max-width:640px;margin:0 auto;background:#fff;border-radius:8px;overflow:hidden">
  <div style="background:#1a1a1a;color:#fff;padding:24px 28px">
    <div style="display:inline-block;padding:4px 12px;border-radius:4px;background:{color}22;color:{color};font-size:12px;font-weight:700;border:1px solid {color};margin-bottom:10px">{level} ESCALATION</div>
    <h1 style="margin:0;font-size:20px;font-weight:400">{report.get('report_title','War Monitor')}</h1>
    <p style="margin:8px 0 0;color:#aaa;font-size:13px">WarWatch · Powered by Gemini</p>
  </div>
  <div style="padding:20px 28px;border-bottom:1px solid #eee">
    <h3 style="font-size:13px;letter-spacing:.08em;text-transform:uppercase;color:#999;margin:0 0 12px">Summary</h3>
    <p style="font-size:15px;line-height:1.7;color:#222;margin:0">{report.get('executive_summary','')}</p>
  </div>
  <div style="padding:20px 28px;border-bottom:1px solid #eee">
    <h3 style="font-size:13px;letter-spacing:.08em;text-transform:uppercase;color:#999;margin:0 0 12px">Key Developments</h3>
    <table style="width:100%;border-collapse:collapse">{devs_html}</table>
  </div>
  {india_section}
  <div style="padding:20px 28px;border-bottom:1px solid #eee">
    <p style="font-size:13px;color:#555">Tone: <strong>{sentiment.get('overall_tone','')}</strong> &nbsp;·&nbsp; US: {sentiment.get('us_stance','')} &nbsp;·&nbsp; Iran: {sentiment.get('iran_stance','')}</p>
  </div>
  <div style="padding:16px 28px;text-align:center;font-size:12px;color:#aaa">WarWatch · {report.get('generated_at','')} · Gemini AI</div>
</div></body></html>"""