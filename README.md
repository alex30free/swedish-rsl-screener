# 🇸🇪 Swedish RSL Momentum Screener

Automated weekly screener for Swedish stocks (Large, Mid & Small Cap) ranked by **Levy Relative Strength (RSL)** — updated every Friday evening after Nasdaq Stockholm closes.

## Live Screener

Enable **GitHub Pages** (Settings → Pages → Branch: `main`, folder: `/root`) to view the live screener at:
```
https://<your-username>.github.io/<repo-name>/
```

## How It Works

| Step | What happens |
|------|-------------|
| 1 | GitHub Actions triggers every **Friday at 17:30 UTC** (≈ 19:30 CEST / 18:30 CET) |
| 2 | `screener.py` downloads 9 months of daily close prices for ~370 Swedish stocks via Yahoo Finance |
| 3 | Computes RSL = Current Price ÷ 130-day SMA for each stock |
| 4 | Ranks all stocks descending by RSL, saves top 20 to `screener_data.json` |
| 5 | Saves previous ranks to `prev_ranks.json` for the "Last Week Rank" column |
| 6 | Commits & pushes the JSON — GitHub Pages serves the updated `index.html` automatically |

## RSL Formula

```
RSL = Current Price / Simple Moving Average (130 trading days)
```

- RSL > 1.0 → stock trades above its 6-month average (bullish momentum)
- Higher RSL = stronger relative momentum vs. own history

## Setup

1. **Fork / clone** this repository
2. Go to **Settings → Pages** → Source: Deploy from branch `main`, folder `/` (root)
3. The workflow runs automatically every Friday — or trigger it manually via **Actions → Run workflow**

## Files

```
├── index.html          # Screener webpage (reads screener_data.json)
├── screener.py         # Python script — fetches data, computes RSL, outputs JSON
├── screener_data.json  # Auto-generated: top 20 RSL data (committed by Actions)
├── prev_ranks.json     # Auto-generated: last week's ranks for comparison
└── .github/
    └── workflows/
        └── update_screener.yml   # GitHub Actions — weekly automation
```

## Dependencies

```
yfinance
pandas
```

Installed automatically by the GitHub Actions workflow. To run locally:
```bash
pip install yfinance pandas
python screener.py
```

## Disclaimer

For informational purposes only. Not financial advice. Always conduct your own research before making investment decisions.

---

*Based on: R.A. Levy, "Relative Strength as a Criterion for Investment Selection", Journal of Finance, 1967.*
