"""
summarizer.py — Bulletproof AI pipeline using Gemini 2.0 Flash.

Design principles:
  - Every step is independent — failure in one NEVER affects others
  - Exponential backoff with jitter on rate limits
  - JSON auto-repair before giving up
  - Per-field fallback from raw article text
  - Chunked prompts — each call stays under 1000 tokens
  - Always returns a complete, non-empty report
"""

import os, json, time, random, re, certifi
from datetime import datetime

os.environ["SSL_CERT_FILE"]      = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

import google.generativeai as genai

MODEL = "gemini-2.0-flash"


# ── API client ────────────────────────────────────────────────────────────────

def _get_model():
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set in environment.")
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(MODEL)


# ── Core call with exponential backoff ────────────────────────────────────────

def _call(model, prompt: str, max_tokens: int = 1200, temperature: float = 0.4) -> str:
    """
    Call Gemini with exponential backoff + jitter.
    Never raises. Returns "" only after 4 attempts all fail.
    """
    config = genai.types.GenerationConfig(
        max_output_tokens=max_tokens,
        temperature=temperature
    )

    base_waits = [8, 15, 30, 60]  # exponential: 20 → 45 → 90 → 180

    for attempt in range(4):
        try:
            resp = model.generate_content(prompt, generation_config=config)
            text = (resp.text or "").strip()
            if text:
                return text
            # Silent empty — treat as soft rate limit
            wait = base_waits[attempt] + random.uniform(0, 8)
            print(f"      [WARN] Empty response attempt {attempt+1}/4 — waiting {wait:.0f}s")
            time.sleep(wait)

        except Exception as e:
            err = str(e).lower()
            is_rate = any(x in err for x in ["429","quota","rate","resource","exhausted","limit"])
            wait = base_waits[attempt] + random.uniform(0, 10)
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


# ── JSON repair ───────────────────────────────────────────────────────────────

def _repair_json(raw: str) -> str:
    """Strip markdown fences, fix common Gemini JSON mistakes."""
    # Strip ```json ... ``` fences
    raw = re.sub(r"^```[a-z]*\s*", "", raw.strip())
    raw = re.sub(r"\s*```$", "", raw.strip())
    raw = raw.strip()

    # Remove trailing commas before ] or }
    raw = re.sub(r",\s*([\]}])", r"\1", raw)

    # Remove control characters that break JSON
    raw = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", raw)

    return raw


def _parse_json_safe(raw: str) -> dict | None:
    """Try to parse JSON, return None on failure."""
    if not raw:
        return None
    cleaned = _repair_json(raw)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Try extracting first { ... } block
        m = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except Exception:
                pass
    return None


# ── Article text builder ──────────────────────────────────────────────────────

def _build_article_text(articles: list, max_articles: int = 10, max_content: int = 250) -> str:
    """Compact article text — keeps prompt well under token limits."""
    lines = []
    for i, art in enumerate(articles[:max_articles], 1):
        lines.append(f"[{i}] {art.get('source','?')}: {art['title']}")
        lines.append(f"    URL: {art['url']}")
        content = (art.get("content") or "").strip()
        if content:
            lines.append(f"    {content[:max_content]}")
    return "\n".join(lines)


# ── Fallback builders (never empty) ──────────────────────────────────────────

def _fallback_report(articles: list) -> dict:
    """Build a complete report from raw headlines when Gemini is totally down."""
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    devs = []
    for art in articles[:8]:
        devs.append({
            "headline":    art["title"][:80],
            "detail":      (art.get("content") or art["title"])[:300],
            "actor":       "Other",
            "type":        "war",
            "significance":"HIGH",
            "source":      art.get("source","Source"),
            "sourceUrl":   art["url"],
            "fullAnalysis":"",
        })
    summary = (
        f"Latest updates from {len(articles)} sources covering the US-Israel-Iran conflict. "
        f"Monitoring {len(devs)} key developments. AI analysis refreshing shortly."
    )
    return {
        "report_title":        f"War Monitor — {now}",
        "executive_summary":   summary,
        "execSummaryRich":     summary,
        "escalation_level":    "HIGH",
        "escalation_reason":   "Conflict ongoing — monitoring active.",
        "key_developments":    devs,
        "sentiment":           {"overall_tone":"ESCALATING","us_stance":"","israel_stance":"","iran_stance":""},
        "terminology_explained":[],
        "what_to_watch_next":  "Monitor live feeds for breaking developments.",
        "india_impact":        [],
        "indiaSummary":        "",
        "indiaMeter":          {"pct":72,"lvl":"High","color":"#d4892a"},
        "sources_used":        len(articles),
        "generated_at":        now,
    }


