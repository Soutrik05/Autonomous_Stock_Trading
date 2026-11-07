"""
Backfills historical daily OHLCV candles from 2025-01-01 to 2025-09-11
so that all lookback periods (including 52-week high/low, EMA200, 252 bars)
are fully satisfied for any date in early 2026 (such as 2026-02-02).
"""

import logging
import sys
import time
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from core.config import settings
from core.database import get_connection
from ingestion.sync_ohlcv import _upsert_candles, get_active_tickers
from ingestion.upstox_client import UpstoxClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("backfill_history_2025")


def main() -> None:
    client = UpstoxClient()
    port_conn = get_connection(settings.PORTFOLIO_DB_PATH)
    ohlcv_conn = get_connection(settings.OHLCV_DB_PATH)

    tickers = get_active_tickers(port_conn)
    logger.info("Starting historical candle backfill (2025-01-01 to 2025-09-11) for %d tickers...", len(tickers))

    t0 = time.time()
    success_count = 0
    total_candles = 0

    for i, (ticker, key) in enumerate(tickers, start=1):
        try:
            candles = client.get_daily_candles(key, "2025-01-01", "2025-09-11")
            if candles:
                _upsert_candles(ohlcv_conn, ticker, candles)
                total_candles += len(candles)
                success_count += 1
            if i % 50 == 0 or i == len(tickers):
                ohlcv_conn.commit()
                elapsed = time.time() - t0
                logger.info(
                    "Progress: %d/%d tickers (%.1f%%) | Saved: %d candles | Elapsed: %.1fs",
                    i,
                    len(tickers),
                    (i / len(tickers)) * 100,
                    total_candles,
                    elapsed,
                )
        except Exception as exc:
            logger.warning("Failed to fetch %s (%s): %s", ticker, key, exc)

    ohlcv_conn.commit()
    port_conn.close()
    ohlcv_conn.close()
    logger.info(
        "Historical backfill complete! Updated %d tickers with %d daily candles in %.1fs",
        success_count,
        total_candles,
        time.time() - t0,
    )


if __name__ == "__main__":
    main()
