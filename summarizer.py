"""
summarizer.py — AI pipeline using Gemini (google-genai SDK).
"""

import os, json, time, random, re, certifi
from datetime import datetime

os.environ["SSL_CERT_FILE"]      = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

from google import genai
from google.genai import types

MODEL = "gemini-2.0-flash"

def _get_client():
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set in environment.")
    return genai.Client(api_key=api_key)

def _call(client, prompt: str, max_tokens: int = 1200, temperature: float = 0.4) -> str:
    base_waits = [8, 15, 30, 60]
    for attempt in range(4):
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    max_output_tokens=max_tokens,
                    temperature=temperature,
                )
            )
            text = (response.text or "").strip()
            if text:
                return text
            wait = base_waits[attempt] + random.uniform(0, 5)
            print(f"      [WARN] Empty response attempt {attempt+1}/4 — waiting {wait:.0f}s")
            time.sleep(wait)
        except Exception as e:
            err = str(e).lower()
            is_rate = any(x in err for x in ["429","quota","rate","resource","exhausted","limit"])
            wait = base_waits[attempt] + random.uniform(0, 8)
            if is_rate:
                print(f"      [WARN] Rate limit attempt {attempt+1}/4 — waiting {wait:.0f}s")
                time.sleep(wait)
            else:
                print(f"      [WARN] Gemini error attempt {attempt+1}/4: {str(e)[:120]}")
                if attempt < 3:
                    time.sleep(base_waits[attempt])
                else:
                    return ""
    print("      [WARN] All 4 attempts failed — using fallback.")
    return ""

def _repair_json(raw: str) -> str:
    raw = re.sub(r"^```[a-z]*\s*", "", raw.strip())
    raw = re.sub(r"\s*```$", "", raw.strip()).strip()
    raw = re.sub(r",\s*([\]}])", r"\1", raw)
    raw = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", raw)
    return raw

def _parse_json_safe(raw: str):
    if not raw: return None
    cleaned = _repair_json(raw)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if m:
            try: return json.loads(m.group())
            except: pass
    return None

def _build_article_text(articles, max_articles=10, max_content=250):
    lines = []
    for i, art in enumerate(articles[:max_articles], 1):
        lines.append(f"[{i}] {art.get('source','?')}: {art['title']}")
        lines.append(f"    URL: {art['url']}")
        content = (art.get("content") or "").strip()
        if content:
            lines.append(f"    {content[:max_content]}")
    return "\n".join(lines)

def _fallback_report(articles):
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    devs = []
    for art in articles[:8]:
        devs.append({
            "headline": art["title"][:80],
            "detail": (art.get("content") or art["title"])[:300],
            "actor": "Other", "type": "war", "significance": "HIGH",
            "source": art.get("source","Source"), "sourceUrl": art["url"], "fullAnalysis": "",
        })
    summary = (f"Latest updates from {len(articles)} sources covering the US-Israel-Iran conflict. "
               f"Monitoring {len(devs)} key developments. AI analysis refreshing shortly.")
    return {
        "report_title": f"War Monitor — {now}",
        "executive_summary": summary, "execSummaryRich": summary,
        "escalation_level": "HIGH", "escalation_reason": "Conflict ongoing.",
        "key_developments": devs,
        "sentiment": {"overall_tone":"ESCALATING","us_stance":"","israel_stance":"","iran_stance":""},
        "terminology_explained": [],
        "what_to_watch_next": "Monitor live feeds for breaking developments.",
        "india_impact": [], "indiaSummary": "", "indiaMeter": {"pct":72,"lvl":"High","color":"#d4892a"},
        "sources_used": len(articles), "generated_at": now,
    }

def _fallback_exec_summary(report, articles):
    devs = report.get("key_developments", [])
    if devs:
        headlines = ". ".join(d.get("headline","") for d in devs[:4] if d.get("headline"))
        return (f"Escalation: {report.get('escalation_level','HIGH')}. "
                f"Key developments: {headlines}. Situation remains active.")
    return f"Latest war monitor update. Headlines: {'. '.join(a['title'] for a in articles[:3])}."

