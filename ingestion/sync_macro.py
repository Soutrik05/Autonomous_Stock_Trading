"""
Syncs India VIX, computes the rule-based daily regime from VIX_BANDS, and writes one
macro_daily row to macro.db. FII/DII columns stay NULL for now (see docs/upstox_findings.md:
Upstox's FII/DII activity data is market-wide, not per-stock, and only available from
1 Apr 2026 onward — wiring it in is out of scope for this task). nifty50_trend, nifty500_trend
and advance_decline are also left NULL: computing them needs index-level OHLCV this task does
not fetch.
See Plan_v3 §2.5.
"""
import sqlite3
from datetime import date

from core.calendar import is_trading_day
from core.clock import Clock
from core.database import get_connection
from settings import settings

MACRO_SCHEMA = """
CREATE TABLE IF NOT EXISTS macro_daily (
    trade_date       TEXT PRIMARY KEY,
    regime           TEXT NOT NULL,
    india_vix        REAL,
    fii_net_cr       REAL,
    dii_net_cr       REAL,
    nifty50_trend    TEXT,
    nifty500_trend   TEXT,
    advance_decline  REAL,
    market_closed    INTEGER NOT NULL
);
"""


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(MACRO_SCHEMA)


def compute_regime(india_vix: float) -> str:
    """LOW_VOL < bands['LOW_VOL'] <= NORMAL < bands['NORMAL'] <= ELEVATED < bands['ELEVATED'] <= PANIC."""
    bands = settings.VIX_BANDS
    if india_vix < bands["LOW_VOL"]:
        return "LOW_VOL"
    if india_vix < bands["NORMAL"]:
        return "NORMAL"
    if india_vix < bands["ELEVATED"]:
        return "ELEVATED"
    return "PANIC"


def sync_macro(client, clock: Clock, macro_conn: sqlite3.Connection = None,
               portfolio_conn: sqlite3.Connection = None, as_of_date: str = None) -> dict:
    """Fetches India VIX and writes one macro_daily row for as_of_date (default: clock.today()). Returns the row
    written, as a dict."""
    owns_macro = macro_conn is None
    owns_portfolio = portfolio_conn is None
    if macro_conn is None:
        macro_conn = get_connection(settings.MACRO_DB_PATH)
        ensure_schema(macro_conn)
    if portfolio_conn is None:
        portfolio_conn = get_connection(settings.PORTFOLIO_DB_PATH)
    try:
        target_date: date = date.fromisoformat(as_of_date) if as_of_date else clock.today()
        market_closed = 0 if is_trading_day(portfolio_conn, target_date) else 1

        vix_quote = client.get_india_vix()
        india_vix = vix_quote.get("last_price") if vix_quote else None
        regime = compute_regime(india_vix) if india_vix is not None else "UNKNOWN"

        row = {
            "trade_date": target_date.isoformat(),
            "regime": regime,
            "india_vix": india_vix,
            "fii_net_cr": None,
            "dii_net_cr": None,
            "nifty50_trend": None,
            "nifty500_trend": None,
            "advance_decline": None,
            "market_closed": market_closed,
        }
        macro_conn.execute(
            """
            INSERT INTO macro_daily
                (trade_date, regime, india_vix, fii_net_cr, dii_net_cr, nifty50_trend,
                 nifty500_trend, advance_decline, market_closed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(trade_date) DO UPDATE SET
                regime = excluded.regime,
                india_vix = excluded.india_vix,
                market_closed = excluded.market_closed
            """,
            (
                row["trade_date"], row["regime"], row["india_vix"], row["fii_net_cr"],
                row["dii_net_cr"], row["nifty50_trend"], row["nifty500_trend"],
                row["advance_decline"], row["market_closed"],
            ),
        )
        return row
    finally:
        if owns_macro:
            macro_conn.close()
        if owns_portfolio:
            portfolio_conn.close()
