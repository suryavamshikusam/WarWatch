"""
bot.py — War Monitor Bot

Modes:
  python bot.py              # Run once (ignores seen cache — good for testing)
  python bot.py --watch      # Continuous loop, polls every 5 min (local use)
  python bot.py --actions    # GitHub Actions mode: check for new articles, exit

GitHub Actions runs --actions every 15 minutes automatically.
seen_urls.json and reports/ are committed back to the repo after each run,
so state persists across runs even though each Action starts fresh.
"""

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from scraper import fetch_all_articles, fetch_article_content
from summarizer import generate_report
from dashboard import build_dashboard

REPORTS_DIR         = Path("reports")
SEEN_FILE           = Path("seen_urls.json")
CHECK_INTERVAL_MINS = 15
MIN_NEW_ARTICLES    = 1   # trigger on even 1 new article in Actions mode
MAX_SEEN_URLS       = 500


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


# ── Core pipeline ─────────────────────────────────────────────────────────────

def run_pipeline(articles: list):
    """Summarise articles, save report, update dashboard."""
    print(f"\n[1/3] Fetching article content...")
    for i, art in enumerate(articles[:8]):
        print(f"      [{i+1}/{min(8,len(articles))}] {art['title'][:65]}...")
        art["content"] = fetch_article_content(art["url"])

    print(f"\n[2/3] Generating AI summary...")
    report = generate_report(articles)
    print(f"      Escalation  : {report.get('escalation_level','?')}")
    print(f"      Developments: {len(report.get('key_developments',[]))}")
    print(f"      India angles: {len(report.get('india_impact',[]))}")

    print(f"\n[3/3] Saving report + updating dashboard...")
    REPORTS_DIR.mkdir(exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    path = REPORTS_DIR / f"report_{ts}.json"
    path.write_text(json.dumps(report, indent=2))
    print(f"      Saved: {path}")
    build_dashboard()
    print(f"      Dashboard updated!\n")


# ── Run modes ─────────────────────────────────────────────────────────────────

def run_actions():
    """
    GitHub Actions mode.
    - Loads seen cache from repo
    - Fetches all RSS feeds
    - If new articles found: run pipeline, save seen cache
    - If nothing new: exit cleanly (workflow will still commit nothing)
    GitHub commits seen_urls.json + reports/ + live_data.js back to repo.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"\n=== WarWatch Bot — GitHub Actions [{now}] ===\n")

    seen = load_seen()
    print(f"Loaded {len(seen)} seen URLs from cache.")

    all_articles = fetch_all_articles()
    new_articles  = [a for a in all_articles if a["url"] not in seen]

    print(f"Found {len(all_articles)} articles total, {len(new_articles)} new.\n")

    # Always update seen cache so old articles don't pile up
    seen.update(a["url"] for a in all_articles)
    save_seen(seen)

    if len(new_articles) < MIN_NEW_ARTICLES:
        print("No new articles — nothing to summarise. Exiting cleanly.")
        return

    print(f">>> {len(new_articles)} new article(s):")
    for a in new_articles:
        print(f"    [{a['source']}] {a['title'][:72]}")

    run_pipeline(new_articles)
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
    print("Done! Open warwatch.html in your browser.")


def run_watch():
    """
    Continuous local loop — polls every CHECK_INTERVAL_MINS minutes.
    Useful when running on your own machine.
    """
    print(f"\n=== WarWatch Bot — WATCHER (every {CHECK_INTERVAL_MINS} min) ===")
    print("Press Ctrl+C to stop\n")

    seen = load_seen()
    print(f"Loaded {len(seen)} seen URLs.\n")

    updates = 0
    while True:
        try:
            now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            print(f"[{now}] Checking...", end=" ", flush=True)

            all_articles = fetch_all_articles()
            new_articles  = [a for a in all_articles if a["url"] not in seen]

            seen.update(a["url"] for a in all_articles)
            save_seen(seen)

            if len(new_articles) < 2:
                print(f"{len(new_articles)} new — skipping.")
            else:
                print(f"\n>>> {len(new_articles)} new articles!")
                for a in new_articles:
                    print(f"    [{a['source']}] {a['title'][:72]}")
                run_pipeline(new_articles)
                updates += 1
                print(f"Session updates: {updates}\n")

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
    else:
        run_once()