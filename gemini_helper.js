/**
 * gemini_helper.js
 * Drop-in replacement for all Groq API calls.
 * Uses Gemini 2.0 Flash via the Google Generative Language REST API.
 * Requires: window.GEMINI_API_KEY (injected by live_data.js from dashboard.py)
 */

window.GeminiAI = (function () {

  const MODEL = 'gemini-2.0-flash';
  const ENDPOINT = `https://generativelanguage.googleapis.com/v1beta/models/${MODEL}:generateContent`;

  /**
   * Core call — returns plain text response string.
   * @param {string} prompt
   * @param {number} maxTokens
   * @returns {Promise<string>}
   */
  async function call(prompt, maxTokens = 800) {
    const key = window.GEMINI_API_KEY || '';
    if (!key) throw new Error('GEMINI_API_KEY not set');

    const res = await fetch(`${ENDPOINT}?key=${key}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        contents: [{ parts: [{ text: prompt }] }],
        generationConfig: {
          maxOutputTokens: maxTokens,
          temperature: 0.4,
        }
      })
    });

    if (!res.ok) {
      const err = await res.text();
      throw new Error(`Gemini API error ${res.status}: ${err}`);
    }

    const data = await res.json();
    return data?.candidates?.[0]?.content?.parts?.[0]?.text?.trim() || '';
  }

  /**
   * Generate 3-paragraph article analysis for the rotator card.
   */
  async function cardAnalysis(headline, summary) {
    const prompt = `You are a senior geopolitical analyst covering the US-Israel-Iran war of 2026.

Headline: ${headline}
Context: ${summary}

Write exactly 3 short paragraphs (no headings, no bullet points, plain prose only):
Para 1: What exactly happened and the immediate military/political facts.
Para 2: Why this matters — strategic significance, regional consequences, India angle.
Para 3: What happens next — most likely 24-48 hour scenario.

Each paragraph: 50-70 words. Be specific, direct, analytical. No filler phrases.`;

    return call(prompt, 600);
  }

  /**
   * Generate the left-panel AI summary (3 paragraphs, refreshed every 15 min).
   */
  async function panelSummary(headlines, escalationLevel) {
    const prompt = `You are a senior conflict analyst. The current escalation level is ${escalationLevel}.

Top recent stories:
${headlines}

Write exactly 3 short paragraphs (no headings, no bullets, plain prose):
Para 1: What is happening right now — the most critical developments.
Para 2: Broader consequences for the region, oil markets and India.
Para 3: What is most likely to happen in the next 24 hours.

Max 55 words per paragraph. Be specific and direct.`;

    return call(prompt, 500);
  }

  /**
   * Generate India tension meter JSON { pct, lvl, color }.
   */
  async function indiaMeter(context) {
    const prompt = `Based on this India-war situation: "${context}"

Return ONLY valid JSON, no markdown:
{"pct":72,"lvl":"High","color":"#d4892a"}

pct = 0-100 overall impact score. lvl = one word (Low/Moderate/High/Severe/Critical).
color = #3daa72 if low, #d4892a if moderate/high, #e05555 if severe/critical.`;

    const raw = await call(prompt, 80);
    return JSON.parse(raw.replace(/```json|```/g, '').trim());
  }

  /**
   * Parse paragraphs from a text response.
   */
  function toParaHtml(text) {
    const paras = text.split(/\n\n+/).filter(p => p.trim().length > 20).slice(0, 3);
    return paras.map(p => `<p>${p.trim()}</p>`).join('');
  }

  return { call, cardAnalysis, panelSummary, indiaMeter, toParaHtml };

})();