def _fallback_india_summary(report):
    items = report.get("india_impact", [])
    if not items:
        return ("India continues to monitor the US-Israel-Iran conflict closely given its "
                "significant dependence on Gulf energy imports and the large Indian diaspora. "
                "Oil price volatility directly impacts petrol prices for Indian consumers.")
    parts = [i.get("full_detail") or i.get("detail") or i.get("headline","") for i in items[:4]]
    return " ".join(p for p in parts if p)

def _step1_parse(client, articles):
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    article_text = _build_article_text(articles, max_articles=10, max_content=250)
    prompt = f"""Analyze these war news articles about the US-Israel-Iran conflict.
Return ONLY a valid JSON object. No markdown, no backticks, no extra text.

ARTICLES:
{article_text}

Return this EXACT structure:
{{
  "report_title": "War Monitor — {now}",
  "executive_summary": "3-4 sentence plain English summary",
  "escalation_level": "HIGH",
  "escalation_reason": "one sentence why",
  "key_developments": [
    {{"headline":"8-12 word headline","detail":"2-3 sentence explanation","actor":"US or Israel or Iran or Hamas or Hezbollah or Houthis or Russia or China or Markets or Other","type":"war","significance":"HIGH","source":"source name","sourceUrl":"url"}}
  ],
  "sentiment": {{"overall_tone":"ESCALATING","us_stance":"one sentence","israel_stance":"one sentence","iran_stance":"one sentence"}},
  "terminology_explained": [{{"term":"word","simple_explanation":"one sentence"}}],
  "what_to_watch_next": "2-3 sentences",
  "india_impact": [
    {{"headline":"India-specific headline","detail":"2-3 sentences","category":"Energy","source":"source","sourceUrl":"url","significance":"HIGH","full_detail":"4-5 sentences"}}
  ],
  "sources_used": {len(articles)},
  "generated_at": "{now}"
}}
Rules: escalation_level must be LOW/MEDIUM/HIGH/CRITICAL. Include 6-8 key_developments, 2-4 india_impact, 4-6 terminology_explained."""

    raw = _call(client, prompt, max_tokens=3000, temperature=0.3)
    result = _parse_json_safe(raw)
    if result and result.get("key_developments"):
        print(f"      [OK] Parsed {len(result.get('key_developments',[]))} developments")
        return result
    print("      [WARN] Step 1 parse failed — fallback")
    return _fallback_report(articles)

def _step2_panel_summary(client, report):
    devs = report.get("key_developments", [])[:5]
    if not devs: return _fallback_exec_summary(report, [])
    dev_lines = "\n".join(f"- {d.get('actor','')}: {d.get('headline','')} — {d.get('detail','')[:150]}" for d in devs)
    prompt = f"""War correspondent. Write a 3-paragraph briefing. No headings. Blank line between paragraphs. Max 220 words.
Escalation: {report.get('escalation_level','HIGH')} | Tone: {report.get('sentiment',{}).get('overall_tone','ESCALATING')}
Developments:\n{dev_lines}
Para 1: What is happening NOW. Para 2: Regional/India impact. Para 3: Next 24h outlook."""
    result = _call(client, prompt, max_tokens=500, temperature=0.35)
    return result.strip() if result and len(result.strip()) > 50 else _fallback_exec_summary(report, [])

def _step3_card_analysis(client, dev):
    prompt = f"""Analyst. 3 short paragraphs, no headings, max 55 words each.
Headline: {dev.get('headline','')}
Detail: {dev.get('detail','')}
Para 1: Facts. Para 2: Strategic importance for India. Para 3: Likely outcome 24-48h."""
    result = _call(client, prompt, max_tokens=400, temperature=0.4)
    return result.strip() if result and len(result.strip()) > 40 else dev.get("detail", dev.get("headline",""))

