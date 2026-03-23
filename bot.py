import sys, os
print("[BOT] Starting...", flush=True)

import json, time, shutil
print("[BOT] stdlib imports OK", flush=True)

from datetime import datetime, timezone
from pathlib import Path
print("[BOT] datetime/pathlib OK", flush=True)

print("[BOT] Importing scraper...", flush=True)
from scraper import fetch_all_articles, fetch_article_content
print("[BOT] scraper OK", flush=True)

print("[BOT] Importing summarizer...", flush=True)
from summarizer import generate_report, format_report_html
print("[BOT] summarizer OK", flush=True)

print("[BOT] Importing dashboard...", flush=True)
from dashboard import build_dashboard
print("[BOT] dashboard OK", flush=True)

try:
    from emailer import send_report_email
    HAS_EMAIL = True
    print("[BOT] emailer OK", flush=True)
except ImportError:
    HAS_EMAIL = False
    print("[BOT] emailer not found — skipped", flush=True)

try:
    from prices_fetcher import build_prices_js
    HAS_PRICES = True
    print("[BOT] prices_fetcher OK", flush=True)
except ImportError:
    HAS_PRICES = False
    print("[BOT] prices_fetcher not found — skipped", flush=True)

REPORTS_DIR    = Path("reports")
SEEN_FILE      = Path("seen_urls.json")
LIVE_JS        = Path("live_data.js")
LIVE_JS_TMP    = Path("live_data.tmp.js")
LIVE_JS_BACKUP = Path("live_data.bak.js")
MAX_SEEN_URLS  = 500
MAX_DATA_AGE_HOURS = 1
MIN_NEW_ARTICLES   = 1

def load_seen():
    if SEEN_FILE.exists():
        try: return set(json.loads(SEEN_FILE.read_text()))
        except: pass
    return set()

def save_seen(seen):
    SEEN_FILE.write_text(json.dumps(list(seen)[-MAX_SEEN_URLS:], indent=2))

def _live_data_age_hours():
    if not LIVE_JS.exists(): return 999.0
    mtime = datetime.fromtimestamp(LIVE_JS.stat().st_mtime, tz=timezone.utc)
    return (datetime.now(timezone.utc) - mtime).total_seconds() / 3600

REQUIRED_KEYS = ["generatedAt","escalationLevel","newsCards","execSummaryRich","indiaSummary","indiaImpact","indiaMeter"]

def _validate_live_data(path):
    try:
        text = path.read_text()
        json_str = text.replace("window.WARWATCH_LIVE =","").strip().rstrip(";")
        data = json.loads(json_str)
        for key in REQUIRED_KEYS:
            if key not in data:
                print(f"  [HEALTH] Missing key: {key}", flush=True)
                return False
        if not data.get("newsCards"):
            print("  [HEALTH] newsCards empty", flush=True)
            return False
        print(f"  [HEALTH] Valid — {len(data.get('newsCards',[]))} cards", flush=True)
        return True
    except Exception as e:
        print(f"  [HEALTH] Failed: {e}", flush=True)
        return False

def _atomic_replace():
    if not LIVE_JS_TMP.exists(): return False
    if not _validate_live_data(LIVE_JS_TMP):
        LIVE_JS_TMP.unlink(missing_ok=True)
        return False
    if LIVE_JS.exists(): shutil.copy2(LIVE_JS, LIVE_JS_BACKUP)
    LIVE_JS_TMP.rename(LIVE_JS)
    print("  [ATOMIC] live_data.js updated ✓", flush=True)
    return True

def _refresh_prices():
    if not HAS_PRICES: return
    try:
        build_prices_js()
        print("  [OK] prices_data.js refreshed", flush=True)
    except Exception as e:
        print(f"  [WARN] Prices failed: {e}", flush=True)

def run_pipeline(articles):
    REPORTS_DIR.mkdir(exist_ok=True)
    print(f"\n[1/4] Fetching content for top 8 articles...", flush=True)
    for i, art in enumerate(articles[:8]):
        print(f"      [{i+1}/8] {art['title'][:60]}...", flush=True)
        try: art["content"] = fetch_article_content(art["url"])
        except Exception as e:
            print(f"      [WARN] {e}", flush=True)
            art["content"] = ""

    print(f"\n[2/4] Running AI pipeline...", flush=True)
    try:
        report = generate_report(articles)
    except Exception as e:
        print(f"  [ERROR] generate_report: {e}", flush=True)
        from summarizer import _fallback_report, _validate_and_fill
        report = _fallback_report(articles)
        _validate_and_fill(report, articles)

    print(f"\n[3/4] Building dashboard...", flush=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    try:
        (REPORTS_DIR / f"report_{ts}.json").write_text(json.dumps(report, indent=2))
    except Exception as e:
        print(f"  [WARN] Report save failed: {e}", flush=True)
    try:
        build_dashboard()
        _atomic_replace()
    except Exception as e:
        print(f"  [ERROR] Dashboard: {e}", flush=True)

    print(f"\n[3b] Refreshing prices...", flush=True)
    _refresh_prices()

    print(f"\n[4/4] Email...", flush=True)
    if HAS_EMAIL:
        try:
            send_report_email(format_report_html(report),
                subject=f"[{report.get('escalation_level','HIGH')}] WarWatch — {datetime.now(timezone.utc).strftime('%b %d %H:%M UTC')}")
            print("  Email sent ✓", flush=True)
        except Exception as e:
            print(f"  [WARN] Email failed: {e}", flush=True)
    else:
        print("  Email skipped", flush=True)

def run_actions():
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"\n=== WarWatch Bot — GitHub Actions [{now}] ===\n", flush=True)

    seen = load_seen()
    print("[BOT] Fetching articles...", flush=True)
    all_articles = fetch_all_articles()
    new_articles = [a for a in all_articles if a["url"] not in seen]
    age_hours = _live_data_age_hours()
    data_is_stale = age_hours > MAX_DATA_AGE_HOURS

    print(f"Seen: {len(seen)} | All: {len(all_articles)} | New: {len(new_articles)}", flush=True)
    print(f"live_data.js age: {age_hours:.1f}h → {'STALE' if data_is_stale else 'fresh'}\n", flush=True)

    seen.update(a["url"] for a in all_articles)
    save_seen(seen)

    if len(new_articles) >= MIN_NEW_ARTICLES:
        print(f">>> {len(new_articles)} new articles — full pipeline", flush=True)
        run_pipeline(new_articles)
    elif data_is_stale:
        print(f">>> Data stale — refreshing", flush=True)
        run_pipeline(all_articles[:20] or [])
    else:
        print("No new articles, data fresh — prices only", flush=True)
        _refresh_prices()

    print("=== Done ===", flush=True)

if __name__ == "__main__":
    try:
        if "--actions" in sys.argv:
            run_actions()
        elif "--prices" in sys.argv:
            _refresh_prices()
        else:
            print("Usage: python bot.py --actions", flush=True)
    except Exception as e:
        print(f"\n[FATAL] {e}", flush=True)
        import traceback; traceback.print_exc()
    finally:
        sys.exit(0)