def _fallback_exec_summary(report: dict, articles: list) -> str:
    """Build exec summary from headlines if Gemini failed."""
    devs = report.get("key_developments", [])
    if devs:
        headlines = ". ".join(d.get("headline","") for d in devs[:4] if d.get("headline"))
        level = report.get("escalation_level","HIGH")
        tone  = report.get("sentiment",{}).get("overall_tone","ESCALATING")
        return (
            f"Escalation level: {level}. Tone: {tone}. "
            f"Key developments: {headlines}. "
            f"Situation remains active across the US-Israel-Iran conflict zone. "
            f"India's energy imports and Gulf diaspora are monitoring closely."
        )
    titles = ". ".join(a["title"] for a in articles[:3])
    return f"Latest war monitor update. Recent headlines: {titles}."


def _fallback_india_summary(report: dict) -> str:
    """Build India summary from india_impact items if Gemini failed."""
    items = report.get("india_impact", [])
    if not items:
        return (
            "India continues to monitor the US-Israel-Iran conflict closely given its "
            "significant dependence on Gulf energy imports and the large Indian diaspora "
            "in the region. Oil price volatility directly impacts petrol and diesel prices "
            "for Indian consumers. The government is in active diplomatic contact with all "
            "parties to protect Indian interests and ensure safe passage for Indian nationals."
        )
    parts = []
    for item in items[:4]:
        h = item.get("headline","")
        d = item.get("detail","")
        if h or d:
            parts.append(f"{h}. {d}" if h and d else h or d)
    return " ".join(parts) if parts else (
        "India is closely tracking conflict developments for impact on energy, "
        "trade, and its diaspora in the Gulf region."
    )


# ── Step 1: Parse articles → structured JSON ──────────────────────────────────

def _step1_parse(model, articles: list) -> dict:
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    article_text = _build_article_text(articles, max_articles=10, max_content=250)

    prompt = f"""Analyze these war news articles about the US-Israel-Iran conflict.
Return ONLY a valid JSON object. No markdown, no backticks, no extra text.

ARTICLES:
{article_text}

Return this EXACT structure:
{{
  "report_title": "War Monitor — {now}",
  "executive_summary": "3-4 sentence plain English summary of the most critical developments",
  "escalation_level": "HIGH",
  "escalation_reason": "one sentence why",
  "key_developments": [
    {{
      "headline": "8-12 word headline",
      "detail": "2-3 sentence explanation",
      "actor": "US or Israel or Iran or Hamas or Hezbollah or Houthis or Russia or China or Markets or Other",
      "type": "war",
      "significance": "HIGH",
      "source": "source name",
      "sourceUrl": "url"
    }}
  ],
  "sentiment": {{
    "overall_tone": "ESCALATING",
    "us_stance": "one sentence",
    "israel_stance": "one sentence",
    "iran_stance": "one sentence"
  }},
  "terminology_explained": [
    {{"term": "word", "simple_explanation": "one sentence"}}
  ],
  "what_to_watch_next": "2-3 sentences on what to watch next 6-12 hours",
  "india_impact": [
    {{
      "headline": "India-specific headline",
      "detail": "2-3 sentence explanation",
      "category": "Energy",
      "source": "source name",
      "sourceUrl": "url",
      "significance": "HIGH",
      "full_detail": "4-5 sentence deeper explanation"
    }}
  ],
  "sources_used": {len(articles)},
  "generated_at": "{now}"
}}

Rules:
- escalation_level must be: LOW, MEDIUM, HIGH, or CRITICAL
- overall_tone must be: TENSE, ESCALATING, DE-ESCALATING, VOLATILE, or STABLE
- significance must be: LOW, MEDIUM, or HIGH
- Include 6-8 key_developments, 2-4 india_impact items, 4-6 terminology_explained
- All text must be factual based on the articles provided"""

    raw = _call(model, prompt, max_tokens=3000, temperature=0.3)
    result = _parse_json_safe(raw)

    if result and result.get("key_developments"):
        print(f"      [OK] Parsed {len(result.get('key_developments',[]))} developments, "
              f"{len(result.get('india_impact',[]))} India items")
        return result

    print("      [WARN] Step 1 JSON parse failed — using fallback report")
    return _fallback_report(articles)


