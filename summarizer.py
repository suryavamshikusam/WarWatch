import os
import json
import certifi
from groq import Groq
from datetime import datetime

os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()


def _generate_full_analysis(client, dev, report):
    """Generate a 6-paragraph plain-English explanation for one development."""
    prompt = f"""You are a conflict journalist writing for everyone — from a curious 12-year-old to a grandparent.

Write a clear, warm explanation of this news development in exactly 6 paragraphs. No bullet points. No jargon without explanation. Plain flowing sentences only.

Headline: {dev.get('headline', '')}
Detail: {dev.get('detail', '')}
Context: {report.get('escalation_reason', '')}
Overall situation: {report.get('executive_summary', '')}

Write 6 paragraphs:
1. What happened — explain simply as if to a 12-year-old
2. Who is involved and why they did this
3. The backstory — what history led to this moment
4. What this means for ordinary people — civilians, economy, daily life
5. How the other side is responding
6. What happens next — possible outcomes, why it matters

Each paragraph 3-5 sentences. Warm, clear. Explain every acronym in brackets."""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1200,
            temperature=0.4
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[WARN] Full analysis failed: {e}")
        return ""


def _generate_india_summary(client, report):
    """Generate a 3-5 paragraph plain-English India impact summary."""
    india_items = report.get("india_impact", [])
    if not india_items:
        return ""

    items_text = "\n".join([
        f"- [{item.get('category','')}] {item.get('headline','')}: {item.get('detail','')}"
        for item in india_items
    ])

    prompt = f"""You are explaining how the US-Israel-Iran war affects India, writing for a general Indian audience — from a curious student to a grandparent.

Here are the India-related developments from the latest news:
{items_text}

Overall conflict context: {report.get('executive_summary', '')}

Write a clear, warm summary in exactly 3-5 paragraphs. No bullet points. Plain flowing sentences only.
- Para 1: What is happening right now that directly affects India
- Para 2: How it affects ordinary Indians — economy, travel, prices, jobs
- Para 3: What the Indian government is doing about it
- Para 4 (if relevant): The diplomatic angle — India's relationship with both sides
- Para 5 (if relevant): What to watch next for India

Each paragraph 2-4 sentences. Simple language, no jargon without explanation."""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800,
            temperature=0.4
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[WARN] India summary failed: {e}")
        return ""



def generate_report(articles):
    if not articles:
        return {"error": "No articles found", "timestamp": datetime.utcnow().isoformat()}

    article_text = ""
    for i, art in enumerate(articles[:15], 1):
        source = art.get("source", "Unknown")
        article_text += f"\n[{i}] SOURCE: {source} | HEADLINE: {art['title']}\n"
        if art.get("content"):
            article_text += f"    CONTENT: {art['content'][:500]}\n"

    prompt = f"""You are a conflict analyst monitoring the US-Israel-Iran war.
Analyze these articles from multiple news sources (NDTV, BBC, Iran International, TRT World, i24 News, The Hindu) and return ONLY a JSON object, no markdown, no extra text.

Pay special attention to any mentions of India — including Indian nationals abroad, Indian economy/oil/energy, Indian diplomacy, Indian citizens in the Middle East, or India's government response. If no India angle exists in the articles, return an empty array for india_impact.

ARTICLES:
{article_text}

Return this exact JSON structure:
{{
  "report_title": "War Monitor Report — {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
  "executive_summary": "2-3 sentence plain English summary",
  "escalation_level": "LOW or MEDIUM or HIGH or CRITICAL",
  "escalation_reason": "one sentence",
  "key_developments": [
    {{
      "headline": "short headline",
      "detail": "2 sentence explanation",
      "actor": "US or Israel or Iran or Hamas or Hezbollah or Other",
      "significance": "LOW or MEDIUM or HIGH",
      "source": "name of the news source this came from"
    }}
  ],
  "sentiment": {{
    "overall_tone": "TENSE or ESCALATING or DE-ESCALATING or VOLATILE or STABLE",
    "us_stance": "one sentence",
    "israel_stance": "one sentence",
    "iran_stance": "one sentence"
  }},
  "terminology_explained": [
    {{"term": "complex word", "simple_explanation": "simple definition"}}
  ],
  "what_to_watch_next": "2-3 things to monitor in next 6 hours",
  "india_impact": [
    {{
      "headline": "short headline about how this affects India",
      "detail": "2-3 sentence plain English explanation of the India angle",
      "category": "Economy or Diaspora or Diplomacy or Security or Energy or Other",
      "source": "name of the news source this came from",
      "significance": "LOW or MEDIUM or HIGH",
      "full_detail": "4-5 sentence deeper explanation for when the user clicks to expand"
    }}
  ],
  "sources_used": {len(articles)},
  "generated_at": "{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
}}"""

    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2000,
        temperature=0.3
    )

    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    report = json.loads(raw)

    # Generate full plain-English analysis for each key development
    print("      Generating full analysis for each development...")
    for dev in report.get("key_developments", []):
        dev["full_analysis"] = _generate_full_analysis(client, dev, report)

    # Generate India summary if there are India impact items
    if report.get("india_impact"):
        print("      Generating India summary...")
        report["india_summary"] = _generate_india_summary(client, report)

    return report


