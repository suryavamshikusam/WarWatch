"""
prices_fetcher.py — Fetches live commodity and Indian market prices via yfinance.
Writes prices_data.js consumed by economy.html.

Called by bot.py after each pipeline run (add to run_pipeline).
Can also be run standalone: python prices_fetcher.py

Schema written to prices_data.js:
  window.WARWATCH_PRICES = {
    fetchedAt:  "2026-03-21 10:00 UTC",
    prices: {
      "BZ=F":          { name, price, formatted, day_pct, war_pct },
      "CL=F":          { ... },
      "NG=F":          { ... },
      "GC=F":          { ... },
      "ZW=F":          { ... },
      "INR=X":         { ... },
      "CRUDEOIL.MCX":  { ... },
      "GOLD.MCX":      { ... },
      "SILVER.MCX":    { ... },
      "IOC.NS":        { ... },
      "ADANIPORTS.NS": { ... },
    },
    india: {
      petrolPump: { formatted, war_change, formula },
      goldSilverRatio: 86.2,
    },
    history: [
      { date, brent, wti, ng, gold, wheat, inr,
        mcx_crude, mcx_gold, mcx_silver, ioc, adani }
    ]
  }
"""

import json
import os
import certifi
from datetime import datetime, timezone, timedelta
from pathlib import Path

os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

try:
    import yfinance as yf
except ImportError:
    print("[ERROR] yfinance not installed. Run: pip install yfinance")
    raise

PRICES_DATA_JS = Path("prices_data.js")
HISTORY_FILE   = Path("prices_history.json")

# War Day 1 baseline — March 10, 2026
WAR_BASELINE = {
    "BZ=F":          76.20,
    "CL=F":          73.10,
    "NG=F":          2.88,
    "GC=F":          2690.0,
    "ZW=F":          535.0,
    "INR=X":         82.10,
    "CRUDEOIL.MCX":  6350.0,
    "GOLD.MCX":      74800.0,
    "SILVER.MCX":    91500.0,
    "IOC.NS":        160.5,
    "ADANIPORTS.NS": 1233.0,
}

# Display names
NAMES = {
    "BZ=F":          "Brent Crude",
    "CL=F":          "WTI Crude",
    "NG=F":          "Natural Gas",
    "GC=F":          "Gold USD",
    "ZW=F":          "Wheat",
    "INR=X":         "USD / INR",
    "CRUDEOIL.MCX":  "MCX Crude",
    "GOLD.MCX":      "MCX Gold",
    "SILVER.MCX":    "MCX Silver",
    "IOC.NS":        "IOC",
    "ADANIPORTS.NS": "Adani Ports",
}


def _pct(current: float, baseline: float) -> float:
    if not baseline:
        return 0.0
    return round((current - baseline) / baseline * 100, 2)


def _fmt(ticker: str, price: float) -> str:
    """Format price for display."""
    if ticker == "INR=X" or "NS" in ticker:
        return f"₹{price:,.2f}".replace(".00", "")
    if ticker == "ZW=F":
        return f"{price:.0f}¢"
    if ticker in ("GOLD.MCX", "SILVER.MCX"):
        return f"₹{price:,.0f}"
    if ticker == "CRUDEOIL.MCX":
        return f"₹{price:,.0f}"
    if ticker == "GC=F":
        return f"${price:,.0f}"
    return f"${price:.3f}" if price < 10 else f"${price:,.2f}"


def fetch_prices() -> dict:
    """Fetch all tickers via yfinance. Returns dict of ticker -> price data."""
    tickers = list(WAR_BASELINE.keys())
    prices = {}

    print("  Fetching prices via yfinance...")
    try:
        data = yf.download(
            tickers,
            period="2d",
            interval="1d",
            group_by="ticker",
            auto_adjust=True,
            progress=False,
            timeout=30,
        )
    except Exception as e:
        print(f"  [ERROR] yfinance download failed: {e}")
        return {}

    for ticker in tickers:
        try:
            if len(tickers) == 1:
                df = data
            else:
                df = data[ticker]

            if df is None or df.empty or len(df) < 1:
                print(f"  [WARN] No data for {ticker}")
                continue

            close = df["Close"].dropna()
            if len(close) < 1:
                continue

            current = float(close.iloc[-1])
            prev    = float(close.iloc[-2]) if len(close) >= 2 else current
            baseline = WAR_BASELINE.get(ticker, current)

            day_pct = _pct(current, prev)
            war_pct = _pct(current, baseline)

            prices[ticker] = {
                "name":      NAMES.get(ticker, ticker),
                "price":     round(current, 4),
                "formatted": _fmt(ticker, current),
                "day_pct":   day_pct,
                "war_pct":   war_pct,
            }
            print(f"    {ticker}: {prices[ticker]['formatted']} ({day_pct:+.2f}% today, {war_pct:+.1f}% since war)")

        except Exception as e:
            print(f"  [WARN] Failed to process {ticker}: {e}")

    return prices


def compute_india(prices: dict) -> dict:
    """Compute Indian-specific derived values."""
    mcx_crude = prices.get("CRUDEOIL.MCX", {}).get("price", 7842)
    inr       = prices.get("INR=X", {}).get("price", 85.42)

    # Petrol pump estimate (Delhi retail)
    # Formula: MCX crude ÷ 159L × 1.08 (refining/transport) + ₹52.5 taxes + ₹3.8 margins
    pump_raw = (mcx_crude / 159) * 1.08 + 52.5 + 3.8
    pump_baseline = (6350 / 159) * 1.08 + 52.5 + 3.8  # war day 1 baseline
    war_change = round(pump_raw - pump_baseline, 1)

    # Gold/Silver ratio
    gold_mcx   = prices.get("GOLD.MCX", {}).get("price", 88240)
    silver_mcx = prices.get("SILVER.MCX", {}).get("price", 102400)
    gs_ratio   = round(gold_mcx / (silver_mcx / 100), 1) if silver_mcx else 86.2

    return {
        "petrolPump": {
            "formatted":   f"₹{pump_raw:.1f}",
            "war_change":  war_change,
            "formula":     f"MCX crude ÷ 159L × 1.08 + ₹52.5 taxes + ₹3.8 margins · Delhi est.",
        },
        "goldSilverRatio": gs_ratio,
    }


