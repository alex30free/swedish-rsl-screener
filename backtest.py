#!/usr/bin/env python3
"""
backtest.py — Swedish RSL Momentum Strategy Backtest
=====================================================
Simulates the Levy RSL strategy weekly over the past 10 years.
Compares against OMXSPI (Stockholm All-Share Index) as benchmark.

IMPORTANT — SURVIVORSHIP BIAS WARNING:
  This backtest uses today's ticker universe only. Stocks that were
  delisted, went bankrupt, or were acquired during the backtest period
  are NOT included. This inflates returns vs reality. Results should be
  treated as directional, not precise.

OUTPUT:
  backtest_results.json — loaded by backtest.html to render charts/tables

HOW TO RUN:
  pip install yfinance pandas numpy
  python backtest.py

Runtime: ~20-40 minutes (downloads 10y of daily data for ~300+ tickers)
"""

import json
import time
import datetime
import warnings
import math
warnings.filterwarnings("ignore")

try:
    import yfinance as yf
    import pandas as pd
    import numpy as np
except ImportError:
    print("ERROR: Run: pip install yfinance pandas numpy")
    raise

from fetch_swedish_tickers import get_tickers

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────

RSL_PERIOD       = 130          # trading days for SMA
TOP_N            = 20           # portfolio size
REBALANCE_DAY    = 4            # 4 = Friday
INITIAL_CAPITAL  = 100.0        # index start value (100 = easy % reading)
BENCHMARK_TICKER = "^OMX"       # OMXSPI — Stockholm All-Share
YEARS_BACK       = 10
MIN_MARKET_CAP   = 500_000_000  # 500M SEK — same as live screener

EXCLUDED_SECTORS = {
    "Financial Services", "Financials", "Banking", "Insurance",
    "Asset Management", "Capital Markets", "Banks",
    "Diversified Financials", "Consumer Finance", "Mortgage Finance",
}

OUTPUT_JSON = "backtest_results.json"

# ─────────────────────────────────────────────────────────────────────────────
# DATE RANGE
# ─────────────────────────────────────────────────────────────────────────────

END_DATE   = datetime.date.today()
START_DATE = END_DATE - datetime.timedelta(days=YEARS_BACK * 365 + 60)  # extra buffer

# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 — DOWNLOAD ALL PRICE DATA
# ─────────────────────────────────────────────────────────────────────────────

def download_all_prices(tickers_list):
    """
    Download 10y of daily close prices for all tickers in one batch call.
    Returns a DataFrame: index=dates, columns=ticker symbols.
    """
    symbols = [t for _, t in tickers_list]

    print(f"\nDownloading {len(symbols)} tickers from {START_DATE} to {END_DATE}…")
    print("(This may take a few minutes — batch download)\n")

    raw = yf.download(
        symbols,
        start=START_DATE.strftime("%Y-%m-%d"),
        end=END_DATE.strftime("%Y-%m-%d"),
        auto_adjust=True,
        progress=True,
        threads=True,
    )

    if isinstance(raw.columns, pd.MultiIndex):
        prices = raw["Close"]
    else:
        prices = raw[["Close"]] if "Close" in raw.columns else raw

    # Drop columns with almost no data (< 30 trading days)
    prices = prices.dropna(axis=1, thresh=30)
    prices.index = pd.to_datetime(prices.index).tz_localize(None).normalize()

    print(f"\nDownloaded {prices.shape[1]} tickers with usable price history.")
    return prices


def download_benchmark():
    """Download benchmark index prices."""
    print(f"\nDownloading benchmark {BENCHMARK_TICKER}…")
    raw = yf.download(
        BENCHMARK_TICKER,
        start=START_DATE.strftime("%Y-%m-%d"),
        end=END_DATE.strftime("%Y-%m-%d"),
        auto_adjust=True,
        progress=False,
    )
    if isinstance(raw.columns, pd.MultiIndex):
        s = raw["Close"].squeeze()
    else:
        s = raw["Close"] if "Close" in raw.columns else raw.squeeze()
    s.index = pd.to_datetime(s.index).tz_localize(None).normalize()
    return s.dropna()


# ─────────────────────────────────────────────────────────────────────────────
# STEP 2 — FETCH SECTOR / MARKET CAP METADATA (once per ticker)
# ─────────────────────────────────────────────────────────────────────────────

