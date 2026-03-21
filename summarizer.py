"""
summarizer.py — Generates conflict analysis reports using AI Summariser.

Produces deeply researched, long-form content:
  - Executive summary: 3 rich paragraphs
  - Per-development full analysis: 7 paragraphs each
  - India summary: 5-6 paragraphs
  - Each key development gets sourceUrl (NO external imageUrls — images removed)
  - India impact items get sourceUrl
"""

import os
import json
import time
import certifi
from groq import Groq
from datetime import datetime

os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()


def _generate_full_analysis(client, dev: dict, report: dict) -> str:
    """
    Generate a 7-paragraph deep-dive plain-English analysis for one development.
    Aimed at a general audience — clear, warm, no jargon without explanation.
    """
    prompt = f"""You are a senior conflict journalist writing for everyone — from a curious teenager to a retired grandparent who wants to understand the news.

Write a deep, warm, clear analysis of this war development in exactly 7 paragraphs. No bullet points. No lists. No headers. Only flowing prose paragraphs, each 4–6 sentences long.

Headline: {dev.get('headline', '')}
Detail: {dev.get('detail', '')}
Actor involved: {dev.get('actor', '')}
Overall conflict context: {report.get('escalation_reason', '')}
Bigger picture: {report.get('executive_summary', '')}

Write exactly 7 paragraphs in this order:

Paragraph 1 — THE SIMPLE VERSION: Explain what happened as if to a curious 12-year-old. Use an analogy if it helps. Make it feel real and immediate.

Paragraph 2 — WHO DID WHAT AND WHY: Identify the specific actors (explain who they are in plain English). Explain their motive — what did they hope to achieve? What were they responding to?

Paragraph 3 — THE BACKSTORY: What history and tensions led to this moment? Give context going back weeks or months. What earlier events made this possible or inevitable?

Paragraph 4 — WHAT THIS MEANS FOR ORDINARY PEOPLE: How does this affect civilians — prices, safety, daily life, travel, jobs? Be specific. Real examples.

Paragraph 5 — HOW THE OTHER SIDE IS RESPONDING: What has the opposing party said or done in response? What options do they have? Is this escalation or de-escalation?

Paragraph 6 — THE INDIA CONNECTION: How does this specifically affect India? Think about oil prices, Indian workers in the Gulf, Indian investments like Chabahar, Indian diplomacy, Indian economy.

Paragraph 7 — WHAT HAPPENS NEXT: What are the two or three most likely next moves? What should readers watch for in the next 24-48 hours? End with what the stakes really are.

Rules:
- Explain EVERY military acronym in plain English on first use (e.g., "the IRGC — Iran's elite Revolutionary Guard Corps")
- No jargon without explanation
- Warm, human tone — not cold or bureaucratic
- Each paragraph must be at least 4 full sentences
- Total output should be at least 600 words"""

    try:
        for attempt in range(3):
            try:
                response = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=2000,
                    temperature=0.45
                )
                return response.choices[0].message.content.strip()
            except Exception as e:
                if "rate_limit" in str(e).lower() or "429" in str(e):
                    wait = (attempt + 1) * 20
                    print(f"[WARN] Rate limit hit, waiting {wait}s...")
                    time.sleep(wait)
                else:
                    raise
        return ""
    except Exception as e:
        print(f"[WARN] Full analysis failed: {e}")
        return ""