def load_history() -> list:
    """Load price history from file."""
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text())
        except Exception:
            pass
    # Return built-in baseline history if file missing
    return [
        {"date":"2026-03-10","brent":76.2,"wti":73.1,"ng":2.88,"gold":2690,"wheat":535,"inr":82.1,"mcx_crude":6350,"mcx_gold":74800,"mcx_silver":91500,"ioc":160.5,"adani":1233},
        {"date":"2026-03-11","brent":79.4,"wti":76.2,"ng":2.91,"gold":2714,"wheat":538,"inr":82.4,"mcx_crude":6580,"mcx_gold":75200,"mcx_silver":92100,"ioc":157.2,"adani":1241},
        {"date":"2026-03-12","brent":84.1,"wti":80.8,"ng":2.95,"gold":2741,"wheat":542,"inr":82.9,"mcx_crude":6980,"mcx_gold":76100,"mcx_silver":93400,"ioc":153.8,"adani":1248},
        {"date":"2026-03-13","brent":88.7,"wti":85.3,"ng":2.99,"gold":2798,"wheat":548,"inr":83.3,"mcx_crude":7360,"mcx_gold":77400,"mcx_silver":95200,"ioc":150.1,"adani":1256},
        {"date":"2026-03-14","brent":86.2,"wti":83.0,"ng":3.01,"gold":2781,"wheat":545,"inr":83.1,"mcx_crude":7150,"mcx_gold":76800,"mcx_silver":94600,"ioc":151.4,"adani":1252},
        {"date":"2026-03-15","brent":89.5,"wti":86.1,"ng":3.04,"gold":2830,"wheat":549,"inr":83.6,"mcx_crude":7430,"mcx_gold":78200,"mcx_silver":96800,"ioc":148.6,"adani":1261},
        {"date":"2026-03-16","brent":91.8,"wti":88.4,"ng":3.07,"gold":2872,"wheat":551,"inr":84.0,"mcx_crude":7620,"mcx_gold":80100,"mcx_silver":98400,"ioc":146.2,"adani":1268},
        {"date":"2026-03-17","brent":94.1,"wti":90.6,"ng":3.10,"gold":2921,"wheat":554,"inr":84.5,"mcx_crude":7812,"mcx_gold":82400,"mcx_silver":100200,"ioc":144.1,"adani":1274},
        {"date":"2026-03-18","brent":92.7,"wti":89.1,"ng":3.09,"gold":2908,"wheat":552,"inr":84.8,"mcx_crude":7690,"mcx_gold":84100,"mcx_silver":99800,"ioc":145.0,"adani":1271},
        {"date":"2026-03-19","brent":93.8,"wti":90.3,"ng":3.11,"gold":2948,"wheat":553,"inr":85.1,"mcx_crude":7780,"mcx_gold":86200,"mcx_silver":101100,"ioc":143.2,"adani":1278},
        {"date":"2026-03-20","brent":94.8,"wti":91.3,"ng":3.12,"gold":3082,"wheat":606,"inr":85.42,"mcx_crude":7842,"mcx_gold":88240,"mcx_silver":102400,"ioc":142.3,"adani":1284},
    ]


def append_today_to_history(history: list, prices: dict) -> list:
    """Add today's prices to history, avoiding duplicate dates."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    # Remove any existing entry for today
    history = [h for h in history if h.get("date") != today]

    def g(ticker, key="price"):
        return prices.get(ticker, {}).get(key, 0)

    history.append({
        "date":       today,
        "brent":      round(g("BZ=F"), 2),
        "wti":        round(g("CL=F"), 2),
        "ng":         round(g("NG=F"), 3),
        "gold":       round(g("GC=F")),
        "wheat":      round(g("ZW=F")),
        "inr":        round(g("INR=X"), 2),
        "mcx_crude":  round(g("CRUDEOIL.MCX")),
        "mcx_gold":   round(g("GOLD.MCX")),
        "mcx_silver": round(g("SILVER.MCX")),
        "ioc":        round(g("IOC.NS"), 1),
        "adani":      round(g("ADANIPORTS.NS")),
    })

    # Keep last 60 days max
    return history[-60:]


def build_prices_js():
    """Main entry point — fetch prices and write prices_data.js."""
    prices  = fetch_prices()

    if not prices:
        print("  [WARN] No prices fetched — prices_data.js not updated.")
        return

    india   = compute_india(prices)
    history = load_history()
    history = append_today_to_history(history, prices)

    # Save history for next run
    HISTORY_FILE.write_text(json.dumps(history, indent=2))

    payload = {
        "fetchedAt": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "prices":    prices,
        "india":     india,
        "history":   history,
    }

    js = "window.WARWATCH_PRICES = " + json.dumps(payload, indent=2) + ";\n"
    PRICES_DATA_JS.write_text(js, encoding="utf-8")
    print(f"  [OK] prices_data.js written — {len(prices)} tickers, {len(history)} history points")


if __name__ == "__main__":
    build_prices_js()
    print("Done. Open economy.html in your browser.")