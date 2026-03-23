"""
bot.py — Bulletproof WarWatch orchestrator.

Improvements:
  - Atomic writes: writes live_data.tmp.js first, renames on success
  - Health check: validates live_data.js after write, restores backup if invalid
  - Article cache: if scraper returns 0, uses cached articles instead of skipping
  - Always exits 0 — GitHub Actions never fails/pauses due to bot error
  - Graceful import fallback for optional modules (emailer, prices_fetcher)

Modes:
  python bot.py              → run once (good for local testing)
  python bot.py --watch      → continuous loop every 15 min
  python bot.py --actions    → GitHub Actions mode
  python bot.py --prices     → prices-only refresh
"""

import json, sys, time, shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path

from scraper   import fetch_all_articles, fetch_article_content
from summarizer import generate_report, format_report_html
from dashboard import build_dashboard

# Optional modules — bot works fine without them
try:
    from emailer import send_report_email
    HAS_EMAIL = True
except ImportError:
    HAS_EMAIL = False
    print("[INFO] emailer.py not found — email step skipped")

try:
    from prices_fetcher import build_prices_js
    HAS_PRICES = True
except ImportError:
    HAS_PRICES = False
    print("[INFO] prices_fetcher.py not found — prices step skipped")

REPORTS_DIR         = Path("reports")
SEEN_FILE           = Path("seen_urls.json")
LIVE_JS             = Path("live_data.js")
LIVE_JS_TMP         = Path("live_data.tmp.js")
LIVE_JS_BACKUP      = Path("live_data.bak.js")
CHECK_INTERVAL_MINS = 15
MIN_NEW_ARTICLES    = 1
MAX_SEEN_URLS       = 500
MAX_DATA_AGE_HOURS  = 1


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
    if not LIVE_JS.exists():
        return 999.0
    mtime = datetime.fromtimestamp(LIVE_JS.stat().st_mtime, tz=timezone.utc)
    return (datetime.now(timezone.utc) - mtime).total_seconds() / 3600


# ── Health check ──────────────────────────────────────────────────────────────

REQUIRED_KEYS = [
    "generatedAt", "escalationLevel", "newsCards",
    "execSummaryRich", "indiaSummary", "indiaImpact", "indiaMeter",
]

def _validate_live_data(path: Path) -> bool:
    """Return True if live_data.js is valid and has all required keys."""
    try:
        text = path.read_text()
        # Strip the window.WARWATCH_LIVE = ... wrapper
        json_str = text.replace("window.WARWATCH_LIVE =", "").strip().rstrip(";").strip()
        data = json.loads(json_str)
        for key in REQUIRED_KEYS:
            if key not in data:
                print(f"  [HEALTH] Missing key: {key}")
                return False
        if not data.get("newsCards"):
            print("  [HEALTH] newsCards is empty")
            return False
        print(f"  [HEALTH] live_data.js valid — {len(data.get('newsCards',[]))} cards, "
              f"execSummary={len(data.get('execSummaryRich',''))}c, "
              f"indiaSummary={len(data.get('indiaSummary',''))}c")
        return True
    except Exception as e:
        print(f"  [HEALTH] Validation failed: {e}")
        return False


def _atomic_replace_live_data():
    """
    Move live_data.tmp.js → live_data.js atomically.
    Validates before replacing; restores backup if new file is bad.
    """
    if not LIVE_JS_TMP.exists():
        print("  [ATOMIC] No tmp file found — skipping replace")
        return False

    print("  [ATOMIC] Validating new live_data.js...")
    if not _validate_live_data(LIVE_JS_TMP):
        print("  [ATOMIC] New file failed validation — keeping old live_data.js")
        LIVE_JS_TMP.unlink(missing_ok=True)
        return False

    # Backup current live_data.js
    if LIVE_JS.exists():
        shutil.copy2(LIVE_JS, LIVE_JS_BACKUP)

    # Atomic rename
    LIVE_JS_TMP.rename(LIVE_JS)
    print("  [ATOMIC] live_data.js updated successfully ✓")
    return True


# ── Prices refresh ────────────────────────────────────────────────────────────

def _refresh_prices():
    if not HAS_PRICES:
        return
    try:
        build_prices_js()
        print("  [OK] prices_data.js refreshed.")
    except Exception as e:
        print(f"  [WARN] Prices fetch failed: {e}")


# ── Core pipeline ─────────────────────────────────────────────────────────────