def _generate_india_summary(client, report: dict) -> str:
    """
    Generate a 5-6 paragraph India impact summary.
    Written for a general Indian audience — concrete, specific, warm.
    """
    india_items = report.get("india_impact", [])
    if not india_items:
        return ""

    items_text = "\n".join([
        f"- [{item.get('category', '')}] {item.get('headline', '')}: {item.get('detail', '')}"
        for item in india_items
    ])

    prompt = f"""You are a senior journalist writing for an Indian audience — from students to working families to retirees. You are explaining how the US-Israel-Iran war is affecting India right now.

Here are the India-related developments from today's news:
{items_text}

Overall conflict situation: {report.get('executive_summary', '')}

Write a clear, warm, specific summary in exactly 5 to 6 paragraphs. No bullet points. No lists. Only flowing prose.

Paragraph 1 — WHAT'S HAPPENING RIGHT NOW that directly affects India. Be specific — which oil routes, which ports, which Indian investments are at risk.

Paragraph 2 — THE PETROL PUMP AND KITCHEN: How does this hit ordinary Indian families? Think: petrol prices, cooking gas, inflation, grocery prices. Use real rupee numbers where possible.

Paragraph 3 — INDIANS ABROAD: What about the millions of Indians living and working in the UAE, Saudi Arabia, Kuwait, Qatar, Oman? What does the latest development mean for them specifically? For their families back home?

Paragraph 4 — INDIA'S DIPLOMATIC TIGHTROPE: How is the Indian government navigating this? India has ties with Iran (Chabahar), Israel (defence contracts), the US (Quad), and Russia. What positions has India taken at the UN? What is Jaishankar doing?

Paragraph 5 — WHAT INDIA SHOULD WATCH: What are the two or three developments in this conflict that Indian citizens should pay closest attention to in the coming days? Why?

Paragraph 6 (optional) — WHAT THE GOVERNMENT IS DOING: Any emergency planning, fuel reserve orders, diplomatic calls, evacuation arrangements for Gulf workers.

Rules:
- Warm, direct tone — like a trusted journalist explaining to a friend
- Use ₹ for Indian currency
- Explain any acronym on first use
- Minimum 500 words total"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1600,
            temperature=0.4
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[WARN] India summary failed: {e}")
        return ""


def _generate_executive_summary_rich(client, report: dict) -> str:
    """
    Generate a 3-paragraph rich executive summary.
    Suitable for the main dashboard left panel — refreshed every 15 min by the browser.
    """
    devs_text = "\n".join([
        f"- {d.get('actor', '')}: {d.get('headline', '')} — {d.get('detail', '')}"
        for d in report.get("key_developments", [])[:6]
    ])

    prompt = f"""You are the senior editor of a conflict monitoring service. Write a clear, authoritative executive summary of the current US-Israel-Iran conflict situation.

Today's key developments:
{devs_text}

Escalation level: {report.get('escalation_level', '')}
Tone: {report.get('sentiment', {}).get('overall_tone', '')}

Write exactly 3 paragraphs of flowing prose. No bullet points. No headers.

Paragraph 1: What is happening RIGHT NOW — the most critical developments in the last 12-24 hours. Be specific. Name actors, places, numbers. Max 4 sentences.

Paragraph 2: What led to this point — the immediate chain of events. Context for someone who hasn't been following. Max 4 sentences.

Paragraph 3: What the stakes are — for oil markets, for India, for the region. What the next 24 hours could bring. Max 4 sentences.

Separate each paragraph with a blank line. Total output must be under 200 words. No headers, no bullets."""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=900,
            temperature=0.35
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[WARN] Rich exec summary failed: {e}")
        return report.get("executive_summary", "")


def generate_report(articles: list) -> dict:
    """
    Main entry point.
    1. Calls AI to analyze articles and extract structured JSON
    2. Generates 7-paragraph full analysis per development
    3. Generates 5-paragraph India summary
    4. Generates rich 3-paragraph executive summary
    5. Attaches sourceUrl to every development and India item (NO image URLs)
    """
    if not articles:
        return {"error": "No articles found", "timestamp": datetime.utcnow().isoformat()}

    # Build article text for the primary prompt
    article_text = ""
    for i, art in enumerate(articles[:20], 1):
        source = art.get("source", "Unknown")
        content = art.get("content", "")
        article_text += f"\n[{i}] SOURCE: {source} | URL: {art['url']}\n"
        article_text += f"    HEADLINE: {art['title']}\n"
        if content:
            article_text += f"    CONTENT: {content[:600]}\n"

    prompt = f"""You are a senior conflict analyst monitoring the US-Israel-Iran war.
Analyze these articles from 17 news sources and return ONLY a JSON object. No markdown. No extra text. No backticks.

Pay close attention to INDIA angles — Indian nationals abroad, Indian oil/energy, Indian diplomacy, Indian economy.
Also include INDIRECT war news: Pakistan statements, Russia/China positions, Houthi actions, oil markets, global diplomacy.

ARTICLES:
{article_text}

Return this EXACT JSON structure:
{{
  "report_title": "War Monitor Report — {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
  "executive_summary": "3-4 sentence plain English summary of the most critical developments",
  "escalation_level": "LOW or MEDIUM or HIGH or CRITICAL",
  "escalation_reason": "one clear sentence explaining why this level",
  "key_developments": [
    {{
      "headline": "punchy 8-12 word headline",
      "detail": "3-4 sentence clear explanation — what happened, who, where, why it matters",
      "actor": "US or Israel or Iran or Hamas or Hezbollah or Pakistan or Russia or China or Houthis or Markets or Other",
      "type": "war or wider_war or markets or diplomacy or military or india",
      "significance": "LOW or MEDIUM or HIGH",
      "source": "source name",
      "sourceUrl": "the article URL from the input"
    }}
  ],
  "sentiment": {{
    "overall_tone": "TENSE or ESCALATING or DE-ESCALATING or VOLATILE or STABLE",
    "us_stance": "one sentence on US position",
    "israel_stance": "one sentence on Israel position",
    "iran_stance": "one sentence on Iran position"
  }},
  "terminology_explained": [
    {{"term": "acronym or hard word", "simple_explanation": "plain English definition in 1-2 sentences"}}
  ],
  "what_to_watch_next": "2-3 specific things to watch in the next 6-12 hours",
  "india_impact": [
    {{
      "headline": "specific headline about India's stakes",
      "detail": "3 sentence plain English explanation",
      "category": "Economy or Diaspora or Diplomacy or Security or Energy or Trade",
      "source": "source name",
      "sourceUrl": "article URL",
      "significance": "LOW or MEDIUM or HIGH",
      "full_detail": "5-6 sentence deeper explanation for expanded view"
    }}
  ],
  "sources_used": {len(articles)},
  "generated_at": "{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
}}