# ── Step 2: Panel summary (3-paragraph briefing) ──────────────────────────────

def _step2_panel_summary(model, report: dict) -> str:
    devs = report.get("key_developments", [])[:5]
    if not devs:
        return _fallback_exec_summary(report, [])

    dev_lines = "\n".join(
        f"- {d.get('actor','')}: {d.get('headline','')} — {d.get('detail','')[:150]}"
        for d in devs
    )
    level = report.get("escalation_level","HIGH")
    tone  = report.get("sentiment",{}).get("overall_tone","ESCALATING")

    prompt = f"""You are a conflict news editor. Write a 3-paragraph briefing for the WarWatch dashboard.
No headings. No bullets. Blank line between paragraphs. Max 220 words total.

Escalation: {level} | Tone: {tone}
Key developments:
{dev_lines}

Para 1: What is happening RIGHT NOW — most critical facts. Max 4 sentences.
Para 2: Impact on the region, oil markets, and India. Max 4 sentences.
Para 3: Most likely developments in the next 24 hours. Max 3 sentences.

Write in confident, factual broadcast English. No speculation."""

    result = _call(model, prompt, max_tokens=500, temperature=0.35)
    if result and len(result.strip()) > 50:
        return result.strip()

    print("      [WARN] Step 2 failed — using fallback exec summary")
    return _fallback_exec_summary(report, [])


# ── Step 3: Card analysis for top developments ────────────────────────────────

def _step3_card_analysis(model, dev: dict) -> str:
    prompt = f"""Geopolitical analyst. Write 3 short paragraphs about this development.
No headings. No bullets. Max 55 words each paragraph.

Headline: {dev.get('headline','')}
Detail: {dev.get('detail','')}
Actor: {dev.get('actor','')}

Para 1: What happened — facts, who, where, when.
Para 2: Why it matters strategically and for India.
Para 3: Most likely outcome in the next 24-48 hours."""

    result = _call(model, prompt, max_tokens=400, temperature=0.4)
    if result and len(result.strip()) > 40:
        return result.strip()
    # Fallback: use the detail field
    return dev.get("detail", dev.get("headline", ""))


# ── Step 4: India summary ─────────────────────────────────────────────────────

def _step4_india_summary(model, report: dict) -> str:
    items = report.get("india_impact", [])
    if not items:
        return _fallback_india_summary(report)

    items_text = "\n".join(
        f"- [{i.get('category','')}] {i.get('headline','')}: {i.get('detail','')[:150]}"
        for i in items
    )

    prompt = f"""Senior Indian journalist. Write 4 paragraphs for Indian readers about war impact on India.
No bullets. Flowing prose. Min 280 words.

India developments:
{items_text}

Para 1: What is affecting India RIGHT NOW — oil, ports, investments.
Para 2: Impact on ordinary Indian families — petrol prices, cost of living. Use ₹ symbols.
Para 3: Indians abroad in Gulf — UAE, Saudi Arabia, Kuwait. Remittances at risk.
Para 4: India's diplomatic balancing act — Iran, Israel, and US relations."""

    result = _call(model, prompt, max_tokens=900, temperature=0.4)
    if result and len(result.strip()) > 100:
        return result.strip()

    print("      [WARN] Step 4 failed — using fallback India summary")
    return _fallback_india_summary(report)