def fetch_metadata(tickers_list):
    """
    Fetch sector and market cap for each ticker.
    Returns dict: ticker -> {sector, mcap}
    NOTE: market cap is CURRENT — we have no historical mcap data.
          Using it as a rough proxy to exclude nano-caps consistently.
    """
    meta = {}
    total = len(tickers_list)
    print(f"\nFetching sector/mcap metadata for {total} tickers…")

    for i, (name, symbol) in enumerate(tickers_list):
        print(f"  [{i+1:>3}/{total}] {symbol:<20}", end="", flush=True)
        try:
            info   = yf.Ticker(symbol).info
            sector = (info.get("sector") or info.get("industry") or "").strip()
            mcap   = info.get("marketCap")
            meta[symbol] = {"sector": sector, "mcap": float(mcap) if mcap else None}
            print(f"  {sector or '—'}")
        except Exception as e:
            meta[symbol] = {"sector": "", "mcap": None}
            print(f"  error: {str(e)[:40]}")
        time.sleep(0.25)

    return meta


# ─────────────────────────────────────────────────────────────────────────────
# STEP 3 — IDENTIFY WEEKLY REBALANCE DATES
# ─────────────────────────────────────────────────────────────────────────────

def get_rebalance_dates(price_index, rebalance_weekday=4):
    """
    Return one trading date per week (last trading day of each week
    that falls on or before Friday), starting after RSL_PERIOD is available.
    """
    dates = pd.Series(price_index)
    # Group by ISO week, take last date in each week
    weekly = dates.groupby([dates.dt.isocalendar().year,
                            dates.dt.isocalendar().week]).last()
    # Need at least RSL_PERIOD + some buffer before first rebalance
    cutoff = price_index[RSL_PERIOD + 10]
    weekly = weekly[weekly >= cutoff]
    return weekly.values


# ─────────────────────────────────────────────────────────────────────────────
# STEP 4 — COMPUTE RSL AND SELECT PORTFOLIO ON A GIVEN DATE
# ─────────────────────────────────────────────────────────────────────────────

def select_portfolio(prices, metadata, as_of_date, period=RSL_PERIOD, top_n=TOP_N):
    """
    Given price data up to as_of_date, compute RSL for all eligible stocks
    and return the top N tickers by RSL.
    """
    # Slice prices up to as_of_date
    hist = prices[prices.index <= pd.Timestamp(as_of_date)]

    eligible = []
    for col in hist.columns:
        series = hist[col].dropna()
        if len(series) < period:
            continue

        # Sector/mcap filter (using current metadata as proxy)
        m = metadata.get(col, {})
        if m.get("sector") in EXCLUDED_SECTORS:
            continue
        mcap = m.get("mcap")
        if mcap is not None and mcap < MIN_MARKET_CAP:
            continue

        current_price = float(series.iloc[-1])
        sma           = float(series.iloc[-period:].mean())
        if sma == 0:
            continue
        rsl = current_price / sma
        eligible.append((col, rsl))

    eligible.sort(key=lambda x: x[1], reverse=True)
    return [t for t, _ in eligible[:top_n]]


# ─────────────────────────────────────────────────────────────────────────────
# STEP 5 — RUN THE BACKTEST
# ─────────────────────────────────────────────────────────────────────────────

