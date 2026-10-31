"""
Syncs daily OHLCV candles into ohlcv.db, with the corporate-action overlap-comparison guard.
See Plan_v3 §1.5.
"""
import sqlite3
from datetime import date, timedelta
from typing import List, Optional, Tuple

from core.clock import Clock
from core.database import get_connection
from ingestion.upstox_client import UpstoxAPIError
from settings import settings

# Prices are REAL rupees here (this is a raw market-data cache, not the paise money ledger).
OHLCV_SCHEMA = """
CREATE TABLE IF NOT EXISTS ohlcv (
    ticker      TEXT NOT NULL,
    trade_date  TEXT NOT NULL,
    open        REAL NOT NULL,
    high        REAL NOT NULL,
    low         REAL NOT NULL,
    close       REAL NOT NULL,
    volume      INTEGER NOT NULL,
    PRIMARY KEY (ticker, trade_date)
);

CREATE TABLE IF NOT EXISTS ticker_status (
    ticker      TEXT PRIMARY KEY,
    status      TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
"""


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(OHLCV_SCHEMA)


def _col(row, key, idx):
    return row[key] if isinstance(row, sqlite3.Row) else row[idx]


def get_active_tickers(portfolio_conn: sqlite3.Connection, limit: int = None) -> List[Tuple[str, str]]:
    query = "SELECT ticker, instrument_key FROM symbols WHERE is_active = 1 ORDER BY ticker"
    if limit is not None:
        query += " LIMIT ?"
        rows = portfolio_conn.execute(query, (int(limit),)).fetchall()
    else:
        rows = portfolio_conn.execute(query).fetchall()
    return [(_col(r, "ticker", 0), _col(r, "instrument_key", 1)) for r in rows]


def get_last_stored_date(ohlcv_conn: sqlite3.Connection, ticker: str) -> Optional[date]:
    row = ohlcv_conn.execute("SELECT MAX(trade_date) AS d FROM ohlcv WHERE ticker = ?", (ticker,)).fetchone()
    value = _col(row, "d", 0) if row else None
    return date.fromisoformat(value) if value else None


def set_ticker_status(ohlcv_conn: sqlite3.Connection, ticker: str, status: str, clock: Clock) -> None:
    ohlcv_conn.execute(
        """
        INSERT INTO ticker_status (ticker, status, updated_at) VALUES (?, ?, ?)
        ON CONFLICT(ticker) DO UPDATE SET status = excluded.status, updated_at = excluded.updated_at
        """,
        (ticker, status, clock.now_iso()),
    )


def _upsert_candles(ohlcv_conn: sqlite3.Connection, ticker: str, candles: list) -> None:
    for row in candles:
        timestamp, open_, high, low, close, volume, _oi = row
        trade_date = timestamp[:10]
        ohlcv_conn.execute(
            """
            INSERT INTO ohlcv (ticker, trade_date, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ticker, trade_date) DO UPDATE SET
                open = excluded.open, high = excluded.high, low = excluded.low,
                close = excluded.close, volume = excluded.volume
            """,
            (ticker, trade_date, open_, high, low, close, volume),
        )


def _freeze_open_position(portfolio_conn: sqlite3.Connection, ticker: str, clock: Clock) -> None:
    rows = portfolio_conn.execute(
        "SELECT id, agent_id FROM positions WHERE ticker = ? AND status = 'OPEN'", (ticker,)
    ).fetchall()
    for row in rows:
        position_id, agent_id = _col(row, "id", 0), _col(row, "agent_id", 1)
        portfolio_conn.execute(
            "UPDATE positions SET frozen_reason = 'CORP_ACTION' WHERE id = ?", (position_id,)
        )
        portfolio_conn.execute(
            """
            INSERT INTO activity_log (agent_id, event_type, ticker, description, metadata_json, created_at)
            VALUES (?, 'CORP_ACTION_FROZEN', ?, ?, NULL, ?)
            """,
            (agent_id, ticker, f"Corporate action detected for {ticker}; position frozen.", clock.now_iso()),
        )


def _detect_corporate_action(ohlcv_conn: sqlite3.Connection, ticker: str, candles: list) -> bool:
    """Compares each freshly fetched candle's close against the cached close for the same date
    (if any). Returns True if any overlapping close differs by more than CORP_ACTION_DIFF_PCT%."""
    for row in candles:
        timestamp, _o, _h, _l, close, _v, _oi = row
        trade_date = timestamp[:10]
        cached = ohlcv_conn.execute(
            "SELECT close FROM ohlcv WHERE ticker = ? AND trade_date = ?", (ticker, trade_date)
        ).fetchone()
        if cached is None:
            continue
        cached_close = _col(cached, "close", 0)
        if not close or not cached_close:
            continue
        diff_pct = abs(cached_close - close) / abs(close) * 100
        if diff_pct > settings.CORP_ACTION_DIFF_PCT:
            return True
    return False