# ── Step 5: India tension meter ───────────────────────────────────────────────

def _step5_india_meter(model, report: dict) -> dict:
    level   = report.get("escalation_level","HIGH")
    items   = report.get("india_impact",[])
    context = " ".join(i.get("headline","") for i in items[:3])

    # Hardcoded defaults by escalation level — used if Gemini fails
    defaults = {
        "LOW":      {"pct":28,"lvl":"Low",      "color":"#3daa72"},
        "MEDIUM":   {"pct":50,"lvl":"Moderate", "color":"#3daa72"},
        "HIGH":     {"pct":72,"lvl":"High",     "color":"#d4892a"},
        "CRITICAL": {"pct":90,"lvl":"Severe",   "color":"#e05555"},
    }

    prompt = f"""Conflict: US-Israel-Iran war. Escalation: {level}.
India context: "{context}"

Return ONLY valid JSON (no markdown, no backticks):
{{"pct": 72, "lvl": "High", "color": "#d4892a"}}

Rules:
- pct: 0-100 integer representing India's risk exposure
- lvl: exactly one of: Low, Moderate, High, Severe, Critical
- color: #3daa72 for Low/Moderate, #d4892a for High, #e05555 for Severe/Critical"""

    raw    = _call(model, prompt, max_tokens=60, temperature=0.1)
    result = _parse_json_safe(raw)

    if result and "pct" in result and "lvl" in result and "color" in result:
        # Validate pct is a number
        try:
            result["pct"] = int(result["pct"])
            return result
        except (ValueError, TypeError):
            pass

    print(f"      [WARN] Step 5 meter parse failed — using default for {level}")
    return defaults.get(level, defaults["HIGH"])


# ── Source URL matcher ────────────────────────────────────────────────────────

def _match_source_urls(report: dict, articles: list):
    """Match best-fit article URLs to developments and india_impact items."""
    used_urls: set = set()

    for dev in report.get("key_developments", []):
        words = [w for w in dev.get("headline","").lower().split() if len(w) > 3]
        best, best_score = None, -1
        for art in articles:
            score = sum(1 for w in words if w in art["title"].lower())
            if art["url"] not in used_urls:
                score += 0.5
            if score > best_score:
                best_score, best = score, art
        if best:
            dev.setdefault("sourceUrl",   best["url"])
            dev.setdefault("sourceLabel", best.get("source", dev.get("source","Source")))
            used_urls.add(best["url"])
        dev.setdefault("fullAnalysis", "")

    india_used: set = set()
    for item in report.get("india_impact", []):
        words = [w for w in item.get("headline","").lower().split() if len(w) > 3]
        best, best_score = None, -1
        for art in articles:
            score = sum(1 for w in words if w in art["title"].lower())
            if art["url"] not in india_used:
                score += 0.5
            if score > best_score:
                best_score, best = score, art
        if best:
            item.setdefault("sourceUrl", best["url"])
            item.setdefault("source",    best.get("source","Source"))
            india_used.add(best["url"])


# ── Main pipeline ─────────────────────────────────────────────────────────────

