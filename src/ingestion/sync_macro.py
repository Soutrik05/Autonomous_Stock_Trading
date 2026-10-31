"""
Syncs India VIX, computes rule-based daily regime from VIX_BANDS, calculates market breadth
(advance/decline ratio) across active constituents in ohlcv.db, determines index trends
(Nifty 50 and Nifty 500), and writes one macro_daily row to macro.db.
See Plan_v3 §2.5.
"""
import sqlite3
from datetime import date, datetime, timezone, timedelta
from typing import Optional, Tuple

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


def _extract_net_cr(records: list, target_iso: str) -> Optional[float]:
    """Finds record matching target_iso date and returns net buy-sell amount in Crores."""
    ist = timezone(timedelta(hours=5, minutes=30))
    for rec in records:
        ts = rec.get("time_stamp")
        if not ts:
            continue
        rec_date = datetime.fromtimestamp(ts / 1000, tz=ist).date().isoformat()
        if rec_date == target_iso:
            buy = rec.get("buy_amount") or 0.0
            sell = rec.get("sell_amount") or 0.0
            return round(buy - sell, 2)
    return None


def compute_advance_decline(ohlcv_conn: Optional[sqlite3.Connection], target_iso: str) -> Optional[float]:
    """Computes advance/decline ratio across active constituents on target_iso from ohlcv.db.
    Compares close(target_iso) vs close(prev_trade_date).
    If no prior session exists, compares close vs open.
    Returns round(advances / declines, 2) if declines > 0, else float(advances) if advances > 0 else 1.0.
    """
    if ohlcv_conn is None:
        return None
    try:
        # Find preceding trade date with constituent coverage
        row = ohlcv_conn.execute(
            """
            SELECT trade_date 
            FROM ohlcv 
            WHERE trade_date < ? 
            GROUP BY trade_date 
            HAVING COUNT(*) >= 50 
            ORDER BY trade_date DESC 
            LIMIT 1
            """,
            (target_iso,),
        ).fetchone()

        if row and row[0]:
            prev_d = row[0]
            counts = ohlcv_conn.execute(
                """
                SELECT 
                    SUM(CASE WHEN curr.close > prev.close THEN 1 ELSE 0 END) AS advances,
                    SUM(CASE WHEN curr.close < prev.close THEN 1 ELSE 0 END) AS declines
                FROM ohlcv curr
                JOIN ohlcv prev ON curr.ticker = prev.ticker AND prev.trade_date = ?
                WHERE curr.trade_date = ?
                """,
                (prev_d, target_iso),
            ).fetchone()
        else:
            # Fallback to intraday close vs open
            counts = ohlcv_conn.execute(
                """
                SELECT 
                    SUM(CASE WHEN close > open THEN 1 ELSE 0 END) AS advances,
                    SUM(CASE WHEN close < open THEN 1 ELSE 0 END) AS declines
                FROM ohlcv
                WHERE trade_date = ?
                """,
                (target_iso,),
            ).fetchone()

        if not counts or (counts[0] is None and counts[1] is None):
            return None

        advances = counts[0] or 0
        declines = counts[1] or 0
        if advances == 0 and declines == 0:
            return None
        if declines == 0:
            return float(advances) if advances > 0 else 1.0
        return round(advances / declines, 2)
    except Exception:
        return None


def _trend_from_candles(candles: list, target_iso: str, window_size: int = 20) -> Optional[str]:
    """Computes trend (BULLISH/BEARISH/SIDEWAYS) from daily candles [ts, o, h, l, c, v, ...].
    Calculates 20-day SMA up to target_iso and compares close vs SMA."""
    if not candles:
        return None
    sorted_candles = sorted(candles, key=lambda c: str(c[0]))
    target_dt = target_iso[:10]
    sub = [c for c in sorted_candles if str(c[0])[:10] <= target_dt]
    if not sub:
        return None
    curr_close = float(sub[-1][4])
    window = [float(c[4]) for c in sub[-window_size:]]
    if not window:
        return None
    sma = sum(window) / len(window)
    diff_pct = (curr_close - sma) / sma * 100.0
    if diff_pct >= 0.2:
        return "BULLISH"
    elif diff_pct <= -0.2:
        return "BEARISH"
    else:
        return "SIDEWAYS"


def _trend_from_quote(quote: dict) -> Optional[str]:
    """Computes trend from quote dict with last_price and ohlc/net_change."""
    if not quote:
        return None
    last_price = quote.get("last_price")
    ohlc = quote.get("ohlc") or {}
    prev_close = ohlc.get("close")
    net_change = quote.get("net_change")
    if last_price is not None and prev_close is not None and prev_close > 0:
        pct = (last_price - prev_close) / prev_close
    elif net_change is not None and last_price is not None and (last_price - net_change) > 0:
        pct = net_change / (last_price - net_change)
    else:
        return None
    if pct >= 0.003:
        return "BULLISH"
    elif pct <= -0.003:
        return "BEARISH"
    else:
        return "SIDEWAYS"


