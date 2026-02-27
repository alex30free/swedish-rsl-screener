#!/usr/bin/env python3
"""
Levy RSL Momentum Screener for Swedish Stocks
Computes Relative Strength Levy (RSL) = Current Price / 130-day (26-week) SMA
Ranks all stocks, saves top 20 + full skip log to JSON for the webpage.
"""

import json
import os
import time
import datetime
import warnings
warnings.filterwarnings("ignore")

try:
    import yfinance as yf
    import pandas as pd
except ImportError:
    print("ERROR: Run: pip install yfinance pandas")
    raise

from fetch_swedish_tickers import get_tickers

TICKERS = get_tickers(verbose=True)


RSL_PERIOD = 130  # trading days (~26 weeks)
OUTPUT_JSON = "screener_data.json"
PREV_RANKS_FILE = "prev_ranks.json"


def compute_rsl(tickers, period=130):
    results = []
    skipped = []
    total = len(tickers)

    end_date   = datetime.datetime.today()
    start_date = end_date - datetime.timedelta(days=400)

    print("=" * 65)
    print("  Levy RSL Screener — OMX Stockholm")
    print("  Universe: " + str(total) + " tickers (Large + Mid + Small Cap)")
    print("  Running at: " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
    print("=" * 65)
    print("")

    for i, (name, symbol) in enumerate(tickers):
        print("[" + str(i + 1).rjust(3) + "/" + str(total) + "] " + symbol.ljust(20), end="", flush=True)

        try:
            stock = yf.Ticker(symbol)
            hist  = stock.history(
                start=start_date.strftime("%Y-%m-%d"),
                end=end_date.strftime("%Y-%m-%d"),
                auto_adjust=True
            )

            if hist.empty or len(hist) == 0:
                skipped.append({
                    "name": name, "ticker": symbol,
                    "reason": "No price data returned", "days_available": 0
                })
                print("X  No price data")
                time.sleep(0.3)
                continue

            series = hist["Close"].dropna()
            days   = len(series)

            if days < period:
                skipped.append({
                    "name": name, "ticker": symbol,
                    "reason": "Insufficient history - needs " + str(period) + " days, only " + str(days) + " available",
                    "days_available": days
                })
                print("X  Only " + str(days) + "/" + str(period) + " days of history")
                time.sleep(0.3)
                continue

            current_price = float(series.iloc[-1])
            sma           = float(series.iloc[-period:].mean())
            rsl           = current_price / sma

            results.append({
                "name":   name,
                "ticker": symbol,
                "price":  round(current_price, 2),
                "sma130": round(sma, 2),
                "rsl":    round(rsl, 4),
            })

            print("OK  Price=" + str(round(current_price, 2)).rjust(9) +
                  "  SMA130=" + str(round(sma, 2)).rjust(9) +
                  "  RSL=" + str(round(rsl, 4)))

        except Exception as e:
            skipped.append({
                "name": name, "ticker": symbol,
                "reason": "Error: " + str(e)[:60], "days_available": 0
            })
            print("X  " + str(e)[:50])

        time.sleep(0.3)

    print("")
    print("-" * 65)
    print("  Valid: " + str(len(results)) + " stocks   Skipped: " + str(len(skipped)))
    print("-" * 65)

    results.sort(key=lambda x: x["rsl"], reverse=True)
    for i, r in enumerate(results):
        r["rank"] = i + 1

    skipped.sort(key=lambda x: x["days_available"])
    return results, skipped


def load_prev_ranks():
    if os.path.exists(PREV_RANKS_FILE):
        with open(PREV_RANKS_FILE) as f:
            return json.load(f)
    return {}


def save_prev_ranks(top20):
    ranks = {r["ticker"]: r["rank"] for r in top20}
    with open(PREV_RANKS_FILE, "w") as f:
        json.dump(ranks, f)


def main():
    now = datetime.datetime.now(datetime.timezone.utc)

    all_stocks, skipped = compute_rsl(TICKERS, RSL_PERIOD)
    top20 = all_stocks[:20]

    prev_ranks = load_prev_ranks()
    for r in top20:
        r["prev_rank"] = prev_ranks.get(r["ticker"], None)

    save_prev_ranks(top20)

    not_found  = [s for s in skipped if s["days_available"] == 0 and "Not found" in s["reason"]]
    no_data    = [s for s in skipped if s["days_available"] == 0 and "No price" in s["reason"]]
    short_hist = [s for s in skipped if s["days_available"] > 0]
    errors     = [s for s in skipped if "Error:" in s["reason"]]

    print("")
    print("--- SKIP SUMMARY ---")
    print("  Total attempted     : " + str(len(TICKERS)))
    print("  Successfully loaded : " + str(len(all_stocks)))
    print("  Skipped total       : " + str(len(skipped)))
    print("    Not found on Yahoo Finance   : " + str(len(not_found)))
    print("    No price data                : " + str(len(no_data)))
    print("    Insufficient history <130d   : " + str(len(short_hist)))
    print("    Other errors                 : " + str(len(errors)))

    output = {
        "updated":         now.strftime("%Y-%m-%d %H:%M UTC"),
        "period_days":     RSL_PERIOD,
        "total_attempted": len(TICKERS),
        "stocks_screened": len(all_stocks),
        "skipped_count":   len(skipped),
        "top20":           top20,
        "skipped":         skipped,
    }

    with open(OUTPUT_JSON, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print("")
    print("=" * 65)
    print("  TOP 20 — LEVY RSL RANKING")
    print("=" * 65)
    for r in top20:
        prev = "(prev #" + str(r["prev_rank"]) + ")" if r["prev_rank"] else "(new)"
        print("  #" + str(r["rank"]).rjust(2) + "  RSL=" + str(r["rsl"]) +
              "  " + r["name"] + "  " + prev)

    print("")
    print("Saved " + OUTPUT_JSON)


if __name__ == "__main__":
    main()
