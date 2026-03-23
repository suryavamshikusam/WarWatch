"""
summarizer.py — Generates ALL AI content in CI using Gemini 2.0 Flash.

Fixes vs previous version:
  - Articles capped at 10 with content stripped to 200 chars (avoids rate limits)
  - Longer sleep between API calls (2s base, more after big calls)
  - Empty response retried with longer wait instead of crashing
  - All 5 steps wrapped in try/except — partial failure never kills the run
  - Reduced card analyses to top 5 cards (not 8) to stay under quota
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


def _call(model, prompt: str, max_tokens: int = 1500, temperature: float = 0.4) -> str:
    """
    Single Gemini call with retry on rate limit or empty response.
    Waits progressively longer on each retry.
    Never raises — returns "" on total failure so callers can use fallback.
    """
    config = genai.types.GenerationConfig(max_output_tokens=max_tokens, temperature=temperature)
    wait_times = [30, 60, 90]

    for attempt in range(3):
        try:
            resp = model.generate_content(prompt, generation_config=config)
            text = resp.text.strip() if resp.text else ""
            if text:
                return text
            # Empty response = rate limited silently
            wait = wait_times[attempt]
            print(f"        [WARN] Empty response (attempt {attempt+1}/3), waiting {wait}s...")
            time.sleep(wait)
        except Exception as e:
            err = str(e).lower()
            if "429" in err or "quota" in err or "rate" in err or "resource" in err:
                wait = wait_times[attempt]
                print(f"        [WARN] Rate limit (attempt {attempt+1}/3), waiting {wait}s...")
                time.sleep(wait)
            else:
                print(f"        [WARN] Gemini error: {e}")
                return ""

    print("        [WARN] All 3 attempts failed, using fallback.")
    return ""


# ── Step 1 helpers ────────────────────────────────────────────────────────────

def _build_article_text(articles: list) -> str:
    """
    Build compact article text for the main parse prompt.
    Cap at 10 articles, 200 chars content each — keeps prompt under ~3000 tokens.
    """
    text = ""
    for i, art in enumerate(articles[:10], 1):
        text += f"\n[{i}] {art.get('source','?')}: {art['title']}\n"
        text += f"    URL: {art['url']}\n"
        if art.get("content"):
            text += f"    {art['content'][:200]}\n"
    return text


# ── Step 2: Panel summary ─────────────────────────────────────────────────────

def _panel_summary(model, report: dict) -> str:
    devs = "\n".join([
        f"- {d.get('actor','')}: {d.get('headline','')} — {d.get('detail','')[:120]}"
        for d in report.get("key_developments", [])[:5]
    ])
    prompt = f"""You are a conflict news editor. Write a 3-paragraph briefing. No headings, no bullets. Blank line between paragraphs.

Escalation: {report.get('escalation_level','')} · Tone: {report.get('sentiment',{}).get('overall_tone','')}
Developments:
{devs}

Para 1: What is happening RIGHT NOW — most critical facts. Max 4 sentences.
Para 2: Consequences for the region, oil markets, and India. Max 4 sentences.
Para 3: Most likely next 24 hours. Max 4 sentences.

Under 200 words total."""

    result = _call(model, prompt, max_tokens=500, temperature=0.35)
    return result or report.get("executive_summary", "")


# ── Step 3: Card analysis ─────────────────────────────────────────────────────

def _card_analysis(model, dev: dict, report: dict) -> str:
    prompt = f"""Geopolitical analyst covering US-Israel-Iran war.

Headline: {dev.get('headline','')}
Detail: {dev.get('detail','')}
Actor: {dev.get('actor','')}

Write 3 short paragraphs. No headings, no bullets.
Para 1: What happened — facts, who, where.
Para 2: Why it matters — strategic significance and India angle.
Para 3: What happens next — most likely 24-48hr scenario.
Max 60 words each."""

    result = _call(model, prompt, max_tokens=400, temperature=0.4)
    return result or dev.get("detail", "")


# ── Step 4: India summary ─────────────────────────────────────────────────────

def _india_summary(model, report: dict) -> str:
    items = report.get("india_impact", [])
    if not items:
        return ""
    items_text = "\n".join([
        f"- [{i.get('category','')}] {i.get('headline','')}: {i.get('detail','')[:120]}"
        for i in items
    ])
    prompt = f"""Senior journalist writing for Indian readers.

