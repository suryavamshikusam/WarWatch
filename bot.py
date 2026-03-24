"""
bot.py — WarWatch Bot. Pure RSS. Zero AI.

Modes:
  python bot.py              # Run once (testing)
  python bot.py --actions    # GitHub Actions mode (every 15 min)
  python bot.py --prices     # Prices only
"""

import sys
from datetime import datetime, timezone
from scraper import fetch_and_update
from dashboard import build_dashboard

try:
    from prices_fetcher import build_prices_js
    HAS_PRICES = True
except ImportError:
    HAS_PRICES = False
    print("[WARN] prices_fetcher.py not found — skipping prices")


def run_pipeline():
    print(f"\n[1/3] Fetching RSS feeds...")
    data  = fetch_and_update()
    arts  = data.get("articles",[])
    india = [a for a in arts if a.get("india")]
    print(f"      Total: {len(arts)} | War: {len(arts)-len(india)} | India: {len(india)}")

    print(f"\n[2/3] Building live_data.js...")
    build_dashboard()

    print(f"\n[3/3] Fetching prices...")
    if HAS_PRICES:
        try:
            build_prices_js()
        except Exception as e:
            print(f"      [WARN] Prices failed: {e}")
    else:
        print("      Skipped — no prices_fetcher.py")

    print(f"\nDone. Open index.html to view.")


def run_actions():
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"\n=== WarWatch Bot — GitHub Actions [{now}] ===")
    run_pipeline()
    print("=== Done ===")


def run_once():
    print(f"\n=== WarWatch Bot — One-time run ===")
    run_pipeline()


if __name__ == "__main__":
    if "--actions" in sys.argv:
        run_actions()
    elif "--prices" in sys.argv:
        print("\n=== Prices only ===")
        if HAS_PRICES:
            try:
                build_prices_js()
                print("Done!")
            except Exception as e:
                print(f"[ERROR] {e}")
        else:
            print("[ERROR] prices_fetcher.py not found")
    else:
        run_once()
