"""
Builds the symbols table: ticker, instrument key, ISIN, company name, sector from the Nifty 500 constituents file.
See Plan_v3 §1.2.
"""
import csv
import gzip
import io
import sys
from pathlib import Path
from typing import Dict, List, Tuple

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

import requests

from settings import settings
from core.database import get_connection

NIFTY500_CSV = Path(__file__).resolve().parent.parent / "storage" / "market" / "nifty500_constituents.csv"
UPSTOX_INSTRUMENTS_URL = "https://assets.upstox.com/market-quote/instruments/exchange/NSE.csv.gz"


def load_nifty500(csv_path: Path = NIFTY500_CSV) -> List[Dict[str, str]]:
    """Reads data/nifty500_constituents.csv (Company Name, Industry, Symbol, Series, ISIN Code)."""
    with csv_path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def fetch_upstox_nse_equities(url: str = UPSTOX_INSTRUMENTS_URL) -> Dict[str, dict]:
    """Downloads Upstox's public NSE instrument master (no authentication required) and returns
    EQUITY rows keyed by instrument_key."""
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    text = gzip.decompress(resp.content).decode("utf-8")
    reader = csv.DictReader(io.StringIO(text))
    return {
        row["instrument_key"]: row
        for row in reader
        if row["instrument_type"] == "EQUITY" and row["exchange"] == "NSE_EQ"
    }


def match_symbols(
    nifty_rows: List[Dict[str, str]], upstox_equities: Dict[str, dict]
) -> Tuple[List[dict], List[str]]:
    """Matches each Nifty 500 row to an Upstox instrument_key, primarily by ISIN
    (instrument_key == 'NSE_EQ|<isin>'), falling back to an exact tradingsymbol match.
    Returns (matched_rows, unmatched_tickers)."""
    by_symbol = {row["tradingsymbol"]: row for row in upstox_equities.values()}
    matched = []
    unmatched = []
    for row in nifty_rows:
        ticker = row["Symbol"]
        isin = row["ISIN Code"]
        candidate_key = f"NSE_EQ|{isin}"
        if candidate_key in upstox_equities:
            matched.append(
                {
                    "ticker": ticker,
                    "instrument_key": candidate_key,
                    "isin": isin,
                    "company_name": row["Company Name"],
                    "sector": row["Industry"],
                }
            )
            continue
        fallback = by_symbol.get(ticker)
        if fallback is not None:
            matched.append(
                {
                    "ticker": ticker,
                    "instrument_key": fallback["instrument_key"],
                    "isin": isin,
                    "company_name": row["Company Name"],
                    "sector": row["Industry"],
                }
            )
            continue
        unmatched.append(ticker)
    return matched, unmatched


def write_symbols(matched: List[dict], db_path: str = None) -> None:
    """Writes matched rows into the symbols table (upsert, keyed by ticker)."""
    conn = get_connection(db_path or settings.PORTFOLIO_DB_PATH)
    try:
        for row in matched:
            conn.execute(
                """
                INSERT INTO symbols (ticker, instrument_key, isin, company_name, sector, sector_index, is_active)
                VALUES (?, ?, ?, ?, ?, NULL, 1)
                ON CONFLICT(ticker) DO UPDATE SET
                    instrument_key = excluded.instrument_key,
                    isin = excluded.isin,
                    company_name = excluded.company_name,
                    sector = excluded.sector,
                    is_active = 1
                """,
                (row["ticker"], row["instrument_key"], row["isin"], row["company_name"], row["sector"]),
            )
    finally:
        conn.close()


def main() -> None:
    nifty_rows = load_nifty500()
    upstox_equities = fetch_upstox_nse_equities()
    matched, unmatched = match_symbols(nifty_rows, upstox_equities)
    write_symbols(matched)
    print(f"Matched {len(matched)} of {len(nifty_rows)} Nifty 500 tickers to an Upstox instrument_key.")
    if unmatched:
        print(f"Unmatched ({len(unmatched)}):")
        for ticker in unmatched:
            print(f"  {ticker}")


if __name__ == "__main__":
    main()
