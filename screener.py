#!/usr/bin/env python3
"""
Levy RSL Momentum Screener for Swedish Stocks
Computes Relative Strength Levy (RSL) = Current Price / 130-day (26-week) SMA
Computes Piotroski F-Score (0-9) from annual financial statements.

Filters applied:
  - Minimum market cap:  500M SEK  (removes nano/micro-caps)
  - Minimum history:     130 trading days (~26 weeks)
  - F-Score filter:      >= 5 passes into Top 20
                         1-4 -> "Momentum Watchlist" (top 3 by RSL shown separately)
                         0   -> excluded entirely

Output JSON sections:
  top20        -- RSL-ranked, F-Score >= 5, market cap >= 500M SEK
  watchlist    -- top 3 by RSL among stocks with F-Score 1-4
  skipped      -- stocks excluded for data/history/market cap reasons
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
    import numpy as np
except ImportError:
    print("ERROR: Run: pip install yfinance pandas numpy")
    raise

from fetch_swedish_tickers import get_tickers

TICKERS         = get_tickers(verbose=True)
RSL_PERIOD      = 130          # trading days (~26 weeks)
MIN_MARKET_CAP  = 500_000_000  # 500M SEK
MIN_FSCORE      = 5            # minimum F-Score to appear in Top 20
WATCHLIST_COUNT = 3            # how many low-F-Score momentum stocks to show
OUTPUT_JSON     = "screener_data.json"
PREV_RANKS_FILE = "prev_ranks.json"


# -----------------------------------------------------------------------------
# F-SCORE
# -----------------------------------------------------------------------------

def _safe(df, row_keys, col_idx=0):
    """
    Safely extract a scalar from a yfinance financial DataFrame.
    Tries multiple row-key aliases (Yahoo Finance label names vary).
    Returns float or NaN.
    """
    if df is None or df.empty:
        return float("nan")
    for key in row_keys:
        if key in df.index:
            try:
                val = df.loc[key].iloc[col_idx]
                if val is not None and not (isinstance(val, float) and np.isnan(val)):
                    return float(val)
            except Exception:
                continue
    return float("nan")


def compute_fscore(stock) -> tuple:
    """
    Compute Piotroski F-Score (0-9) from yfinance annual financials.

    Returns:
        (score, detail_dict)
        score is None if insufficient data to compute.
    """
    detail = {
        "f1_roa":            None,
        "f2_cfo":            None,
        "f3_roa_change":     None,
        "f4_accruals":       None,
        "f5_leverage":       None,
        "f6_liquidity":      None,
        "f7_dilution":       None,
        "f8_gross_margin":   None,
        "f9_asset_turnover": None,
    }

    try:
        fin = stock.financials
        bal = stock.balance_sheet
        cf  = stock.cashflow

        # Need at least 2 years of data for YoY comparisons
        if fin is None or fin.empty or fin.shape[1] < 2:
            return None, detail
        if bal is None or bal.empty or bal.shape[1] < 2:
            return None, detail
        if cf is None or cf.empty:
            return None, detail

        # Extract values (col 0 = current year, col 1 = prior year)
        net_income_0  = _safe(fin, ["Net Income", "NetIncome", "Net Income Common Stockholders"])
        net_income_1  = _safe(fin, ["Net Income", "NetIncome", "Net Income Common Stockholders"], 1)
        revenue_0     = _safe(fin, ["Total Revenue", "Revenue", "TotalRevenue"])
        revenue_1     = _safe(fin, ["Total Revenue", "Revenue", "TotalRevenue"], 1)
        gross_0       = _safe(fin, ["Gross Profit", "GrossProfit"])
        gross_1       = _safe(fin, ["Gross Profit", "GrossProfit"], 1)

        assets_0      = _safe(bal, ["Total Assets", "TotalAssets"])
        assets_1      = _safe(bal, ["Total Assets", "TotalAssets"], 1)
        lt_debt_0     = _safe(bal, ["Long Term Debt", "LongTermDebt", "Long-Term Debt"])
        lt_debt_1     = _safe(bal, ["Long Term Debt", "LongTermDebt", "Long-Term Debt"], 1)
        curr_assets_0 = _safe(bal, ["Current Assets", "Total Current Assets", "TotalCurrentAssets"])
        curr_assets_1 = _safe(bal, ["Current Assets", "Total Current Assets", "TotalCurrentAssets"], 1)
        curr_liab_0   = _safe(bal, ["Current Liabilities", "Total Current Liabilities", "TotalCurrentLiabilities"])
        curr_liab_1   = _safe(bal, ["Current Liabilities", "Total Current Liabilities", "TotalCurrentLiabilities"], 1)
        shares_0      = _safe(bal, ["Share Issued", "Common Stock", "Ordinary Shares Number",
                                    "Shares Outstanding", "CommonStock"])
        shares_1      = _safe(bal, ["Share Issued", "Common Stock", "Ordinary Shares Number",
                                    "Shares Outstanding", "CommonStock"], 1)

        cfo_0         = _safe(cf, ["Operating Cash Flow", "Total Cash From Operating Activities",
                                   "Cash Flow From Continuing Operating Activities"])

        # Derived ratios
        def nan(v):
            return isinstance(v, float) and np.isnan(v)

        roa_0 = net_income_0 / assets_0 if not nan(assets_0) and assets_0 != 0 else float("nan")
        roa_1 = net_income_1 / assets_1 if not nan(assets_1) and assets_1 != 0 else float("nan")

        dr_0  = lt_debt_0 / assets_0 if (not nan(lt_debt_0) and not nan(assets_0) and assets_0 != 0) else float("nan")
        dr_1  = lt_debt_1 / assets_1 if (not nan(lt_debt_1) and not nan(assets_1) and assets_1 != 0) else float("nan")

        cr_0  = curr_assets_0 / curr_liab_0 if (not nan(curr_liab_0) and curr_liab_0 != 0) else float("nan")
        cr_1  = curr_assets_1 / curr_liab_1 if (not nan(curr_liab_1) and curr_liab_1 != 0) else float("nan")

        gm_0  = gross_0 / revenue_0 if (not nan(revenue_0) and revenue_0 != 0) else float("nan")
        gm_1  = gross_1 / revenue_1 if (not nan(revenue_1) and revenue_1 != 0) else float("nan")

        at_0  = revenue_0 / assets_0 if (not nan(assets_0) and assets_0 != 0) else float("nan")
        at_1  = revenue_1 / assets_1 if (not nan(assets_1) and assets_1 != 0) else float("nan")

        acc   = (cfo_0 / assets_0 - roa_0) if (not nan(cfo_0) and not nan(assets_0) and assets_0 != 0) else float("nan")

        def s(cond):
            try:
                return 1 if bool(cond) else 0
            except Exception:
                return 0

        def v(*vals):
            return all(not (isinstance(x, float) and np.isnan(x)) for x in vals)

        detail["f1_roa"]            = s(v(roa_0) and roa_0 > 0)
        detail["f2_cfo"]            = s(v(cfo_0) and cfo_0 > 0)
        detail["f3_roa_change"]     = s(v(roa_0, roa_1) and roa_0 > roa_1)
        detail["f4_accruals"]       = s(v(acc) and acc > 0)
        detail["f5_leverage"]       = s(v(dr_0, dr_1) and dr_0 < dr_1)
        detail["f6_liquidity"]      = s(v(cr_0, cr_1) and cr_0 > cr_1)
        detail["f7_dilution"]       = s(v(shares_0, shares_1) and shares_0 <= shares_1)
        detail["f8_gross_margin"]   = s(v(gm_0, gm_1) and gm_0 > gm_1)
        detail["f9_asset_turnover"] = s(v(at_0, at_1) and at_0 > at_1)

        score = sum(x for x in detail.values() if x is not None)
        return score, detail

    except Exception:
        return None, detail


# -----------------------------------------------------------------------------
# MARKET CAP
# -----------------------------------------------------------------------------

def get_market_cap_sek(info):
    mcap = info.get("marketCap")
    if mcap and mcap > 0:
        return float(mcap)
    return None


# -----------------------------------------------------------------------------
# MAIN COMPUTE LOOP
# -----------------------------------------------------------------------------

def compute_all(tickers, period=130):
    results              = []
    watchlist_candidates = []
    skipped              = []
    total                = len(tickers)

    end_date   = datetime.datetime.today()
    start_date = end_date - datetime.timedelta(days=400)

    print("=" * 70)
    print("  Levy RSL + Piotroski F-Score Screener -- OMX Stockholm")
    print("  Universe   : " + str(total) + " tickers (Large + Mid + Small Cap)")
    print("  Min MCap   : " + str(MIN_MARKET_CAP // 1_000_000) + "M SEK")
    print("  Min F-Score: " + str(MIN_FSCORE) + "  (1-" + str(MIN_FSCORE - 1) + " -> Watchlist, 0 -> excluded)")
    print("  Running at : " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
    print("=" * 70)
    print("")

    for i, (name, symbol) in enumerate(tickers):
        print("[" + str(i + 1).rjust(3) + "/" + str(total) + "] " + symbol.ljust(22), end="", flush=True)

        try:
            stock = yf.Ticker(symbol)
            info  = stock.info

            # Market cap filter
            mcap = get_market_cap_sek(info)
            if mcap is not None and mcap < MIN_MARKET_CAP:
                skipped.append({
                    "name": name, "ticker": symbol,
                    "reason": "Market cap too small (" + str(round(mcap / 1e6)) + "M SEK < " + str(MIN_MARKET_CAP // 1_000_000) + "M SEK)",
                    "days_available": 0
                })
                print("X  MCap " + str(round(mcap / 1e6)) + "M SEK -- below minimum")
                time.sleep(0.35)
                continue

            # Price history
            hist = stock.history(
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
                time.sleep(0.35)
                continue

            series = hist["Close"].dropna()
            days   = len(series)

            if days < period:
                skipped.append({
                    "name": name, "ticker": symbol,
                    "reason": "Insufficient history - needs " + str(period) + " days, only " + str(days) + " available",
                    "days_available": days
                })
                print("X  Only " + str(days) + "/" + str(period) + " days")
                time.sleep(0.35)
                continue

            current_price = float(series.iloc[-1])
            sma           = float(series.iloc[-period:].mean())
            rsl           = round(current_price / sma, 4)

            # F-Score
            fscore, fdetail = compute_fscore(stock)
            fscore_str = str(fscore) if fscore is not None else "N/A"
            mcap_str   = "  MCap=" + str(round(mcap / 1e9, 1)) + "B" if mcap else ""

            print("OK  RSL=" + str(rsl) + "  F=" + fscore_str + mcap_str)

            record = {
                "name":          name,
                "ticker":        symbol,
                "price":         round(current_price, 2),
                "sma130":        round(sma, 2),
                "rsl":           rsl,
                "market_cap":    round(mcap / 1e6) if mcap else None,
                "fscore":        fscore,
                "fscore_detail": fdetail,
            }

            # Route: main list, watchlist, or excluded
            if fscore is None or fscore >= MIN_FSCORE:
                results.append(record)
            elif 1 <= fscore <= (MIN_FSCORE - 1):
                watchlist_candidates.append(record)
            # fscore == 0 -> excluded entirely

        except Exception as e:
            skipped.append({
                "name": name, "ticker": symbol,
                "reason": "Error: " + str(e)[:60], "days_available": 0
            })
            print("X  " + str(e)[:55])

        time.sleep(0.35)

    # Sort and rank
    results.sort(key=lambda x: x["rsl"], reverse=True)
    for idx, r in enumerate(results):
        r["rank"] = idx + 1

    watchlist_candidates.sort(key=lambda x: x["rsl"], reverse=True)
    watchlist = watchlist_candidates[:WATCHLIST_COUNT]
    for idx, r in enumerate(watchlist):
        r["watchlist_rank"] = idx + 1

    skipped.sort(key=lambda x: x["days_available"])

    print("")
    print("-" * 70)
    print("  Passed filters : " + str(len(results)) + " stocks")
    print("  Watchlist pool : " + str(len(watchlist_candidates)) + " stocks  (F-Score 1-" + str(MIN_FSCORE - 1) + ")")
    print("  Skipped        : " + str(len(skipped)) + " stocks")
    print("-" * 70)

    return results, watchlist, skipped


# -----------------------------------------------------------------------------
# PREV RANKS
# -----------------------------------------------------------------------------

def load_prev_ranks():
    if os.path.exists(PREV_RANKS_FILE):
        with open(PREV_RANKS_FILE) as f:
            return json.load(f)
    return {}


def save_prev_ranks(top20):
    ranks = {r["ticker"]: r["rank"] for r in top20}
    with open(PREV_RANKS_FILE, "w") as f:
        json.dump(ranks, f)


# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------

def main():
    now = datetime.datetime.now(datetime.timezone.utc)

    all_stocks, watchlist, skipped = compute_all(TICKERS, RSL_PERIOD)
    top20 = all_stocks[:20]

    prev_ranks = load_prev_ranks()
    for r in top20:
        r["prev_rank"] = prev_ranks.get(r["ticker"], None)
    save_prev_ranks(top20)

    mcap_skip  = [s for s in skipped if "Market cap" in s["reason"]]
    short_hist = [s for s in skipped if s["days_available"] > 0]
    no_data    = [s for s in skipped if "No price" in s["reason"]]
    not_found  = [s for s in skipped if "Not found" in s["reason"]]
    errors     = [s for s in skipped if "Error:" in s["reason"]]

    print("")
    print("--- SKIP SUMMARY ---")
    print("  Total attempted          : " + str(len(TICKERS)))
    print("  Passed all filters       : " + str(len(all_stocks)))
    print("  Watchlist (F<" + str(MIN_FSCORE) + ")         : " + str(len(watchlist)))
    print("  Skipped total            : " + str(len(skipped)))
    print("    Market cap too small   : " + str(len(mcap_skip)))
    print("    Insufficient history   : " + str(len(short_hist)))
    print("    No price data          : " + str(len(no_data)))
    print("    Not found on Yahoo     : " + str(len(not_found)))
    print("    Other errors           : " + str(len(errors)))

    output = {
        "updated":          now.strftime("%Y-%m-%d %H:%M UTC"),
        "period_days":      RSL_PERIOD,
        "min_market_cap_m": MIN_MARKET_CAP // 1_000_000,
        "min_fscore":       MIN_FSCORE,
        "total_attempted":  len(TICKERS),
        "stocks_screened":  len(all_stocks),
        "skipped_count":    len(skipped),
        "top20":            top20,
        "watchlist":        watchlist,
        "skipped":          skipped,
    }

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print("")
    print("=" * 70)
    print("  TOP 20 -- RSL RANKED, F-Score >= " + str(MIN_FSCORE))
    print("=" * 70)
    for r in top20:
        prev   = "(prev #" + str(r["prev_rank"]) + ")" if r["prev_rank"] else "(new)"
        fstr   = "  F=" + str(r["fscore"]) if r["fscore"] is not None else "  F=N/A"
        mcap_s = "  MCap=" + str(r["market_cap"]) + "M" if r.get("market_cap") else ""
        print("  #" + str(r["rank"]).rjust(2) + "  RSL=" + str(r["rsl"]) +
              "  " + r["name"] + "  " + prev + fstr + mcap_s)

    if watchlist:
        print("")
        print("=" * 70)
        print("  MOMENTUM WATCHLIST -- High RSL but F-Score < " + str(MIN_FSCORE))
        print("=" * 70)
        for r in watchlist:
            print("  #" + str(r["watchlist_rank"]) + "  RSL=" + str(r["rsl"]) +
                  "  F=" + str(r["fscore"]) + "  " + r["name"])

    print("\nSaved -> " + OUTPUT_JSON)


if __name__ == "__main__":
    main()
