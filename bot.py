"""
bot.py — War Monitor Bot

Modes:
  python bot.py              # Run once (ignores seen cache — good for testing)
  python bot.py --watch      # Continuous loop, polls every 15 min (local use)
  python bot.py --actions    # GitHub Actions mode: check for new articles, exit

GitHub Actions runs --actions every 15 minutes automatically.
seen_urls.json and reports/ are committed back to the repo after each run,
so state persists across runs even though each Action starts fresh.

Data freshness policy:
  - If new articles found        → always run full pipeline
  - If no new articles BUT data is older than MAX_DATA_AGE_HOURS → re-run pipeline
    (uses existing seen articles so Gemini still has context)
  - If no new articles AND data is fresh → prices-only refresh, skip AI
"""

import json
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

from scraper import fetch_all_articles, fetch_article_content
from summarizer import generate_report, format_report_html
from dashboard import build_dashboard
from emailer import send_report_email
from prices_fetcher import build_prices_js

REPORTS_DIR         = Path("reports")
SEEN_FILE           = Path("seen_urls.json")
CHECK_INTERVAL_MINS = 15
MIN_NEW_ARTICLES    = 1
MAX_SEEN_URLS       = 500
MAX_DATA_AGE_HOURS  = 6   # Regenerate AI content if live_data.js is older than this


# ── Seen-URL cache ────────────────────────────────────────────────────────────

def load_seen() -> set:
    if SEEN_FILE.exists():
        try:
            return set(json.loads(SEEN_FILE.read_text()))
        except Exception:
            pass
    return set()


def save_seen(seen: set):
    urls = list(seen)[-MAX_SEEN_URLS:]
    SEEN_FILE.write_text(json.dumps(urls, indent=2))


def _live_data_age_hours() -> float:
    """Return how many hours ago live_data.js was last written. 999 if missing."""
    live_js = Path("live_data.js")
    if not live_js.exists():
        return 999.0
    mtime = datetime.fromtimestamp(live_js.stat().st_mtime, tz=timezone.utc)
    return (datetime.now(timezone.utc) - mtime).total_seconds() / 3600


# ── Core pipeline ─────────────────────────────────────────────────────────────