def generate_report(articles: list) -> dict:
    """
    Full AI pipeline. Always returns a complete, non-empty report.
    Each step is independent — failure in one never kills the next.
    """
    if not articles:
        print("      [WARN] No articles — returning minimal report")
        return _fallback_report([])

    print(f"      Articles received: {len(articles)}")

    try:
        model = _get_model()
    except RuntimeError as e:
        print(f"      [ERROR] {e}")
        return _fallback_report(articles)

    # ── Step 1: Parse articles ────────────────────────────────────────────────
    print("      [1/5] Parsing articles...")
    report = _step1_parse(model, articles)
    _match_source_urls(report, articles)
    time.sleep(1)

    # ── Step 2: Panel summary ─────────────────────────────────────────────────
    print("      [2/5] Panel summary...")
    try:
        report["execSummaryRich"] = _step2_panel_summary(model, report)
    except Exception as e:
        print(f"      [WARN] Step 2 exception: {e}")
        report["execSummaryRich"] = _fallback_exec_summary(report, articles)
    time.sleep(1)

    # Guarantee execSummaryRich is never empty
    if not report.get("execSummaryRich","").strip():
        report["execSummaryRich"] = _fallback_exec_summary(report, articles)

    # ── Step 3: Card analyses (top 5) ────────────────────────────────────────
    cards = report.get("key_developments",[])
    print(f"      [3/5] Card analyses ({min(5,len(cards))} cards)...")
    for i, dev in enumerate(cards[:5]):
        try:
            dev["fullAnalysis"] = _step3_card_analysis(model, dev)
            print(f"        [{i+1}/5] ✓ {dev.get('headline','')[:55]}")
        except Exception as e:
            print(f"        [{i+1}/5] WARN: {e} — using detail fallback")
            dev["fullAnalysis"] = dev.get("detail","")
        time.sleep(1)

    # Remaining cards get detail as analysis
    for dev in cards[5:]:
        dev.setdefault("fullAnalysis", dev.get("detail",""))

    time.sleep(1)

    # ── Step 4: India summary ─────────────────────────────────────────────────
    print("      [4/5] India summary...")
    try:
        india_sum = _step4_india_summary(model, report)
    except Exception as e:
        print(f"      [WARN] Step 4 exception: {e}")
        india_sum = _fallback_india_summary(report)

    # Guarantee indiaSummary is never empty
    report["indiaSummary"] = india_sum if india_sum.strip() else _fallback_india_summary(report)
    report["india_summary"] = report["indiaSummary"]
    time.sleep(1)

    # ── Step 5: India meter ───────────────────────────────────────────────────
    print("      [5/5] India tension meter...")
    try:
        report["indiaMeter"] = _step5_india_meter(model, report)
    except Exception as e:
        print(f"      [WARN] Step 5 exception: {e}")
        report["indiaMeter"] = {"pct":72,"lvl":"High","color":"#d4892a"}

    # ── Final validation — guarantee all required fields exist ────────────────
    _validate_and_fill(report, articles)

    print(f"\n      Pipeline complete:")
    print(f"        escalation  : {report.get('escalation_level')}")
    print(f"        developments: {len(report.get('key_developments',[]))}")
    print(f"        india items : {len(report.get('india_impact',[]))}")
    print(f"        exec summary: {len(report.get('execSummaryRich',''))} chars")
    print(f"        india summ  : {len(report.get('indiaSummary',''))} chars")
    print(f"        india meter : {report.get('indiaMeter')}")

    return report


def _validate_and_fill(report: dict, articles: list):
    """
    Final safety net — ensure every field the frontend needs is non-empty.
    Called after all steps so nothing is ever missing from live_data.js.
    """
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    # Scalar fields
    report.setdefault("report_title",       f"War Monitor — {now}")
    report.setdefault("escalation_level",   "HIGH")
    report.setdefault("escalation_reason",  "Conflict ongoing.")
    report.setdefault("what_to_watch_next", "Monitor live feeds for breaking developments.")
    report.setdefault("sources_used",       len(articles))
    report.setdefault("generated_at",       now)

    # executive_summary
    if not report.get("executive_summary","").strip():
        report["executive_summary"] = _fallback_exec_summary(report, articles)

    # execSummaryRich
    if not report.get("execSummaryRich","").strip():
        report["execSummaryRich"] = report["executive_summary"]

    # sentiment
    if not report.get("sentiment"):
        report["sentiment"] = {
            "overall_tone": "ESCALATING",
            "us_stance":    "The US maintains active military posture in the region.",
            "israel_stance":"Israel continues coordinated operations against Iranian targets.",
            "iran_stance":  "Iran signals readiness to respond to further escalation.",
        }

    # key_developments — must have at least 1
    if not report.get("key_developments"):
        report["key_developments"] = _fallback_report(articles)["key_developments"]

    # Ensure every development has fullAnalysis
    for dev in report.get("key_developments",[]):
        if not dev.get("fullAnalysis","").strip():
            dev["fullAnalysis"] = dev.get("detail", dev.get("headline",""))

    # india_impact — build from articles if empty
    if not report.get("india_impact"):
        report["india_impact"] = [{
            "headline":    "India Monitors Gulf Conflict for Energy Security",
            "detail":      "India's energy security is directly tied to Gulf stability. The government is tracking oil price movements and shipping routes closely.",
            "category":    "Energy",
            "significance":"HIGH",
            "source":      "WarWatch Monitor",
            "sourceUrl":   "#",
            "full_detail": "India imports over 85% of its crude oil, with a significant share from the Gulf region. Any disruption to shipping through the Strait of Hormuz would immediately affect supply chains. The Indian government is in contact with all parties and has contingency plans for supply disruptions.",
        }]

    # indiaSummary
    if not report.get("indiaSummary","").strip():
        report["indiaSummary"] = _fallback_india_summary(report)

    # indiaMeter
    if not report.get("indiaMeter"):
        report["indiaMeter"] = {"pct":72,"lvl":"High","color":"#d4892a"}

    # terminology_explained — at least a few terms
    if not report.get("terminology_explained"):
        report["terminology_explained"] = [
            {"term":"IRGC",           "simple_explanation":"Iran's Islamic Revolutionary Guard Corps — the elite military force that controls Iran's missile and drone arsenal."},
            {"term":"Strait of Hormuz","simple_explanation":"A narrow waterway through which ~20% of the world's oil supply passes — Iran can threaten to close it."},
            {"term":"IDF",            "simple_explanation":"Israel Defense Forces — Israel's military, currently operating against Iranian targets."},
        ]