def compute_index_trends(
    client, target_iso: str, advance_decline: Optional[float] = None
) -> Tuple[Optional[str], Optional[str]]:
    """Determines nifty50_trend and nifty500_trend.
    Order of resolution:
    1. Historical daily candles from client.get_daily_candles (SMA-20 trend)
    2. Single-day market quote from client.get_quotes (net change trend)
    3. Fallback to market breadth (advance_decline ratio)
    """
    n50_trend = None
    n500_trend = None

    # 1. Try historical candles
    if hasattr(client, "get_daily_candles"):
        try:
            target_d = date.fromisoformat(target_iso)
            from_d = (target_d - timedelta(days=45)).isoformat()
            candles_50 = client.get_daily_candles("NSE_INDEX|Nifty 50", from_d, target_iso)
            n50_trend = _trend_from_candles(candles_50, target_iso)
        except Exception:
            pass
        try:
            target_d = date.fromisoformat(target_iso)
            from_d = (target_d - timedelta(days=45)).isoformat()
            candles_500 = client.get_daily_candles("NSE_INDEX|Nifty 500", from_d, target_iso)
            n500_trend = _trend_from_candles(candles_500, target_iso)
        except Exception:
            pass

    # 2. Try market quotes if candles did not resolve
    if (n50_trend is None or n500_trend is None) and hasattr(client, "get_quotes"):
        try:
            quotes = client.get_quotes(["NSE_INDEX|Nifty 50", "NSE_INDEX|Nifty 500"])
            if n50_trend is None:
                q50 = quotes.get("NSE_INDEX:Nifty 50") or quotes.get("NSE_INDEX|Nifty 50")
                n50_trend = _trend_from_quote(q50)
            if n500_trend is None:
                q500 = quotes.get("NSE_INDEX:Nifty 500") or quotes.get("NSE_INDEX|Nifty 500")
                n500_trend = _trend_from_quote(q500)
        except Exception:
            pass

    # 3. Fallback to market breadth if still unresolved
    if advance_decline is not None:
        breadth_trend = "BULLISH" if advance_decline >= 1.25 else ("BEARISH" if advance_decline <= 0.80 else "SIDEWAYS")
        if n50_trend is None:
            n50_trend = breadth_trend
        if n500_trend is None:
            n500_trend = breadth_trend

    return n50_trend, n500_trend


def sync_macro(
    client,
    clock: Clock,
    macro_conn: sqlite3.Connection = None,
    portfolio_conn: sqlite3.Connection = None,
    as_of_date: str = None,
    ohlcv_conn: sqlite3.Connection = None,
) -> dict:
    """Fetches India VIX, FII and DII net cash flows, computes advance/decline breadth
    from ohlcv.db, determines index trends, and writes one macro_daily row for as_of_date
    (default: clock.today()). Returns the row written as a dict."""
    owns_macro = macro_conn is None
    owns_portfolio = portfolio_conn is None
    owns_ohlcv = False

    if macro_conn is None:
        macro_conn = get_connection(settings.MACRO_DB_PATH)
        ensure_schema(macro_conn)
    if portfolio_conn is None:
        portfolio_conn = get_connection(settings.PORTFOLIO_DB_PATH)
    if ohlcv_conn is None:
        try:
            ohlcv_conn = get_connection(settings.OHLCV_DB_PATH)
            owns_ohlcv = True
        except Exception:
            ohlcv_conn = None

    try:
        target_date: date = date.fromisoformat(as_of_date) if as_of_date else clock.today()
        target_iso = target_date.isoformat()
        market_closed = 0 if is_trading_day(portfolio_conn, target_date) else 1

        vix_quote = client.get_india_vix() if hasattr(client, "get_india_vix") else None
        india_vix = vix_quote.get("last_price") if vix_quote else None
        regime = compute_regime(india_vix) if india_vix is not None else "UNKNOWN"

        fii_net_cr = None
        if hasattr(client, "get_fii_data"):
            try:
                fii_records = client.get_fii_data(data_type="NSE_EQ|CASH", interval="1D")
                fii_net_cr = _extract_net_cr(fii_records, target_iso)
            except Exception:
                pass

        dii_net_cr = None
        if hasattr(client, "get_dii_data"):
            try:
                dii_records = client.get_dii_data(data_type="NSE_EQ|CASH", interval="1D")
                dii_net_cr = _extract_net_cr(dii_records, target_iso)
            except Exception:
                pass

        # Compute market breadth from ohlcv constituents
        advance_decline = compute_advance_decline(ohlcv_conn, target_iso)

        # Compute index trends
        nifty50_trend, nifty500_trend = compute_index_trends(client, target_iso, advance_decline)

        row = {
            "trade_date": target_iso,
            "regime": regime,
            "india_vix": india_vix,
            "fii_net_cr": fii_net_cr,
            "dii_net_cr": dii_net_cr,
            "nifty50_trend": nifty50_trend,
            "nifty500_trend": nifty500_trend,
            "advance_decline": advance_decline,
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
                fii_net_cr = COALESCE(excluded.fii_net_cr, macro_daily.fii_net_cr),
                dii_net_cr = COALESCE(excluded.dii_net_cr, macro_daily.dii_net_cr),
                nifty50_trend = COALESCE(excluded.nifty50_trend, macro_daily.nifty50_trend),
                nifty500_trend = COALESCE(excluded.nifty500_trend, macro_daily.nifty500_trend),
                advance_decline = COALESCE(excluded.advance_decline, macro_daily.advance_decline),
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
        if owns_macro and macro_conn is not None:
            macro_conn.close()
        if owns_portfolio and portfolio_conn is not None:
            portfolio_conn.close()
        if owns_ohlcv and ohlcv_conn is not None:
            ohlcv_conn.close()