def run_pipeline(articles: list):
    """Summarise articles, save report, update dashboard, send email."""
    print(f"\n[1/4] Fetching article content...")
    for i, art in enumerate(articles[:8]):
        print(f"      [{i+1}/{min(8,len(articles))}] {art['title'][:65]}...")
        art["content"] = fetch_article_content(art["url"])

    print(f"\n[2/4] Generating AI content (all 5 steps in CI)...")
    report = generate_report(articles)
    print(f"      Escalation  : {report.get('escalation_level','?')}")
    print(f"      Developments: {len(report.get('key_developments',[]))}")
    print(f"      India angles: {len(report.get('india_impact',[]))}")
    print(f"      Panel summary: {len(report.get('execSummaryRich',''))} chars")
    print(f"      India summary: {len(report.get('indiaSummary',''))} chars")
    print(f"      India meter : {report.get('indiaMeter',{})}")

    print(f"\n[3/4] Saving report + updating live_data.js...")
    REPORTS_DIR.mkdir(exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    path = REPORTS_DIR / f"report_{ts}.json"
    path.write_text(json.dumps(report, indent=2))
    print(f"      Saved: {path}")
    build_dashboard()
    print(f"      live_data.js updated — all AI content pre-baked")

    print(f"\n[3b] Fetching live prices...")
    try:
        build_prices_js()
    except Exception as e:
        print(f"      [WARN] Prices fetch failed: {e}")

    print(f"\n[4/4] Sending email report...")
    try:
        html_body = format_report_html(report)
        level = report.get("escalation_level", "MEDIUM")
        subject = f"[{level}] WarWatch Report — {datetime.now(timezone.utc).strftime('%b %d %H:%M UTC')}"
        send_report_email(html_body, subject=subject)
    except Exception as e:
        print(f"      [WARN] Email failed: {e}")

    print()


# ── Run modes ─────────────────────────────────────────────────────────────────

def run_actions():
    """
    GitHub Actions mode.

    Logic:
      1. Load seen URL cache
      2. Fetch all RSS feeds
      3. Find new articles
      4. If new articles exist → run full pipeline
      5. If NO new articles BUT live_data.js is stale (> MAX_DATA_AGE_HOURS) →
           re-run pipeline with recent seen articles so data stays fresh
      6. If NO new articles AND data is fresh → prices-only refresh
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"\n=== WarWatch Bot — GitHub Actions [{now}] ===\n")

    seen = load_seen()
    print(f"Loaded {len(seen)} seen URLs from cache.")

    all_articles = fetch_all_articles()
    new_articles  = [a for a in all_articles if a["url"] not in seen]

    print(f"Found {len(all_articles)} articles total, {len(new_articles)} new.")

    if len(all_articles) == 0:
        print("[WARN] Scraper returned 0 articles.")
        print("       Causes: RSS URLs broken/403, keyword filter too strict, or network issue.")

    age_hours = _live_data_age_hours()
    data_is_stale = age_hours > MAX_DATA_AGE_HOURS
    print(f"live_data.js age: {age_hours:.1f}h (stale if >{MAX_DATA_AGE_HOURS}h) → {'STALE' if data_is_stale else 'fresh'}\n")

    # Always update seen cache
    seen.update(a["url"] for a in all_articles)
    save_seen(seen)

    if len(new_articles) >= MIN_NEW_ARTICLES:
        # New articles → run full pipeline
        print(f">>> {len(new_articles)} new article(s) — running full pipeline:")
        for a in new_articles:
            print(f"    [{a['source']}] {a['title'][:72]}")
        run_pipeline(new_articles)

    elif len(all_articles) > 0 and data_is_stale:
        # No new articles but data is stale → re-run to refresh AI content
        print(f">>> No new articles but data is {age_hours:.1f}h old — refreshing AI content...")
        recent = all_articles[:20]
        print(f"    Re-running pipeline with {len(recent)} recent articles")
        run_pipeline(recent)

    elif len(all_articles) == 0 and data_is_stale:
        print(f">>> Scraper empty AND data stale ({age_hours:.1f}h) — prices only.")
        try:
            build_prices_js()
            print("    [OK] prices_data.js refreshed.")
        except Exception as e:
            print(f"    [WARN] Prices fetch failed: {e}")

    else:
        # No new articles, data is fresh → prices only
        print(f"No new articles, data fresh ({age_hours:.1f}h old) — prices only.")
        try:
            build_prices_js()
            print("  [OK] prices_data.js refreshed.")
        except Exception as e:
            print(f"  [WARN] Prices fetch failed: {e}")

    print("=== Done ===")


def run_once():
    """Force a full run regardless of seen cache. Good for local testing."""
    print(f"\n=== WarWatch Bot — ONE-TIME RUN ===\n")

    articles = fetch_all_articles()
    if not articles:
        print("No articles found.")
        return

    print(f"Found {len(articles)} articles.\n")
    run_pipeline(articles)

    seen = load_seen()
    seen.update(a["url"] for a in articles)
    save_seen(seen)
    print("Done! Open index.html in your browser.")


def run_watch():
    """
    Continuous local loop — polls every CHECK_INTERVAL_MINS minutes.
    """
    print(f"\n=== WarWatch Bot — WATCHER (every {CHECK_INTERVAL_MINS} min) ===")
    print("Press Ctrl+C to stop\n")

    seen = load_seen()
    print(f"Loaded {len(seen)} seen URLs.\n")

    updates = 0
    while True:
        try:
            now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            age_hours = _live_data_age_hours()
            data_is_stale = age_hours > MAX_DATA_AGE_HOURS
            print(f"[{now}] Checking... (data age: {age_hours:.1f}h)", end=" ", flush=True)

            all_articles = fetch_all_articles()
            new_articles  = [a for a in all_articles if a["url"] not in seen]

            seen.update(a["url"] for a in all_articles)
            save_seen(seen)

            if len(new_articles) >= MIN_NEW_ARTICLES:
                print(f"\n>>> {len(new_articles)} new articles!")
                for a in new_articles:
                    print(f"    [{a['source']}] {a['title'][:72]}")
                run_pipeline(new_articles)
                updates += 1
                print(f"Session updates: {updates}\n")
            elif data_is_stale:
                print(f"\n>>> Data stale ({age_hours:.1f}h) — refreshing with recent articles")
                run_pipeline(all_articles[:20])
                updates += 1
            else:
                print(f"0 new — skipping (data fresh).")

        except KeyboardInterrupt:
            print(f"\nStopped. {updates} update(s) this session.")
            break
        except Exception as e:
            print(f"\n[ERROR] {e} — retrying in {CHECK_INTERVAL_MINS} min")

        time.sleep(CHECK_INTERVAL_MINS * 60)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if "--actions" in sys.argv:
        run_actions()
    elif "--watch" in sys.argv or "--loop" in sys.argv:
        run_watch()
    elif "--prices" in sys.argv:
        print("\n=== WarWatch Bot — PRICES ONLY ===\n")
        try:
            build_prices_js()
            print("Done!")
        except Exception as e:
            print(f"[ERROR] {e}")
    else:
        run_once()