# ── Email formatter ───────────────────────────────────────────────────────────

def format_report_html(report: dict) -> str:
    level_colors = {"LOW":"#1D9E75","MEDIUM":"#BA7517","HIGH":"#D85A30","CRITICAL":"#A32D2D"}
    level  = report.get("escalation_level","HIGH")
    color  = level_colors.get(level,"#888")
    sentiment = report.get("sentiment",{})

    devs_html = ""
    for dev in report.get("key_developments",[]):
        sc   = {"HIGH":"#D85A30","MEDIUM":"#BA7517","LOW":"#1D9E75"}.get(dev.get("significance","LOW"),"#888")
        link = (f'<a href="{dev["sourceUrl"]}" style="font-size:11px;color:#5b9cf6;text-decoration:none">'
                f'Read → {dev.get("sourceLabel","Source")} ↗</a>') if dev.get("sourceUrl","#") != "#" else ""
        devs_html += (
            f'<tr><td style="padding:10px 12px;border-bottom:1px solid #eee;">'
            f'<strong style="color:#111">{dev.get("headline","")}</strong>'
            f'<span style="margin-left:8px;padding:2px 8px;border-radius:4px;font-size:11px;'
            f'background:{sc}22;color:{sc}">{dev.get("actor","")}</span>'
            f'<p style="margin:4px 0 4px;color:#555;font-size:13px">{dev.get("detail","")}</p>'
            f'{link}</td></tr>'
        )

    india_html = ""
    for item in report.get("india_impact",[]):
        india_html += (
            f'<tr><td style="padding:10px 12px;border-bottom:1px solid #eee;">'
            f'<strong style="color:#111">{item.get("headline","")}</strong>'
            f'<span style="margin-left:8px;padding:2px 8px;border-radius:4px;font-size:10px;'
            f'background:#1D9E7522;color:#1D9E75">{item.get("category","")}</span>'
            f'<p style="margin:4px 0 0;color:#555;font-size:13px">{item.get("detail","")}</p>'
            f'</td></tr>'
        )

    india_section = (
        f'<div style="padding:20px 28px;border-bottom:1px solid #eee">'
        f'<h3 style="font-size:13px;letter-spacing:.08em;text-transform:uppercase;color:#999;margin:0 0 12px">India Impact</h3>'
        f'<table style="width:100%;border-collapse:collapse">{india_html}</table></div>'
    ) if india_html else ""

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
    <p style="font-size:15px;line-height:1.7;color:#222;margin:0">{report.get('execSummaryRich') or report.get('executive_summary','')}</p>
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
