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
    # Ask for UTF-8 explicitly
    "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
    "Accept-Charset": "utf-8",
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
    parts = sa_ticker.split(".")
    if len(parts) == 1:
        return f"{sa_ticker}.ST"
    return "-".join(parts) + ".ST"


def _fix_encoding(text: str) -> str:
    """
    Fix double-encoded UTF-8 strings that arrive as latin-1 interpreted bytes.
    e.g. 'OrrÃ¶n' → 'Orron'  (we just re-encode/decode to fix it)
    """
    try:
        return text.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text  # already correct, return as-is


def _scrape_page(url: str, session: requests.Session) -> list[tuple[str, str]]:
    """Scrape one page and return list of (company_name, yf_ticker) tuples."""
    resp = session.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()

    # Force correct encoding — stockanalysis.com is UTF-8
    resp.encoding = "utf-8"

    soup = BeautifulSoup(resp.text, "html.parser")
    results = []

    for row in soup.select("tbody tr"):
        cells = row.find_all("td")
        if len(cells) < 3:
            continue

        link = cells[1].find("a")
        if not link:
            continue
        href = link.get("href", "")
        m = re.search(r"/quote/sto/([^/]+)/", href)
        if not m:
            continue

        sa_ticker    = m.group(1)
        raw_name     = cells[2].get_text(strip=True) if len(cells) > 2 else sa_ticker
        company_name = _fix_encoding(raw_name)
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
    Returns list of (company_name, yahoo_ticker) tuples.
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
            break

        all_rows.extend(rows)

        if verbose:
            print(f"  Page {page}: {len(rows)} tickers found (total so far: {len(all_rows)})")

        page += 1
        time.sleep(0.8)

    if verbose:
        print(f"\n  Raw tickers scraped: {len(all_rows)}")

    if dedupe_companies:
        all_rows = _deduplicate(all_rows)
        if verbose:
            print(f"  After deduplication (one per company): {len(all_rows)}")

    return all_rows


def _deduplicate(rows: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Keep only the most liquid share class per company."""
    from collections import defaultdict
    by_company: dict[str, list[tuple[str, str]]] = defaultdict(list)

    for name, ticker in rows:
        base_name = re.sub(r"\s*\(publ[.\)]*", "", name, flags=re.IGNORECASE).strip()
        by_company[base_name].append((name, ticker))

    PRIORITY = ["B.ST", "A.ST", "D.ST", "SDB.ST", "SEK.ST", "R.ST", "C.ST"]

    result = []
    for base_name, variants in by_company.items():
        if len(variants) == 1:
            result.append(variants[0])
            continue

        chosen = None
        for suffix in PRIORITY:
            for name, ticker in variants:
                if ticker.endswith(suffix):
                    chosen = (name, ticker)
                    break
            if chosen:
                break

        if not chosen:
            chosen = variants[0]

        result.append(chosen)

    return result


if __name__ == "__main__":
    import sys
    verbose    = "--verbose" in sys.argv or "-v" in sys.argv
    all_shares = "--all" in sys.argv

    print("Fetching Nasdaq Stockholm ticker list from stockanalysis.com…\n")
    tickers = get_tickers(verbose=True, dedupe_companies=not all_shares)

    print(f"\n{'─'*55}")
    print(f"  Total tickers: {len(tickers)}")
    print(f"{'─'*55}")

    if verbose or "--list" in sys.argv:
        for i, (name, ticker) in enumerate(tickers, 1):
            print(f"  {i:>3}. {ticker:<20} {name}")