def run_pipeline(articles: list):
    """
    Full pipeline: summarise → save report → build dashboard → email.
    Uses atomic write so a crash mid-way never corrupts live_data.js.
    """
    REPORTS_DIR.mkdir(exist_ok=True)

    print(f"\n[1/4] Fetching article content for top 8 articles...")
    for i, art in enumerate(articles[:8]):
        print(f"      [{i+1}/{min(8,len(articles))}] {art['title'][:65]}...")
        try:
            art["content"] = fetch_article_content(art["url"])
        except Exception as e:
            print(f"      [WARN] Content fetch failed: {e}")
            art["content"] = ""

    print(f"\n[2/4] Running AI pipeline...")
    try:
        report = generate_report(articles)
    except Exception as e:
        print(f"  [ERROR] generate_report raised: {e}")
        # Build minimal report so pipeline never stops
        from summarizer import _fallback_report, _validate_and_fill
        report = _fallback_report(articles)
        _validate_and_fill(report, articles)

    print(f"\n[3/4] Saving report + building live_data.js...")
    ts   = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    path = REPORTS_DIR / f"report_{ts}.json"
    try:
        path.write_text(json.dumps(report, indent=2))
        print(f"      Saved: {path}")
    except Exception as e:
        print(f"      [WARN] Report save failed: {e}")

    # Build dashboard writes to live_data.tmp.js via patched dashboard.py
    try:
        build_dashboard()
        _atomic_replace_live_data()
    except Exception as e:
        print(f"      [ERROR] Dashboard build failed: {e}")

    print(f"\n[3b] Refreshing prices...")
    _refresh_prices()

    print(f"\n[4/4] Sending email...")
    if HAS_EMAIL:
        try:
            html_body = format_report_html(report)
            level     = report.get("escalation_level","HIGH")
            subject   = f"[{level}] WarWatch — {datetime.now(timezone.utc).strftime('%b %d %H:%M UTC')}"
            send_report_email(html_body, subject=subject)
            print("      Email sent ✓")
        except Exception as e:
            print(f"      [WARN] Email failed: {e}")
    else:
        print("      Email skipped (emailer.py not present)")

    print()


# ── Run modes ─────────────────────────────────────────────────────────────────

def run_actions():
    """GitHub Actions mode — smart: new articles → full pipeline, stale → refresh, fresh → prices only."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"\n=== WarWatch Bot — GitHub Actions [{now}] ===\n")

    seen          = load_seen()
    all_articles  = fetch_all_articles()
    new_articles  = [a for a in all_articles if a["url"] not in seen]
    age_hours     = _live_data_age_hours()
    data_is_stale = age_hours > MAX_DATA_AGE_HOURS

    print(f"Seen: {len(seen)} | All: {len(all_articles)} | New: {len(new_articles)}")
    print(f"live_data.js age: {age_hours:.1f}h → {'STALE' if data_is_stale else 'fresh'}\n")

    seen.update(a["url"] for a in all_articles)
    save_seen(seen)

    if len(new_articles) >= MIN_NEW_ARTICLES:
        print(f">>> {len(new_articles)} new articles — full pipeline")
        for a in new_articles:
            print(f"    [{a['source']}] {a['title'][:72]}")
        run_pipeline(new_articles)

    elif data_is_stale:
        recent = all_articles[:20] or []
        print(f">>> No new articles but data is {age_hours:.1f}h old — refreshing with {len(recent)} recent")
        if recent:
            run_pipeline(recent)
        else:
            print("    No articles at all — prices only")
            _refresh_prices()

    else:
        print(f"No new articles, data fresh ({age_hours:.1f}h) — prices only")
        _refresh_prices()

    print("=== Done ===")


def run_once():
    """Force full run — ignores seen cache. Good for local testing."""
    print(f"\n=== WarWatch Bot — ONE-TIME RUN ===\n")
    articles = fetch_all_articles()
    if not articles:
        print("[ERROR] No articles found even from cache.")
        return
    print(f"Found {len(articles)} articles.\n")
    run_pipeline(articles)
    seen = load_seen()
    seen.update(a["url"] for a in articles)
    save_seen(seen)
    print("Done! Open index.html in your browser.")


def run_watch():
    """Continuous local loop."""
    print(f"\n=== WarWatch Bot — WATCHER (every {CHECK_INTERVAL_MINS} min) ===")
    print("Press Ctrl+C to stop\n")

    seen    = load_seen()
    updates = 0

    while True:
        try:
            now           = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            age_hours     = _live_data_age_hours()
            data_is_stale = age_hours > MAX_DATA_AGE_HOURS
            print(f"[{now}] Checking... (data age: {age_hours:.1f}h)", end=" ", flush=True)

            all_articles = fetch_all_articles()
            new_articles = [a for a in all_articles if a["url"] not in seen]
            seen.update(a["url"] for a in all_articles)
            save_seen(seen)

            if len(new_articles) >= MIN_NEW_ARTICLES:
                print(f"\n>>> {len(new_articles)} new articles!")
                run_pipeline(new_articles)
                updates += 1
            elif data_is_stale:
                print(f"\n>>> Data stale ({age_hours:.1f}h) — refreshing")
                run_pipeline(all_articles[:20])
                updates += 1
            else:
                print("0 new, data fresh — skipping.")

        except KeyboardInterrupt:
            print(f"\nStopped. {updates} update(s) this session.")
            break
        except Exception as e:
            print(f"\n[ERROR] {e} — continuing in {CHECK_INTERVAL_MINS} min")

        time.sleep(CHECK_INTERVAL_MINS * 60)


# ── Entry ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    try:
        if "--actions" in sys.argv:
            run_actions()
        elif "--watch" in sys.argv or "--loop" in sys.argv:
            run_watch()
        elif "--prices" in sys.argv:
            print("\n=== WarWatch Bot — PRICES ONLY ===\n")
            _refresh_prices()
        else:
            run_once()
    except Exception as e:
        # Always exit 0 so GitHub Actions never pauses the workflow
        print(f"\n[FATAL] Unhandled exception: {e}")
        import traceback; traceback.print_exc()
    finally:
        sys.exit(0)   # Always 0 — never pause GitHub Actions
