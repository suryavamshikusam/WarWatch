"""
bot.py — War Monitor Bot

Modes:
  python bot.py              # Run once — good for local testing
  python bot.py --watch      # Continuous loop, polls every 15 min
  python bot.py --actions    # GitHub Actions mode

How the seen cache works NOW:
  - seen_urls.json tracks which URLs have been processed
  - NEW articles   → always fetch content + run full pipeline
  - NO new articles BUT data stale (>6h) → fetch content for recent articles + re-run
  - NO new articles AND data fresh → prices only

Critical fix vs old version:
  - fetch_article_content() is ALWAYS called before run_pipeline()
    even for the stale-data re-run path, so Gemini always gets real text
"""

import json
import sys
import time
from datetime import datetime, timezone
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
MAX_SEEN_URLS       = 600
MAX_DATA_AGE_HOURS  = 6


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
    live_js = Path("live_data.js")
    if not live_js.exists():
        return 999.0
    mtime = datetime.fromtimestamp(live_js.stat().st_mtime, tz=timezone.utc)
    return (datetime.now(timezone.utc) - mtime).total_seconds() / 3600


# ── Content fetching ──────────────────────────────────────────────────────────

def _fetch_content_for_articles(articles: list, max_fetch: int = 10):
    """
    Fetch full article text for the top N articles.
    Modifies articles in-place.
    """
    to_fetch = [a for a in articles if not a.get("content")][:max_fetch]
    print(f"  Fetching content for {len(to_fetch)} articles...")
    for i, art in enumerate(to_fetch):
        print(f"    [{i+1}/{len(to_fetch)}] {art['title'][:65]}...")
        art["content"] = fetch_article_content(art["url"])
    return articles


# ── Core pipeline ─────────────────────────────────────────────────────────────

def run_pipeline(articles: list):
    """Fetch content, summarise, save report, update dashboard, send email."""
    print(f"\n[1/4] Fetching article content...")
    _fetch_content_for_articles(articles, max_fetch=10)

    print(f"\n[2/4] Generating AI content...")
    report = generate_report(articles)
    print(f"      Escalation  : {report.get('escalation_level','?')}")
    print(f"      Developments: {len(report.get('key_developments',[]))}")
    print(f"      India angles: {len(report.get('india_impact',[]))}")

    print(f"\n[3/4] Saving report + updating live_data.js...")
    REPORTS_DIR.mkdir(exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    path = REPORTS_DIR / f"report_{ts}.json"
    path.write_text(json.dumps(report, indent=2))
    print(f"      Saved: {path}")
    build_dashboard()

    print(f"\n[3b] Fetching live prices...")
    try:
        build_prices_js()
    except Exception as e:
        print(f"      [WARN] Prices failed: {e}")

    print(f"\n[4/4] Sending email...")
    try:
        html_body = format_report_html(report)
        level = report.get("escalation_level", "MEDIUM")
        subject = f"[{level}] WarWatch — {datetime.now(timezone.utc).strftime('%b %d %H:%M UTC')}"
        send_report_email(html_body, subject=subject)
    except Exception as e:
        print(f"      [WARN] Email failed: {e}")
    print()


# ── Run modes ─────────────────────────────────────────────────────────────────

def run_actions():
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"\n=== WarWatch Bot — GitHub Actions [{now}] ===\n")

    seen = load_seen()
    print(f"Loaded {len(seen)} seen URLs from cache.")

    # Always fetch fresh articles from RSS
    all_articles = fetch_all_articles()
    new_articles  = [a for a in all_articles if a["url"] not in seen]

    print(f"Found {len(all_articles)} articles total, {len(new_articles)} new.")

    age_hours = _live_data_age_hours()
    data_is_stale = age_hours > MAX_DATA_AGE_HOURS
    print(f"live_data.js age: {age_hours:.1f}h → {'STALE' if data_is_stale else 'fresh'}\n")

    # Update seen cache with everything found
    seen.update(a["url"] for a in all_articles)
    save_seen(seen)

    if len(new_articles) >= MIN_NEW_ARTICLES:
        print(f">>> {len(new_articles)} new article(s) — running full pipeline")
        for a in new_articles[:5]:
            print(f"    [{a['source']}] {a['title'][:72]}")
        run_pipeline(new_articles)

    elif len(all_articles) > 0 and data_is_stale:
        # No new articles but data is stale.
        # Use all_articles (the most recent from RSS) and fetch their content fresh.
        # This ensures Gemini always gets real text, not empty strings.
        print(f">>> No new articles but data is {age_hours:.1f}h old — refreshing with recent articles")
        recent = all_articles[:20]
        # Clear content so it gets re-fetched fresh
        for a in recent:
            a["content"] = ""
        run_pipeline(recent)

    else:
        print(f"No new articles, data fresh ({age_hours:.1f}h old) — prices only.")
        try:
            build_prices_js()
            print("  [OK] prices_data.js refreshed.")
        except Exception as e:
            print(f"  [WARN] Prices failed: {e}")

    print("=== Done ===")


def run_once():
    """Force a full run — good for local testing."""
    print(f"\n=== WarWatch Bot — ONE-TIME RUN ===\n")
    articles = fetch_all_articles()
    if not articles:
        print("No articles found.")
        return
    print(f"Found {len(articles)} articles.\n")
    # Always clear content so it gets fetched fresh
    for a in articles:
        a["content"] = ""
    run_pipeline(articles)
    seen = load_seen()
    seen.update(a["url"] for a in articles)
    save_seen(seen)
    print("Done!")


def run_watch():
    print(f"\n=== WarWatch Bot — WATCHER (every {CHECK_INTERVAL_MINS} min) ===")
    print("Press Ctrl+C to stop\n")
    seen = load_seen()
    updates = 0
    while True:
        try:
            now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            age_hours = _live_data_age_hours()
            print(f"[{now}] Checking... (data age: {age_hours:.1f}h)", end=" ", flush=True)

            all_articles = fetch_all_articles()
            new_articles  = [a for a in all_articles if a["url"] not in seen]

            seen.update(a["url"] for a in all_articles)
            save_seen(seen)

            if len(new_articles) >= MIN_NEW_ARTICLES:
                print(f"\n>>> {len(new_articles)} new articles!")
                run_pipeline(new_articles)
                updates += 1
            elif age_hours > MAX_DATA_AGE_HOURS:
                print(f"\n>>> Data stale — refreshing")
                recent = all_articles[:20]
                for a in recent:
                    a["content"] = ""
                run_pipeline(recent)
                updates += 1
            else:
                print(f"0 new — skipping.")

        except KeyboardInterrupt:
            print(f"\nStopped. {updates} update(s) this session.")
            break
        except Exception as e:
            print(f"\n[ERROR] {e}")

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