def run_backtest(prices, benchmark, metadata):
    rebalance_dates = get_rebalance_dates(prices.index)
    print(f"\nRunning backtest over {len(rebalance_dates)} weekly periods…")

    portfolio_value  = INITIAL_CAPITAL
    benchmark_value  = INITIAL_CAPITAL
    current_holdings = []

    equity_curve  = []   # {date, portfolio, benchmark}
    weekly_log    = []   # detailed weekly log
    annual_returns = {}  # year -> {strategy, benchmark}

    prev_date = None

    for i, rebal_date in enumerate(rebalance_dates):
        rebal_ts = pd.Timestamp(rebal_date)

        # ── Benchmark return since last period ────────────────────────────
        if prev_date is not None:
            prev_ts = pd.Timestamp(prev_date)

            # Benchmark
            bm_slice = benchmark[(benchmark.index > prev_ts) & (benchmark.index <= rebal_ts)]
            if len(bm_slice) >= 2:
                bm_ret = bm_slice.iloc[-1] / bm_slice.iloc[0] - 1
            elif prev_ts in benchmark.index and rebal_ts in benchmark.index:
                bm_ret = benchmark.loc[rebal_ts] / benchmark.loc[prev_ts] - 1
            else:
                bm_ret = 0.0
            benchmark_value *= (1 + bm_ret)

            # Portfolio — equal weight across holdings
            if current_holdings:
                port_rets = []
                for ticker in current_holdings:
                    if ticker not in prices.columns:
                        continue
                    s = prices[ticker]
                    s_slice = s[(s.index > prev_ts) & (s.index <= rebal_ts)].dropna()
                    if len(s_slice) >= 1:
                        # Use last known price before period start
                        prev_price_slice = s[s.index <= prev_ts].dropna()
                        if len(prev_price_slice) == 0:
                            continue
                        p0 = float(prev_price_slice.iloc[-1])
                        p1 = float(s_slice.iloc[-1])
                        if p0 > 0:
                            port_rets.append(p1 / p0 - 1)

                if port_rets:
                    avg_ret = sum(port_rets) / len(port_rets)
                    portfolio_value *= (1 + avg_ret)

            # Log annual returns
            year = rebal_ts.year
            prev_year = pd.Timestamp(prev_date).year
            if year not in annual_returns:
                annual_returns[year] = {"port_start": portfolio_value / (1 + avg_ret if port_rets else 1),
                                        "bm_start":   benchmark_value / (1 + bm_ret)}
            annual_returns[year]["port_end"] = portfolio_value
            annual_returns[year]["bm_end"]   = benchmark_value

        # ── Select new portfolio ──────────────────────────────────────────
        new_holdings = select_portfolio(prices, metadata, rebal_date)
        current_holdings = new_holdings

        # ── Record equity curve point ─────────────────────────────────────
        equity_curve.append({
            "date":      rebal_ts.strftime("%Y-%m-%d"),
            "portfolio": round(portfolio_value, 4),
            "benchmark": round(benchmark_value, 4),
        })

        if i % 10 == 0:
            pct = (portfolio_value / INITIAL_CAPITAL - 1) * 100
            bpct = (benchmark_value / INITIAL_CAPITAL - 1) * 100
            print(f"  {rebal_ts.date()}  Port={portfolio_value:.1f} ({pct:+.1f}%)  "
                  f"BM={benchmark_value:.1f} ({bpct:+.1f}%)  "
                  f"Holdings: {len(new_holdings)}")

        prev_date = rebal_date

    return equity_curve, annual_returns


# ─────────────────────────────────────────────────────────────────────────────
# STEP 6 — COMPUTE SUMMARY STATISTICS
# ─────────────────────────────────────────────────────────────────────────────