def generate_monthly_summary(reports):
    """Generate kid-friendly bullet points summarising the whole month."""
    if not reports:
        return []

    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

    all_events = ""
    for r in reports[:48]:
        all_events += f"\n[{r.get('generated_at','')}] Level: {r.get('escalation_level','')}\n"
        all_events += f"Summary: {r.get('executive_summary','')}\n"
        for dev in r.get("key_developments", [])[:3]:
            all_events += f"  - {dev.get('actor','')}: {dev.get('headline','')}\n"

    prompt = f"""You are explaining a war to a curious 10-year-old and their grandparent at the same time.

Based on these news reports from multiple sources (NDTV, BBC, Iran International, TRT World, i24 News, The Hindu), write exactly 8 bullet points summarising what has happened in the US-Israel-Iran conflict.

REPORTS:
{all_events[:3000]}

Rules:
- Each bullet point must be ONE clear simple sentence
- No jargon. Explain any hard word immediately in simple words
- Write like you're telling a story to a child — warm, clear, no scary language
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
        raw = raw.strip()
        return json.loads(raw)
    except Exception as e:
        print(f"[WARN] Monthly summary failed: {e}")
        return []


def format_report_html(report):
    level_colors = {"LOW": "#1D9E75", "MEDIUM": "#BA7517", "HIGH": "#D85A30", "CRITICAL": "#A32D2D"}
    level = report.get("escalation_level", "MEDIUM")
    color = level_colors.get(level, "#888")
    sentiment = report.get("sentiment", {})

    developments_html = ""
    for dev in report.get("key_developments", []):
        sig_colors = {"HIGH": "#D85A30", "MEDIUM": "#BA7517", "LOW": "#1D9E75"}
        sig_c = sig_colors.get(dev.get("significance", "LOW"), "#888")
        developments_html += f"""
        <tr><td style="padding:10px 12px;border-bottom:1px solid #eee;">
            <strong style="color:#111">{dev.get('headline','')}</strong>
            <span style="margin-left:8px;padding:2px 8px;border-radius:4px;font-size:11px;background:{sig_c}22;color:{sig_c}">{dev.get('actor','')}</span>
            <p style="margin:4px 0 0;color:#555;font-size:13px">{dev.get('detail','')}</p>
        </td></tr>"""

    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"></head><body style="font-family:Georgia,serif;background:#f5f5f0;margin:0;padding:20px">
<div style="max-width:640px;margin:0 auto;background:#fff;border-radius:8px;overflow:hidden">
  <div style="background:#1a1a1a;color:#fff;padding:24px 28px">
    <div style="display:inline-block;padding:4px 12px;border-radius:4px;background:{color}22;color:{color};font-size:12px;font-weight:700;border:1px solid {color};margin-bottom:10px">{level} ESCALATION</div>
    <h1 style="margin:0;font-size:20px;font-weight:400">{report.get('report_title','War Monitor')}</h1>
    <p style="margin:8px 0 0;color:#aaa;font-size:13px">Auto-generated · NDTV · Powered by Groq</p>
  </div>
  <div style="padding:20px 28px;border-bottom:1px solid #eee">
    <h3 style="font-size:13px;letter-spacing:.08em;text-transform:uppercase;color:#999;margin:0 0 12px">Executive Summary</h3>
    <p style="font-size:15px;line-height:1.7;color:#222;margin:0">{report.get('executive_summary','')}</p>
  </div>
  <div style="padding:20px 28px;border-bottom:1px solid #eee">
    <h3 style="font-size:13px;letter-spacing:.08em;text-transform:uppercase;color:#999;margin:0 0 12px">Key Developments</h3>
    <table style="width:100%;border-collapse:collapse">{developments_html}</table>
  </div>
  <div style="padding:20px 28px;border-bottom:1px solid #eee">
    <h3 style="font-size:13px;letter-spacing:.08em;text-transform:uppercase;color:#999;margin:0 0 12px">Sentiment</h3>
    <p style="font-size:13px;color:#555">Tone: <strong>{sentiment.get('overall_tone','')}</strong></p>
    <p style="font-size:13px;color:#555">US: {sentiment.get('us_stance','')}</p>
    <p style="font-size:13px;color:#555">Israel: {sentiment.get('israel_stance','')}</p>
    <p style="font-size:13px;color:#555">Iran: {sentiment.get('iran_stance','')}</p>
  </div>
  <div style="padding:16px 28px;text-align:center;font-size:12px;color:#aaa">
    War Monitor Bot · {report.get('generated_at','')} · NDTV.com
  </div>
</div></body></html>"""