Include 8-10 key_developments. Assign type precisely:
  war = direct US/Israel/Iran strikes or attacks
  wider_war = Pakistan/Russia/China/Houthi/proxy actions
  markets = oil prices/economy/sanctions/shipping
  diplomacy = ceasefire talks/UN/back-channels/statements
  military = naval movements/weapons/troop deployments/hardware
  india = anything directly affecting India (diaspora/energy/Chabahar/diplomacy)
Include 2-4 india_impact items. Include 8-10 terminology_explained items."""

    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=4000,
        temperature=0.3
    )

    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    report = json.loads(raw)

    # ── Enrich developments: full analysis + unique sourceUrl ─────────────────
    print("      Generating 7-paragraph full analysis for each development...")
    used_urls = set()

    for idx, dev in enumerate(report.get("key_developments", [])):
        if idx > 0:
            time.sleep(3)  # avoid Groq rate limits between calls
        dev["fullAnalysis"] = _generate_full_analysis(client, dev, report)

        headline = dev.get("headline", "").lower()
        headline_words = [w for w in headline.split() if len(w) > 3]

        # Score each article by how well it matches this development
        best_art = None
        best_score = -1
        for art in articles:
            art_title = art["title"].lower()
            score = sum(1 for w in headline_words if w in art_title)
            if art["url"] not in used_urls:
                score += 0.5
            if score > best_score:
                best_score = score
                best_art = art

        if best_art:
            dev["sourceUrl"]   = best_art["url"]
            dev["sourceLabel"] = best_art.get("source", dev.get("source", "Source"))
            used_urls.add(best_art["url"])

    # ── India impact: unique sourceUrl ────────────────────────────────────────
    india_used_urls = set()
    for item in report.get("india_impact", []):
        headline = item.get("headline", "").lower()
        headline_words = [w for w in headline.split() if len(w) > 3]
        best_art = None
        best_score = -1
        for art in articles:
            art_title = art["title"].lower()
            score = sum(1 for w in headline_words if w in art_title)
            if art["url"] not in india_used_urls:
                score += 0.5
            if score > best_score:
                best_score = score
                best_art = art
        if best_art:
            item["sourceUrl"] = best_art["url"]
            item["source"]    = best_art.get("source", item.get("source", "Source"))
            india_used_urls.add(best_art["url"])

    # ── Rich executive summary (3 paragraphs) ─────────────────────────────────
    print("      Generating rich executive summary...")
    report["execSummaryRich"] = _generate_executive_summary_rich(client, report)

    # ── India summary (5-6 paragraphs) ────────────────────────────────────────
    if report.get("india_impact"):
        print("      Generating India summary (5-6 paragraphs)...")
        _summary = _generate_india_summary(client, report)
        report["india_summary"] = _summary
        report["indiaSummary"] = _summary   # camelCase for frontend

    return report


def generate_monthly_summary(reports: list) -> list:
    """Generate 8 plain-English bullet points summarising the month."""
    if not reports:
        return []

    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

    all_events = ""
    for r in reports[:48]:
        all_events += f"\n[{r.get('generated_at', '')}] Level: {r.get('escalation_level', '')}\n"
        all_events += f"Summary: {r.get('executive_summary', '')}\n"
        for dev in r.get("key_developments", [])[:3]:
            all_events += f"  - {dev.get('actor', '')}: {dev.get('headline', '')}\n"

    prompt = f"""You are explaining a war to a curious 10-year-old and their grandparent at the same time.

Based on these news reports, write exactly 8 bullet points summarising what has happened in the US-Israel-Iran conflict.

REPORTS:
{all_events[:3000]}

Rules:
- Each bullet point must be ONE clear simple sentence
- No jargon. Explain any hard word immediately
- Write warmly, clearly — like telling a story
- Cover the most important things in roughly chronological order
- Each bullet starts with a relevant emoji

Return ONLY a JSON array of strings, no markdown, no extra text:
["🔥 Something happened...", "✈️ Then this happened..."]"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800,
            temperature=0.3
        )
        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())
    except Exception as e:
        print(f"[WARN] Monthly summary failed: {e}")
        return []