def _step4_india_summary(client, report):
    items = report.get("india_impact", [])
    if not items: return _fallback_india_summary(report)
    items_text = "\n".join(f"- [{i.get('category','')}] {i.get('headline','')}: {i.get('detail','')[:150]}" for i in items)
    prompt = f"""Senior Indian journalist. 4 paragraphs for Indian readers. No bullets. Min 280 words.
{items_text}
Para 1: India NOW — oil, ports, investments. Para 2: Ordinary families — petrol prices, use ₹. Para 3: Indians in Gulf. Para 4: India's diplomatic balancing act."""
    result = _call(client, prompt, max_tokens=900, temperature=0.4)
    return result.strip() if result and len(result.strip()) > 100 else _fallback_india_summary(report)

def _step5_india_meter(client, report):
    level = report.get("escalation_level","HIGH")
    defaults = {"LOW":{"pct":28,"lvl":"Low","color":"#3daa72"},"MEDIUM":{"pct":50,"lvl":"Moderate","color":"#3daa72"},
                "HIGH":{"pct":72,"lvl":"High","color":"#d4892a"},"CRITICAL":{"pct":90,"lvl":"Severe","color":"#e05555"}}
    context = " ".join(i.get("headline","") for i in report.get("india_impact",[])[:3])
    prompt = f"""Conflict: US-Israel-Iran. Escalation: {level}. India context: "{context}"
Return ONLY valid JSON: {{"pct": 72, "lvl": "High", "color": "#d4892a"}}
pct: 0-100, lvl: Low/Moderate/High/Severe/Critical, color: #3daa72 for Low/Moderate, #d4892a for High, #e05555 for Severe/Critical"""
    raw = _call(client, prompt, max_tokens=60, temperature=0.1)
    result = _parse_json_safe(raw)
    if result and "pct" in result and "lvl" in result:
        try:
            result["pct"] = int(result["pct"])
            return result
        except: pass
    return defaults.get(level, defaults["HIGH"])

def _match_source_urls(report, articles):
    used = set()
    for dev in report.get("key_developments", []):
        words = [w for w in dev.get("headline","").lower().split() if len(w) > 3]
        best, best_score = None, -1
        for art in articles:
            score = sum(1 for w in words if w in art["title"].lower()) + (0.5 if art["url"] not in used else 0)
            if score > best_score: best_score, best = score, art
        if best:
            dev.setdefault("sourceUrl", best["url"])
            dev.setdefault("sourceLabel", best.get("source", dev.get("source","Source")))
            used.add(best["url"])
        dev.setdefault("fullAnalysis", "")

def _validate_and_fill(report, articles):
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    report.setdefault("report_title", f"War Monitor — {now}")
    report.setdefault("escalation_level", "HIGH")
    report.setdefault("escalation_reason", "Conflict ongoing.")
    report.setdefault("what_to_watch_next", "Monitor live feeds.")
    report.setdefault("sources_used", len(articles))
    report.setdefault("generated_at", now)
    if not report.get("executive_summary","").strip():
        report["executive_summary"] = _fallback_exec_summary(report, articles)
    if not report.get("execSummaryRich","").strip():
        report["execSummaryRich"] = report["executive_summary"]
    if not report.get("sentiment"):
        report["sentiment"] = {"overall_tone":"ESCALATING","us_stance":"","israel_stance":"","iran_stance":""}
    if not report.get("key_developments"):
        report["key_developments"] = _fallback_report(articles)["key_developments"]
    for dev in report.get("key_developments",[]):
        if not dev.get("fullAnalysis","").strip():
            dev["fullAnalysis"] = dev.get("detail", dev.get("headline",""))
    if not report.get("india_impact"):
        report["india_impact"] = [{"headline":"India Monitors Gulf Conflict","detail":"India's energy security tied to Gulf stability.","category":"Energy","significance":"HIGH","source":"WarWatch","sourceUrl":"#","full_detail":"India imports 85% of crude oil from Gulf. Strait of Hormuz disruption would immediately impact supply."}]
    if not report.get("indiaSummary","").strip():
        report["indiaSummary"] = _fallback_india_summary(report)
    if not report.get("indiaMeter"):
        report["indiaMeter"] = {"pct":72,"lvl":"High","color":"#d4892a"}
    if not report.get("terminology_explained"):
        report["terminology_explained"] = [
            {"term":"IRGC","simple_explanation":"Iran's elite Revolutionary Guard — controls missiles and drones."},
            {"term":"Strait of Hormuz","simple_explanation":"Narrow waterway — 20% of world oil passes through it."},
            {"term":"IDF","simple_explanation":"Israel Defense Forces — Israel's military."},
        ]