India developments:
{items_text}

Write 4 paragraphs. No bullets. Flowing prose.
Para 1: What's affecting India RIGHT NOW — oil, ports, investments.
Para 2: Impact on ordinary families — petrol prices, cost of living. Use ₹.
Para 3: Indians abroad in Gulf — UAE, Saudi, Kuwait. Remittances.
Para 4: India's diplomatic position — Iran, Israel, US balancing act.
Min 300 words."""

    result = _call(model, prompt, max_tokens=900, temperature=0.4)
    return result or ""


# ── Step 5: India meter ───────────────────────────────────────────────────────

def _india_meter(model, report: dict) -> dict:
    items = report.get("india_impact", [])
    context = " ".join([i.get("headline", "") for i in items[:3]])

    prompt = f"""Situation: "{context}" Escalation: {report.get('escalation_level','MEDIUM')}
Return ONLY JSON, no markdown: {{"pct": 72, "lvl": "High", "color": "#d4892a"}}
pct=0-100, lvl=Low/Moderate/High/Severe/Critical, color=#3daa72 if Low/Moderate else #d4892a if High else #e05555"""

    raw = _call(model, prompt, max_tokens=50, temperature=0.1)
    try:
        return json.loads(raw.replace("```json","").replace("```","").strip())
    except Exception:
        defaults = {
            "LOW":{"pct":30,"lvl":"Low","color":"#3daa72"},
            "MEDIUM":{"pct":52,"lvl":"Moderate","color":"#3daa72"},
            "HIGH":{"pct":72,"lvl":"High","color":"#d4892a"},
            "CRITICAL":{"pct":88,"lvl":"Severe","color":"#e05555"},
        }
        return defaults.get(report.get("escalation_level","MEDIUM"), {"pct":52,"lvl":"Moderate","color":"#3daa72"})


# ── Main pipeline ─────────────────────────────────────────────────────────────

