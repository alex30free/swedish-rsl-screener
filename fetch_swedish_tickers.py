"""
fetch_swedish_tickers.py
========================
Fetches the complete live list of Nasdaq Stockholm stocks from stockanalysis.com
and converts them to Yahoo Finance ticker format (e.g. VOLV-B.ST).

Usage — drop-in replacement for the static TICKERS list in any screener:

    from fetch_swedish_tickers import get_tickers
    TICKERS = get_tickers()          # list of (name, "XXXX.ST") tuples

Or call directly to see the full list:
    python fetch_swedish_tickers.py
"""

import time
import re
import warnings
warnings.filterwarnings("ignore")

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("ERROR: Run: pip install requests beautifulsoup4")
    raise


BASE_URL  = "https://stockanalysis.com/list/nasdaq-stockholm/"
HEADERS   = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def _sa_ticker_to_yf(sa_ticker: str) -> str:
    """
    Convert a stockanalysis.com ticker to a Yahoo Finance .ST ticker.

    stockanalysis uses dots as separator:  VOLV.B  → Yahoo uses hyphens: VOLV-B.ST
    Special cases observed:
      NDA.SE   → NDA-SE.ST   (not NDA.SE.ST)
      ALIV.SDB → ALIV-SDB.ST
      Tickers without a dot → just append .ST
    """
    # Multi-character suffixes like .SE, .SDB, .SEK already contain the exchange
    # info that must be kept.  We replace the last dot with a hyphen and add .ST.
    parts = sa_ticker.split(".")
    if len(parts) == 1:
        return f"{sa_ticker}.ST"
    # Rejoin with hyphen between all parts, then add .ST
    # e.g. ALIV.SDB → ALIV-SDB.ST | VOLV.B → VOLV-B.ST | NDA.SE → NDA-SE.ST
    return "-".join(parts) + ".ST"


def _scrape_page(url: str, session: requests.Session) -> list[tuple[str, str]]:
    """Scrape one page and return list of (company_name, yf_ticker) tuples."""
    resp = session.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    results = []

    # The table rows: each has a link /quote/sto/TICKER/ and a company name
    for row in soup.select("tbody tr"):
        cells = row.find_all("td")
        if len(cells) < 3:
            continue

        # Cell 1 (index 1) contains the ticker link
        link = cells[1].find("a")
        if not link:
            continue
        href = link.get("href", "")
        # href looks like /quote/sto/VOLV.B/
        m = re.search(r"/quote/sto/([^/]+)/", href)
        if not m:
            continue

        sa_ticker    = m.group(1)             # e.g. VOLV.B
        company_name = cells[2].get_text(strip=True) if len(cells) > 2 else sa_ticker
        yf_ticker    = _sa_ticker_to_yf(sa_ticker)

        results.append((company_name, yf_ticker))

    return results


def get_tickers(
    max_pages: int = 5,
    verbose: bool = False,
    dedupe_companies: bool = True,
) -> list[tuple[str, str]]:
    """
    Fetch all Nasdaq Stockholm stocks from stockanalysis.com.

    Parameters
    ----------
    max_pages : int
        Safety cap on number of pages to scrape (site currently has 2 pages of
        ~500 stocks each, so 5 is more than enough).
    verbose : bool
        Print progress.
    dedupe_companies : bool
        If True (default), keep only one share class per company.
        Prefers B shares over A shares (more liquid), keeps first occurrence
        otherwise.  Set to False to include all share classes (A, B, D, SDB…).

    Returns
    -------
    list of (company_name, yahoo_ticker) tuples — ready to use in screener.py
    """
    session  = requests.Session()
    all_rows: list[tuple[str, str]] = []
    page     = 1

    while page <= max_pages:
        url = BASE_URL if page == 1 else f"{BASE_URL}?p={page}"
        if verbose:
            print(f"  Fetching page {page}: {url}")

        try:
            rows = _scrape_page(url, session)
        except Exception as e:
            if verbose:
                print(f"  Page {page} failed: {e}")
            break

        if not rows:
            break  # No more data

        all_rows.extend(rows)

        if verbose:
            print(f"  Page {page}: {len(rows)} tickers found (total so far: {len(all_rows)})")

        page += 1
        time.sleep(0.8)   # polite delay between pages

    if verbose:
        print(f"\n  Raw tickers scraped: {len(all_rows)}")

    if dedupe_companies:
        all_rows = _deduplicate(all_rows)
        if verbose:
            print(f"  After deduplication (one per company): {len(all_rows)}")

    return all_rows


def _deduplicate(rows: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """
    Keep only the most liquid share class per company.
    Priority order: B > A > D > SDB > first seen.
    """
    # Group by company name
    from collections import defaultdict
    by_company: dict[str, list[tuple[str, str]]] = defaultdict(list)

    for name, ticker in rows:
        # Normalise name slightly: strip share-class suffixes like " (publ)"
        base_name = re.sub(r"\s*\(publ[.\)]*", "", name, flags=re.IGNORECASE).strip()
        by_company[base_name].append((name, ticker))

    PRIORITY = ["B.ST", "A.ST", "D.ST", "SDB.ST", "SEK.ST", "R.ST", "C.ST"]

    result = []
    for base_name, variants in by_company.items():
        if len(variants) == 1:
            result.append(variants[0])
            continue

        # Try to find preferred share class
        chosen = None
        for suffix in PRIORITY:
            for name, ticker in variants:
                if ticker.endswith(suffix):
                    chosen = (name, ticker)
                    break
            if chosen:
                break

        if not chosen:
            chosen = variants[0]   # fall back to first

        result.append(chosen)

    return result


# ── CLI usage ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    verbose    = "--verbose" in sys.argv or "-v" in sys.argv
    all_shares = "--all"     in sys.argv          # include all share classes

    print("Fetching Nasdaq Stockholm ticker list from stockanalysis.com…\n")
    tickers = get_tickers(
        verbose=True,
        dedupe_companies=not all_shares,
    )

    print(f"\n{'─'*55}")
    print(f"  Total tickers: {len(tickers)}")
    print(f"{'─'*55}")

    if verbose or "--list" in sys.argv:
        for i, (name, ticker) in enumerate(tickers, 1):
            print(f"  {i:>3}. {ticker:<20} {name}")