def generate_report(articles):
    if not articles:
        return _fallback_report([])
    print(f"      Articles received: {len(articles)}")
    try:
        client = _get_client()
    except RuntimeError as e:
        print(f"      [ERROR] {e}")
        return _fallback_report(articles)

    print("      [1/5] Parsing articles...")
    report = _step1_parse(client, articles)
    _match_source_urls(report, articles)
    time.sleep(1)

    print("      [2/5] Panel summary...")
    try: report["execSummaryRich"] = _step2_panel_summary(client, report)
    except Exception as e:
        print(f"      [WARN] Step 2: {e}")
        report["execSummaryRich"] = _fallback_exec_summary(report, articles)
    time.sleep(1)

    print("      [3/5] Card analyses...")
    for i, dev in enumerate(report.get("key_developments",[])[:5]):
        try:
            dev["fullAnalysis"] = _step3_card_analysis(client, dev)
            print(f"        [{i+1}/5] ✓")
        except Exception as e:
            dev["fullAnalysis"] = dev.get("detail","")
        time.sleep(1)
    for dev in report.get("key_developments",[])[5:]:
        dev.setdefault("fullAnalysis", dev.get("detail",""))
    time.sleep(1)

    print("      [4/5] India summary...")
    try: report["indiaSummary"] = _step4_india_summary(client, report)
    except Exception as e:
        print(f"      [WARN] Step 4: {e}")
        report["indiaSummary"] = _fallback_india_summary(report)
    time.sleep(1)

    print("      [5/5] India meter...")
    try: report["indiaMeter"] = _step5_india_meter(client, report)
    except Exception as e:
        report["indiaMeter"] = {"pct":72,"lvl":"High","color":"#d4892a"}

    _validate_and_fill(report, articles)
    print(f"\n      Pipeline complete: {report.get('escalation_level')} | {len(report.get('key_developments',[]))} devs")
    return report

def format_report_html(report):
    level_colors = {"LOW":"#1D9E75","MEDIUM":"#BA7517","HIGH":"#D85A30","CRITICAL":"#A32D2D"}
    level = report.get("escalation_level","HIGH")
    color = level_colors.get(level,"#888")
    devs_html = "".join(
        f'<tr><td style="padding:10px 12px;border-bottom:1px solid #eee"><strong>{d.get("headline","")}</strong>'
        f'<p style="margin:4px 0;color:#555;font-size:13px">{d.get("detail","")}</p></td></tr>'
        for d in report.get("key_developments",[])
    )
    return f"""<!DOCTYPE html><html><body style="font-family:Georgia,serif;background:#f5f5f0;padding:20px">
<div style="max-width:640px;margin:0 auto;background:#fff;border-radius:8px;overflow:hidden">
<div style="background:#1a1a1a;color:#fff;padding:24px 28px">
<div style="padding:4px 12px;background:{color}22;color:{color};font-size:12px;font-weight:700;border:1px solid {color};display:inline-block;margin-bottom:10px">{level}</div>
<h1 style="margin:0;font-size:20px">{report.get('report_title','War Monitor')}</h1></div>
<div style="padding:20px 28px;border-bottom:1px solid #eee">
<p style="font-size:15px;line-height:1.7">{report.get('execSummaryRich') or report.get('executive_summary','')}</p></div>
<div style="padding:20px 28px"><table style="width:100%;border-collapse:collapse">{devs_html}</table></div>
<div style="padding:16px 28px;text-align:center;font-size:12px;color:#aaa">WarWatch · {report.get('generated_at','')} · Gemini AI</div>
</div></body></html>"""
