"""
Synchronizes historical intraday candle data (30-minute or 1-minute) from Upstox
into storage/market/intraday.db.

Automatically splits multi-month date ranges into valid API chunks (e.g. 75-day chunks
for 30m candles, 25-day chunks for 1m candles) and performs rate-limited, idempotent ingestion.
"""

import argparse
import logging
import sqlite3
import sys
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent.parent
_SRC = _ROOT / "src"
for p in (_SRC, _ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from core.config import settings
from core.database import get_connection
from ingestion.upstox_client import UpstoxClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ingestion.sync_intraday")


def init_intraday_db(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection(db_path)
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ohlcv_intraday (
            ticker TEXT NOT NULL,
            trade_date TEXT NOT NULL,
            candle_time TEXT NOT NULL,
            open REAL NOT NULL,
            high REAL NOT NULL,
            low REAL NOT NULL,
            close REAL NOT NULL,
            volume REAL NOT NULL,
            open_interest REAL DEFAULT 0,
            PRIMARY KEY (ticker, candle_time)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_intraday_date ON ohlcv_intraday(trade_date)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_intraday_date_time ON ohlcv_intraday(trade_date, candle_time ASC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_intraday_ticker_date ON ohlcv_intraday(ticker, trade_date)")
    conn.commit()
    return conn


def split_date_range(start_date: date, end_date: date, chunk_days: int) -> list[tuple[date, date]]:
    """Splits a date range into chronological chunks of at most chunk_days."""
    chunks = []
    cur_start = start_date
    while cur_start <= end_date:
        cur_end = min(cur_start + timedelta(days=chunk_days - 1), end_date)
        chunks.append((cur_start, cur_end))
        cur_start = cur_end + timedelta(days=1)
    return chunks


def fetch_and_store_ticker(
    client: UpstoxClient,
    conn: sqlite3.Connection,
    ticker: str,
    instrument_key: str,
    from_date_obj: date,
    to_date_obj: date,
    interval_minutes: int = 30,
) -> int:
    """Fetches intraday candles across all chunks and inserts into ohlcv_intraday."""
    chunk_size = 75 if interval_minutes >= 30 else 25
    chunks = split_date_range(from_date_obj, to_date_obj, chunk_days=chunk_size)

    total_inserted = 0
    for chunk_start, chunk_end in chunks:
        try:
            candles = client.get_intraday_candles(
                instrument_key=instrument_key,
                interval_minutes=interval_minutes,
                from_date=chunk_start.isoformat(),
                to_date=chunk_end.isoformat(),
            )
        except Exception as exc:
            logger.warning("Failed fetching %s (%s to %s): %s", ticker, chunk_start, chunk_end, exc)
            continue

        if not candles:
            continue

        rows_to_insert = []
        for c in candles:
            # c: [timestamp_iso, open, high, low, close, volume, open_interest]
            ts_iso = c[0]
            trade_date = ts_iso[:10]
            rows_to_insert.append(
                (
                    ticker,
                    trade_date,
                    ts_iso,
                    float(c[1]),
                    float(c[2]),
                    float(c[3]),
                    float(c[4]),
                    float(c[5]) if len(c) > 5 else 0.0,
                    float(c[6]) if len(c) > 6 else 0.0,
                )
            )

        conn.executemany(
            """
            INSERT OR REPLACE INTO ohlcv_intraday
                (ticker, trade_date, candle_time, open, high, low, close, volume, open_interest)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows_to_insert,
        )
        conn.commit()
        total_inserted += len(rows_to_insert)

    return total_inserted


def sync_intraday_universe(
    from_date: str = "2025-02-01",
    to_date: str = "2026-11-05",
    interval_minutes: int = 30,
    tickers: list[str] | None = None,
    limit: int | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    intraday_db = db_path or Path(settings.INTRADAY_DB_PATH)
    conn = init_intraday_db(intraday_db)

    port_conn = get_connection(settings.PORTFOLIO_DB_PATH)
    sym_rows = port_conn.execute("SELECT ticker, instrument_key FROM symbols").fetchall()
    sym_map = {r["ticker"]: r["instrument_key"] for r in sym_rows if r["instrument_key"]}

    target_tickers = tickers or sorted(list(sym_map.keys()))
    if limit:
        target_tickers = target_tickers[:limit]

    client = UpstoxClient()
    from_obj = date.fromisoformat(from_date)
    to_obj = date.fromisoformat(to_date)

    logger.info(
        "Starting intraday ingestion (%dm): %d tickers, %s to %s into %s",
        interval_minutes,
        len(target_tickers),
        from_date,
        to_date,
        intraday_db,
    )

    t0 = time.time()
    total_candles = 0
    successful_tickers = 0

    for idx, ticker in enumerate(target_tickers, start=1):
        ikey = sym_map.get(ticker)
        if not ikey:
            logger.warning("No instrument key found for %s; skipping", ticker)
            continue

        # Resume guard: skip if ticker is already comprehensively ingested for this date range
        existing = conn.execute(
            "SELECT COUNT(*), MIN(trade_date), MAX(trade_date) FROM ohlcv_intraday WHERE ticker = ?",
            (ticker,),
        ).fetchone()
        if existing and existing[0] > 4000 and existing[1] <= from_date and existing[2] >= "2026-10-30":
            logger.info(
                "[%3d/%3d] %-12s -> Already ingested (%d candles). Skipping.",
                idx,
                len(target_tickers),
                ticker,
                existing[0],
            )
            total_candles += existing[0]
            successful_tickers += 1
            continue

        c_count = fetch_and_store_ticker(
            client=client,
            conn=conn,
            ticker=ticker,
            instrument_key=ikey,
            from_date_obj=from_obj,
            to_date_obj=to_obj,
            interval_minutes=interval_minutes,
        )
        total_candles += c_count
        successful_tickers += 1
        logger.info(
            "[%3d/%3d] %-12s -> %5d candles ingested (total: %d)",
            idx,
            len(target_tickers),
            ticker,
            c_count,
            total_candles,
        )

    elapsed = time.time() - t0
    logger.info(
        "Intraday ingestion completed in %.1fs: %d tickers, %d total candles.",
        elapsed,
        successful_tickers,
        total_candles,
    )

    return {
        "status": "SUCCESS",
        "tickers_count": successful_tickers,
        "total_candles": total_candles,
        "elapsed_sec": round(elapsed, 1),
    }


def main():
    parser = argparse.ArgumentParser(description="Upstox Intraday Historical Sync")
    parser.add_argument("--from-date", type=str, default="2025-02-01", help="Start date YYYY-MM-DD")
    parser.add_argument("--to-date", type=str, default="2026-11-05", help="End date YYYY-MM-DD")
    parser.add_argument("--interval", type=int, default=30, choices=[1, 30], help="Candle interval (minutes)")
    parser.add_argument("--tickers", nargs="+", default=None, help="Specific tickers to ingest")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of tickers")
    parser.add_argument("--db-path", type=str, default=None, help="Custom intraday database path")
    args = parser.parse_args()

    db_p = Path(args.db_path) if args.db_path else None
    sync_intraday_universe(
        from_date=args.from_date,
        to_date=args.to_date,
        interval_minutes=args.interval,
        tickers=args.tickers,
        limit=args.limit,
        db_path=db_p,
    )


if __name__ == "__main__":
    main()