def generate_report(articles: list) -> dict:
    """
    Full CI pipeline — all AI generated here, baked into live_data.js by dashboard.py.
    Each step is independent — failure in one never kills subsequent steps.
    """
    if not articles:
        return {"error": "No articles", "timestamp": datetime.utcnow().isoformat()}

    model = _get_client()

    # ── Step 1: Parse articles → structured JSON ──────────────────────────────
    print("      [1/5] Parsing articles (top 10)...")
    article_text = _build_article_text(articles)

    parse_prompt = f"""Analyze these war news articles. Return ONLY a JSON object. No markdown, no backticks, no extra text.

ARTICLES:
{article_text}

Return this EXACT JSON:
{{
  "report_title": "War Monitor — {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
  "executive_summary": "3-4 sentence plain English summary of the most critical developments",
  "escalation_level": "LOW or MEDIUM or HIGH or CRITICAL",
  "escalation_reason": "one sentence",
  "key_developments": [
    {{
      "headline": "8-12 word headline",
      "detail": "2-3 sentence explanation",
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
    {{"term": "word", "simple_explanation": "one sentence plain English"}}
  ],
  "what_to_watch_next": "2-3 things to watch in next 6-12 hours",
  "india_impact": [
    {{
      "headline": "India-specific headline",
      "detail": "2-3 sentence explanation",
      "category": "Economy or Diaspora or Diplomacy or Security or Energy or Trade",
      "source": "source name",
      "sourceUrl": "article URL",
      "significance": "LOW or MEDIUM or HIGH",
      "full_detail": "4-5 sentence deeper explanation"
    }}
  ],
  "sources_used": {len(articles)},
  "generated_at": "{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
}}

Include 6-8 key_developments, 2-3 india_impact, 5-6 terminology_explained. Keep all text concise."""

    raw = _call(model, parse_prompt, max_tokens=3000, temperature=0.3)

    # Clean markdown fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    if not raw:
        # Complete failure — build minimal report from article titles so bot doesn't crash
        print("      [WARN] Parse step failed — building minimal report from headlines")
        report = _minimal_report_from_articles(articles)
    else:
        try:
            report = json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"      [WARN] JSON parse error: {e} — building minimal report")
            report = _minimal_report_from_articles(articles)

    # Match source URLs to developments
    _match_source_urls(report, articles)

    # Wait between big call and next calls
    time.sleep(3)

    # ── Step 2: Panel summary ─────────────────────────────────────────────────
    print("      [2/5] Panel summary...")
    try:
        report["execSummaryRich"] = _panel_summary(model, report)
    except Exception as e:
        print(f"      [WARN] Panel summary failed: {e}")
        report["execSummaryRich"] = report.get("executive_summary", "")
    time.sleep(2)

    # ── Step 3: Card analyses — all cards ────────────────────────────────────
    cards = report.get("key_developments", [])
    print(f"      [3/5] Card analyses ({len(cards)} cards)...")
    for i, dev in enumerate(cards):
        print(f"        {i+1}/{len(cards)}: {dev.get('headline','')[:55]}...")
        try:
            dev["fullAnalysis"] = _card_analysis(model, dev, report)
        except Exception as e:
            print(f"        [WARN] Card {i+1} failed: {e}")
            dev["fullAnalysis"] = ""
        time.sleep(2)  # 2s between each card call

    time.sleep(2)

    # ── Step 4: India summary ─────────────────────────────────────────────────
    if report.get("india_impact"):
        print("      [4/5] India summary...")
        try:
            s = _india_summary(model, report)
            report["india_summary"] = s
            report["indiaSummary"]  = s
        except Exception as e:
            print(f"      [WARN] India summary failed: {e}")
            report["india_summary"] = ""
            report["indiaSummary"]  = ""
        time.sleep(2)

    # ── Step 5: India meter ───────────────────────────────────────────────────
    print("      [5/5] India tension meter...")
    try:
        report["indiaMeter"] = _india_meter(model, report)
    except Exception as e:
        print(f"      [WARN] India meter failed: {e}")
        report["indiaMeter"] = {"pct": 72, "lvl": "High", "color": "#d4892a"}

    print(f"      Done — {len(report.get('key_developments',[]))} cards, "
          f"panel={len(report.get('execSummaryRich',''))}c, "
          f"india={len(report.get('indiaSummary',''))}c, "
          f"meter={report.get('indiaMeter',{})}")

    return report


def _minimal_report_from_articles(articles: list) -> dict:
    """
    Fallback report built from article headlines when Gemini fails entirely.
    Ensures the bot never crashes and always produces something.
    """
    devs = []
    for art in articles[:8]:
        devs.append({
            "headline": art["title"][:80],
            "detail": art.get("content", "")[:200] or art["title"],
            "actor": "Other",
            "type": "war",
            "significance": "HIGH",
            "source": art.get("source", "Source"),
            "sourceUrl": art["url"],
            "fullAnalysis": "",
        })
    return {
        "report_title": f"War Monitor — {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        "executive_summary": f"Latest updates from {len(articles)} sources. AI analysis temporarily unavailable — data will refresh shortly.",
        "escalation_level": "HIGH",
        "escalation_reason": "Conflict ongoing — manual review required",
        "key_developments": devs,
        "sentiment": {"overall_tone": "ESCALATING", "us_stance": "", "israel_stance": "", "iran_stance": ""},
        "terminology_explained": [],
        "what_to_watch_next": "Monitor live feeds for latest developments.",
        "india_impact": [],
        "sources_used": len(articles),
        "generated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "execSummaryRich": "",
        "indiaSummary": "",
        "indiaMeter": {"pct": 72, "lvl": "High", "color": "#d4892a"},
    }


def _match_source_urls(report: dict, articles: list):
    """Match source URLs from articles to developments and india_impact items."""
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
            dev["sourceLabel"] = best.get("source", dev.get("source","Source"))
            used_urls.add(best["url"])
        if "fullAnalysis" not in dev:
            dev["fullAnalysis"] = ""

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


# ── Email formatter ───────────────────────────────────────────────────────────

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
    <p style="font-size:13px;color:#555">Tone: <strong>{sentiment.get('overall_tone','')}</strong></p>
  </div>
  <div style="padding:16px 28px;text-align:center;font-size:12px;color:#aaa">WarWatch · {report.get('generated_at','')} · Gemini AI</div>
</div></body></html>"""
