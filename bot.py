"""
bot.py — War Monitor Bot (No AI mode)

Scrapes RSS feeds, categorises articles by keyword rules,
writes live_data.js directly. No Gemini, no summariser.

Modes:
  python bot.py              # Run once
  python bot.py --watch      # Loop every 15 min
  python bot.py --actions    # GitHub Actions mode
  python bot.py --prices     # Prices only
"""

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from scraper import fetch_all_articles
from dashboard import build_dashboard
from prices_fetcher import build_prices_js

SEEN_FILE           = Path("seen_urls.json")
MAX_SEEN_URLS       = 800
CHECK_INTERVAL_MINS = 15
MAX_DATA_AGE_HOURS  = 3   # Refresh every 3 hours even if no new articles


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
    f = Path("live_data.js")
    if not f.exists():
        return 999.0
    mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
    return (datetime.now(timezone.utc) - mtime).total_seconds() / 3600


def run_pipeline(articles: list):
    """Build live_data.js from articles. No AI needed."""
    print(f"\n[1/2] Building dashboard from {len(articles)} articles...")
    build_dashboard()

    print(f"\n[2/2] Fetching live prices...")
    try:
        build_prices_js()
    except Exception as e:
        print(f"  [WARN] Prices failed: {e}")
    print()


def run_actions():
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"\n=== WarWatch Bot — Actions [{now}] ===\n")

    seen = load_seen()
    print(f"Loaded {len(seen)} seen URLs.")

    all_articles = fetch_all_articles()
    new_articles  = [a for a in all_articles if a["url"] not in seen]
    age_hours     = _live_data_age_hours()
    data_is_stale = age_hours > MAX_DATA_AGE_HOURS

    print(f"Found {len(all_articles)} total, {len(new_articles)} new.")
    print(f"live_data.js age: {age_hours:.1f}h → {'STALE' if data_is_stale else 'fresh'}\n")

    seen.update(a["url"] for a in all_articles)
    save_seen(seen)

    if len(new_articles) >= 1:
        print(f">>> {len(new_articles)} new articles — rebuilding dashboard")
        for a in new_articles[:5]:
            print(f"    [{a['source']}] [{a['type']}] {a['title'][:70]}")
        # Pass ALL articles (new + recent) so every category has content
        run_pipeline(all_articles)

    elif data_is_stale:
        print(f">>> No new articles but data is {age_hours:.1f}h old — refreshing")
        run_pipeline(all_articles)

    else:
        print(f"No new articles, data fresh — prices only.")
        try:
            build_prices_js()
            print("  [OK] prices_data.js refreshed.")
        except Exception as e:
            print(f"  [WARN] {e}")

    print("=== Done ===")


def run_once():
    print(f"\n=== WarWatch Bot — ONE-TIME RUN ===\n")
    articles = fetch_all_articles()
    if not articles:
        print("No articles found — check RSS feeds.")
        return
    print(f"Found {len(articles)} articles.\n")
    run_pipeline(articles)
    seen = load_seen()
    seen.update(a["url"] for a in articles)
    save_seen(seen)
    print("Done!")


def run_watch():
    print(f"\n=== WarWatch Bot — WATCHER (every {CHECK_INTERVAL_MINS} min) ===")
    print("Ctrl+C to stop\n")
    seen = load_seen()
    updates = 0
    while True:
        try:
            now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            age = _live_data_age_hours()
            print(f"[{now}] Checking... (age: {age:.1f}h)", end=" ", flush=True)

            all_articles = fetch_all_articles()
            new_articles  = [a for a in all_articles if a["url"] not in seen]
            seen.update(a["url"] for a in all_articles)
            save_seen(seen)

            if len(new_articles) >= 1 or age > MAX_DATA_AGE_HOURS:
                reason = f"{len(new_articles)} new" if new_articles else "data stale"
                print(f"\n>>> {reason} — rebuilding")
                run_pipeline(all_articles)
                updates += 1
            else:
                print("skipping.")

        except KeyboardInterrupt:
            print(f"\nStopped. {updates} update(s).")
            break
        except Exception as e:
            print(f"\n[ERROR] {e}")

        time.sleep(CHECK_INTERVAL_MINS * 60)


if __name__ == "__main__":
    if "--actions" in sys.argv:
        run_actions()
    elif "--watch" in sys.argv or "--loop" in sys.argv:
        run_watch()
    elif "--prices" in sys.argv:
        print("\n=== PRICES ONLY ===\n")
        try:
            build_prices_js()
            print("Done!")
        except Exception as e:
            print(f"[ERROR] {e}")
    else:
        run_once()