def compute_stats(equity_curve, annual_returns):
    if not equity_curve:
        return {}

    port_vals = [p["portfolio"] for p in equity_curve]
    bm_vals   = [p["benchmark"] for p in equity_curve]

    # Total return
    port_total = (port_vals[-1] / port_vals[0] - 1) * 100
    bm_total   = (bm_vals[-1]  / bm_vals[0]  - 1) * 100

    # CAGR
    n_years = len(equity_curve) / 52
    port_cagr = ((port_vals[-1] / port_vals[0]) ** (1 / n_years) - 1) * 100 if n_years > 0 else 0
    bm_cagr   = ((bm_vals[-1]  / bm_vals[0])  ** (1 / n_years) - 1) * 100 if n_years > 0 else 0

    # Max drawdown
    def max_drawdown(vals):
        peak = vals[0]
        max_dd = 0
        for v in vals:
            if v > peak:
                peak = v
            dd = (v - peak) / peak
            if dd < max_dd:
                max_dd = dd
        return max_dd * 100

    port_mdd = max_drawdown(port_vals)
    bm_mdd   = max_drawdown(bm_vals)

    # Weekly returns for Sharpe
    port_weekly = [port_vals[i] / port_vals[i-1] - 1 for i in range(1, len(port_vals))]
    bm_weekly   = [bm_vals[i]  / bm_vals[i-1]  - 1 for i in range(1, len(bm_vals))]

    def sharpe(weekly_rets, rf=0.0):
        if len(weekly_rets) < 2:
            return 0
        arr = np.array(weekly_rets)
        excess = arr - rf / 52
        if excess.std() == 0:
            return 0
        return float((excess.mean() / excess.std()) * math.sqrt(52))

    port_sharpe = sharpe(port_weekly)
    bm_sharpe   = sharpe(bm_weekly)

    # Win rate (weeks portfolio beat benchmark)
    beats = sum(1 for p, b in zip(port_weekly, bm_weekly) if p > b)
    win_rate = beats / len(port_weekly) * 100 if port_weekly else 0

    # Annual returns table
    annual_table = []
    for year in sorted(annual_returns.keys()):
        d = annual_returns[year]
        if "port_start" in d and "port_end" in d:
            port_ret = (d["port_end"] / d["port_start"] - 1) * 100
            bm_ret   = (d["bm_end"]   / d["bm_start"]   - 1) * 100
            annual_table.append({
                "year":      year,
                "portfolio": round(port_ret, 1),
                "benchmark": round(bm_ret, 1),
                "alpha":     round(port_ret - bm_ret, 1),
            })

    return {
        "port_total_return":  round(port_total, 1),
        "bm_total_return":    round(bm_total, 1),
        "port_cagr":          round(port_cagr, 1),
        "bm_cagr":            round(bm_cagr, 1),
        "port_max_drawdown":  round(port_mdd, 1),
        "bm_max_drawdown":    round(bm_mdd, 1),
        "port_sharpe":        round(port_sharpe, 2),
        "bm_sharpe":          round(bm_sharpe, 2),
        "win_rate_pct":       round(win_rate, 1),
        "n_years":            round(n_years, 1),
        "annual":             annual_table,
    }


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    now = datetime.datetime.now(datetime.timezone.utc)

    print("=" * 70)
    print("  Swedish RSL Momentum Strategy — 10-Year Backtest")
    print(f"  Period    : {START_DATE} → {END_DATE}")
    print(f"  Universe  : Nasdaq Stockholm (scraped live)")
    print(f"  Strategy  : Top {TOP_N} stocks by RSL, rebalanced weekly")
    print(f"  Benchmark : OMXSPI ({BENCHMARK_TICKER})")
    print(f"  Capital   : {INITIAL_CAPITAL} (index base = 100)")
    print("=" * 70)
    print()
    print("⚠  SURVIVORSHIP BIAS WARNING")
    print("   This backtest uses today's ticker list only.")
    print("   Stocks delisted or bankrupt during the period are excluded.")
    print("   Returns are likely OVERSTATED vs real-world performance.")
    print()

    # Get tickers
    tickers_list = get_tickers(verbose=False)
    print(f"Ticker universe: {len(tickers_list)} stocks")

    # Download prices (batch — fast)
    prices = download_all_prices(tickers_list)

    # Download benchmark
    benchmark = download_benchmark()

    # Fetch metadata (sector, mcap) — one call per ticker
    metadata = fetch_metadata(tickers_list)

    # Run backtest
    equity_curve, annual_returns = run_backtest(prices, benchmark, metadata)

    # Compute stats
    stats = compute_stats(equity_curve, annual_returns)

    print("\n" + "=" * 70)
    print("  BACKTEST RESULTS SUMMARY")
    print("=" * 70)
    print(f"  Period          : {stats.get('n_years', '?')} years")
    print(f"  Strategy return : {stats.get('port_total_return', '?')}%")
    print(f"  Benchmark return: {stats.get('bm_total_return', '?')}%")
    print(f"  Strategy CAGR   : {stats.get('port_cagr', '?')}% / year")
    print(f"  Benchmark CAGR  : {stats.get('bm_cagr', '?')}% / year")
    print(f"  Max Drawdown    : {stats.get('port_max_drawdown', '?')}%")
    print(f"  Sharpe Ratio    : {stats.get('port_sharpe', '?')}")
    print(f"  Weekly Win Rate : {stats.get('win_rate_pct', '?')}%")
    print()
    print("  Annual breakdown:")
    for row in stats.get("annual", []):
        sign  = "+" if row["alpha"] >= 0 else ""
        print(f"    {row['year']}  Strategy: {row['portfolio']:+.1f}%  "
              f"Benchmark: {row['benchmark']:+.1f}%  "
              f"Alpha: {sign}{row['alpha']:.1f}%")

    # Save output
    output = {
        "generated":        now.strftime("%Y-%m-%d %H:%M UTC"),
        "period_start":     START_DATE.strftime("%Y-%m-%d"),
        "period_end":       END_DATE.strftime("%Y-%m-%d"),
        "years_back":       YEARS_BACK,
        "rsl_period":       RSL_PERIOD,
        "portfolio_size":   TOP_N,
        "benchmark":        BENCHMARK_TICKER,
        "initial_capital":  INITIAL_CAPITAL,
        "survivorship_bias_warning": True,
        "stats":            stats,
        "equity_curve":     equity_curve,
    }

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n✅  Saved → {OUTPUT_JSON}")
    print(f"    Open backtest.html to view the results.")


if __name__ == "__main__":
    main()
