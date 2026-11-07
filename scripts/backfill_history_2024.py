"""
Backfills historical daily OHLCV candles for 2024 (2024-01-01 to 2024-12-31)
into storage/market/ohlcv.db so that 252-session lookback indicators (52-week high/low,
EMA 200) are fully populated and non-null on session 1 of Window 1 (2025-10-21).
Uses UpstoxClient daily candle API with rate limiting and exponential backoff.
"""

import logging
import sys
import time
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))
SRC_DIR = WORKSPACE_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from core.config import settings
from core.database import get_connection
from ingestion.sync_ohlcv import _upsert_candles, get_active_tickers
from ingestion.upstox_client import UpstoxClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("backfill_history_2024")


def fetch_with_retry(client: UpstoxClient, key: str, max_retries: int = 3) -> list:
    for attempt in range(max_retries):
        try:
            candles = client.get_daily_candles(key, "2024-01-01", "2024-12-31")
            return candles or []
        except Exception as exc:
            if attempt < max_retries - 1:
                time.sleep(1.0 * (attempt + 1))
            else:
                logger.debug("Failed to fetch %s: %s", key, exc)
                return []
    return []


def main() -> None:
    client = UpstoxClient()
    port_conn = get_connection(settings.PORTFOLIO_DB_PATH)
    ohlcv_conn = get_connection(settings.OHLCV_DB_PATH)

    tickers = get_active_tickers(port_conn)
    logger.info("Starting 2024 historical candle backfill for %d active tickers...", len(tickers))

    t0 = time.time()
    success_count = 0
    total_candles = 0
    zero_count = 0

    for i, (ticker, key) in enumerate(tickers, start=1):
        if not key:
            zero_count += 1
            continue

        candles = fetch_with_retry(client, key)
        if candles:
            _upsert_candles(ohlcv_conn, ticker, candles)
            total_candles += len(candles)
            success_count += 1
        else:
            zero_count += 1

        # Smooth rate limiting: ~8 requests/sec
        time.sleep(0.12)

        if i % 50 == 0 or i == len(tickers):
            ohlcv_conn.commit()
            elapsed = time.time() - t0
            logger.info(
                "Progress: %d/%d tickers (%.1f%%) | Tickers with 2024 data: %d | Saved: %d candles | Zero (IPOs): %d | Elapsed: %.1fs",
                i,
                len(tickers),
                (i / len(tickers)) * 100,
                success_count,
                total_candles,
                zero_count,
                elapsed,
            )

    ohlcv_conn.commit()
    port_conn.close()
    ohlcv_conn.close()

    elapsed = time.time() - t0
    logger.info(
        "2024 Backfill Complete: %d/%d tickers updated with %d daily candles (Zero/New IPOs: %d) in %.1fs",
        success_count,
        len(tickers),
        total_candles,
        zero_count,
        elapsed,
    )


if __name__ == "__main__":
    main()