def format_report_html(report: dict) -> str:
    """Format a report as HTML email (used by emailer.py)."""
    level_colors = {"LOW": "#1D9E75", "MEDIUM": "#BA7517", "HIGH": "#D85A30", "CRITICAL": "#A32D2D"}
    level = report.get("escalation_level", "MEDIUM")
    color = level_colors.get(level, "#888")
    sentiment = report.get("sentiment", {})

    developments_html = ""
    for dev in report.get("key_developments", []):
        sig_colors = {"HIGH": "#D85A30", "MEDIUM": "#BA7517", "LOW": "#1D9E75"}
        sig_c = sig_colors.get(dev.get("significance", "LOW"), "#888")
        src_link = ""
        if dev.get("sourceUrl"):
            src_label = dev.get("source", "Source")
            src_link = f'<a href="{dev["sourceUrl"]}" style="font-size:11px;color:#5b9cf6;text-decoration:none">Read → {src_label} ↗</a>'
        developments_html += f"""
        <tr><td style="padding:10px 12px;border-bottom:1px solid #eee;">
            <strong style="color:#111">{dev.get('headline', '')}</strong>
            <span style="margin-left:8px;padding:2px 8px;border-radius:4px;font-size:11px;background:{sig_c}22;color:{sig_c}">{dev.get('actor', '')}</span>
            <p style="margin:4px 0 4px;color:#555;font-size:13px">{dev.get('detail', '')}</p>
            {src_link}
        </td></tr>"""

    india_html = ""
    for item in report.get("india_impact", []):
        india_html += f"""
        <tr><td style="padding:10px 12px;border-bottom:1px solid #eee;">
            <strong style="color:#111">{item.get('headline', '')}</strong>
            <span style="margin-left:8px;padding:2px 8px;border-radius:4px;font-size:10px;background:#1D9E7522;color:#1D9E75">{item.get('category', '')}</span>
            <p style="margin:4px 0 0;color:#555;font-size:13px">{item.get('detail', '')}</p>
        </td></tr>"""

    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"></head>
<body style="font-family:Georgia,serif;background:#f5f5f0;margin:0;padding:20px">
<div style="max-width:640px;margin:0 auto;background:#fff;border-radius:8px;overflow:hidden">
  <div style="background:#1a1a1a;color:#fff;padding:24px 28px">
    <div style="display:inline-block;padding:4px 12px;border-radius:4px;background:{color}22;color:{color};font-size:12px;font-weight:700;border:1px solid {color};margin-bottom:10px">{level} ESCALATION</div>
    <h1 style="margin:0;font-size:20px;font-weight:400">{report.get('report_title', 'War Monitor')}</h1>
    <p style="margin:8px 0 0;color:#aaa;font-size:13px">WarWatch · 17 sources · AI Summariser</p>
  </div>
  <div style="padding:20px 28px;border-bottom:1px solid #eee">
    <h3 style="font-size:13px;letter-spacing:.08em;text-transform:uppercase;color:#999;margin:0 0 12px">Executive Summary</h3>
    <p style="font-size:15px;line-height:1.7;color:#222;margin:0">{report.get('executive_summary', '')}</p>
  </div>
  <div style="padding:20px 28px;border-bottom:1px solid #eee">
    <h3 style="font-size:13px;letter-spacing:.08em;text-transform:uppercase;color:#999;margin:0 0 12px">Key Developments</h3>
    <table style="width:100%;border-collapse:collapse">{developments_html}</table>
  </div>
  {'<div style="padding:20px 28px;border-bottom:1px solid #eee"><h3 style="font-size:13px;letter-spacing:.08em;text-transform:uppercase;color:#999;margin:0 0 12px">India Impact</h3><table style="width:100%;border-collapse:collapse">' + india_html + '</table></div>' if india_html else ''}
  <div style="padding:20px 28px;border-bottom:1px solid #eee">
    <h3 style="font-size:13px;letter-spacing:.08em;text-transform:uppercase;color:#999;margin:0 0 12px">Sentiment</h3>
    <p style="font-size:13px;color:#555">Tone: <strong>{sentiment.get('overall_tone', '')}</strong></p>
    <p style="font-size:13px;color:#555">US: {sentiment.get('us_stance', '')}</p>
    <p style="font-size:13px;color:#555">Israel: {sentiment.get('israel_stance', '')}</p>
    <p style="font-size:13px;color:#555">Iran: {sentiment.get('iran_stance', '')}</p>
  </div>
  <div style="padding:16px 28px;text-align:center;font-size:12px;color:#aaa">
    WarWatch Bot · {report.get('generated_at', '')} · 17 sources
  </div>
</div></body></html>"""