def _merge_today_candle_if_missing(client, instrument_key: str, candles: list, today_iso: str) -> None:
    """If today's daily candle is absent from historical storage (e.g. before midnight clearing),
    fetch the current-day candle from the V3 intraday days/1 endpoint and append it."""
    if hasattr(client, "get_intraday_daily_candle"):
        if not any(row[0][:10] == today_iso for row in candles):
            try:
                intra_candles = client.get_intraday_daily_candle(instrument_key)
                for ic in intra_candles:
                    if ic[0][:10] == today_iso:
                        candles.append(ic)
            except UpstoxAPIError:
                pass


def sync_ticker(
    client, ohlcv_conn: sqlite3.Connection, portfolio_conn: sqlite3.Connection, ticker: str,
    instrument_key: str, clock: Clock,
) -> str:
    """Syncs one ticker end to end. Returns the final ticker_status: OK, STALE_DATA or LOCKED_CIRCUIT."""
    today = clock.today()
    last_date = get_last_stored_date(ohlcv_conn, ticker)
    if last_date is None:
        from_date = today - timedelta(days=settings.OHLCV_BACKFILL_DAYS)
    else:
        from_date = last_date - timedelta(days=settings.CORP_ACTION_LOOKBACK_CANDLES)

    try:
        candles = client.get_daily_candles(instrument_key, from_date.isoformat(), today.isoformat())
    except UpstoxAPIError:
        set_ticker_status(ohlcv_conn, ticker, "STALE_DATA", clock)
        return "STALE_DATA"

    _merge_today_candle_if_missing(client, instrument_key, candles, today.isoformat())

    if not candles:
        set_ticker_status(ohlcv_conn, ticker, "STALE_DATA", clock)
        return "STALE_DATA"

    if _detect_corporate_action(ohlcv_conn, ticker, candles):
        ohlcv_conn.execute("DELETE FROM ohlcv WHERE ticker = ?", (ticker,))
        _freeze_open_position(portfolio_conn, ticker, clock)
        reload_from = today - timedelta(days=settings.OHLCV_BACKFILL_DAYS)
        try:
            candles = client.get_daily_candles(instrument_key, reload_from.isoformat(), today.isoformat())
        except UpstoxAPIError:
            set_ticker_status(ohlcv_conn, ticker, "STALE_DATA", clock)
            return "STALE_DATA"
        _merge_today_candle_if_missing(client, instrument_key, candles, today.isoformat())
        if not candles:
            set_ticker_status(ohlcv_conn, ticker, "STALE_DATA", clock)
            return "STALE_DATA"

    _upsert_candles(ohlcv_conn, ticker, candles)

    latest = max(candles, key=lambda row: row[0])
    latest_volume = latest[5]
    status = "LOCKED_CIRCUIT" if latest_volume == 0 else "OK"
    set_ticker_status(ohlcv_conn, ticker, status, clock)
    return status


def sync_ohlcv(client, clock: Clock, ohlcv_conn: sqlite3.Connection = None,
               portfolio_conn: sqlite3.Connection = None, limit: int = None) -> dict:
    """Syncs every active ticker in the symbols table (or the first `limit`). Returns
    {"OK": [...], "STALE_DATA": [...], "LOCKED_CIRCUIT": [...]} of ticker lists."""
    owns_ohlcv = ohlcv_conn is None
    owns_portfolio = portfolio_conn is None
    if ohlcv_conn is None:
        ohlcv_conn = get_connection(settings.OHLCV_DB_PATH)
        ensure_schema(ohlcv_conn)
    if portfolio_conn is None:
        portfolio_conn = get_connection(settings.PORTFOLIO_DB_PATH)
    try:
        summary = {"OK": [], "STALE_DATA": [], "LOCKED_CIRCUIT": []}
        for ticker, instrument_key in get_active_tickers(portfolio_conn, limit=limit):
            status = sync_ticker(client, ohlcv_conn, portfolio_conn, ticker, instrument_key, clock)
            summary[status].append(ticker)
        return summary
    finally:
        if owns_ohlcv:
            ohlcv_conn.close()
        if owns_portfolio:
            portfolio_conn.close()
