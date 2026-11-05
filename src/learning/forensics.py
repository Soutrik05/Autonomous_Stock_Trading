"""
Rule-based post-mortem engine: runs synchronously when a position closes and classifies
the trade into a single forensics label. Results are written back to positions.forensics_type,
positions.regime_at_exit, and positions.diagnosis_json.

Classification priority (first match wins):
  Loss path:
    1. CORP_ACTION_ARTIFACT  -- exit_reason = CORP_ACTION_CLOSE
    2. BROAD_MARKET_DRAG     -- VIX regime was ELEVATED/PANIC for >=50% of holding days
    3. REGIME_MISMATCH       -- VIX >20 at exit AND VIX rose from entry to exit
    4. EARNINGS_SHOCK        -- single-day abs move >=7% in ticker OHLCV during window
    5. FALSE_BREAKOUT        -- price back below entry within first 3 sessions,
                               no volume confirmation (vol < 1.2x 20-day avg)
    6. VALUE_TRAP                       -- contrarian entry held >= horizon with loss <= -5.0%
    7. INSTITUTIONAL_SPONSORSHIP_BREACH -- growth compounder with FII+DII QoQ delta < 0
    8. FUNDAMENTAL_DERATING             -- GARP/compounder held >= horizon with loss <= -5.0%
    9. UNCLASSIFIED                     -- default fallback
  Win path (realized_pnl_pct >= 4.0 AND hold_days >= 3):
    1. EARNINGS_MOMENTUM     -- single-day abs move >=5% during window
    2. MEAN_REVERSION        -- entry RSI < 40 (from feature_snapshots)
    3. TREND_CONTINUATION    -- default win class
    4. UNCLASSIFIED_WIN      -- win but no other win class matched

NOTE on BROAD_MARKET_DRAG: nifty50_trend/nifty500_trend are NULL in macro_daily
(index-level OHLCV not yet ingested -- see ingestion/sync_macro.py). We proxy this
check with VIX-regime elevation. When Nifty absolute data is wired in, replace the
proxy with: Nifty50 close fell >2% from first to last candle of the holding window.

See Plan_v3 section 5.2.
"""
import json
import logging
import sqlite3
from dataclasses import dataclass
from typing import List, Optional

from core.database import get_connection
from settings import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_WIN_PNL_PCT_MIN: float = 4.0
_WIN_HOLD_DAYS_MIN: int = 3
_EARNINGS_SHOCK_PCT: float = 7.0
_EARNINGS_MOMENTUM_PCT: float = 5.0
_FALSE_BREAKOUT_SESSIONS: int = 3
_FALSE_BREAKOUT_VOL_RATIO: float = 1.2
_BROAD_DRAG_VIX_DAYS_RATIO: float = 0.5
_REGIME_MISMATCH_VIX_THRESHOLD: float = 20.0
_MEAN_REVERSION_RSI_MAX: float = 40.0

_HIGH_VOL_REGIMES = {"ELEVATED", "PANIC"}


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class ForensicsResult:
    """Immutable output of one forensics classification run."""
    position_id: int
    forensics_type: str        # one of the 9 labels above
    regime_at_exit: str        # VIX band string at exit date, e.g. NORMAL
    diagnosis_json: str        # full JSON string with raw metrics + reason
    matched: bool = True       # False when a fatal error prevented classification


# ---------------------------------------------------------------------------
# Internal data helpers
# ---------------------------------------------------------------------------

def _fetch_ohlcv_window(
    ohlcv_conn: sqlite3.Connection,
    ticker: str,
    start_date: str,
    end_date: str,
) -> List[sqlite3.Row]:
    """Daily OHLCV rows for ticker between start_date and end_date (inclusive)."""
    return ohlcv_conn.execute(
        """
        SELECT trade_date, open, high, low, close, volume
        FROM ohlcv
        WHERE ticker = ? AND trade_date BETWEEN ? AND ?
        ORDER BY trade_date
        """,
        (ticker, start_date, end_date),
    ).fetchall()


def _fetch_vix_window(
    macro_conn: sqlite3.Connection,
    start_date: str,
    end_date: str,
) -> List[sqlite3.Row]:
    """macro_daily rows with india_vix and regime for the holding window."""
    return macro_conn.execute(
        """
        SELECT trade_date, india_vix, regime
        FROM macro_daily
        WHERE trade_date BETWEEN ? AND ?
          AND market_closed = 0
        ORDER BY trade_date
        """,
        (start_date, end_date),
    ).fetchall()


def _fetch_entry_rsi(
    portfolio_conn: sqlite3.Connection,
    ticker: str,
    entry_date: str,
) -> Optional[float]:
    """RSI at entry date from feature_snapshots (newest schema version)."""
    row = portfolio_conn.execute(
        """
        SELECT features_json
        FROM feature_snapshots
        WHERE ticker = ? AND as_of_date = ?
        ORDER BY schema_version DESC
        LIMIT 1
        """,
        (ticker, entry_date),
    ).fetchone()
    if row is None:
        return None
    try:
        features = json.loads(row["features_json"])
        return float(features.get("rsi_14") or features.get("rsi") or 50.0)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


def _fetch_institutional_delta(
    portfolio_conn: sqlite3.Connection,
    ticker: str,
    as_of_date: str,
) -> Optional[float]:
    """fii_dii_qoq_delta_pct from feature_snapshots at or before as_of_date."""
    row = portfolio_conn.execute(
        """
        SELECT features_json
        FROM feature_snapshots
        WHERE ticker = ? AND as_of_date <= ?
        ORDER BY as_of_date DESC
        LIMIT 1
        """,
        (ticker, as_of_date),
    ).fetchone()
    if row is None:
        return None
    try:
        features = json.loads(row["features_json"])
        val = features.get("fii_dii_qoq_delta_pct")
        return float(val) if val is not None else None
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


def _max_abs_move_pct(rows: List[sqlite3.Row]) -> float:
    """Largest abs((close - open) / open) * 100 across all candles in the window."""
    best = 0.0
    for r in rows:
        o = r["open"]
        if o and o > 0:
            m = abs((r["close"] - o) / o) * 100.0
            if m > best:
                best = m
    return best


def _volume_20d_avg(
    ohlcv_conn: sqlite3.Connection,
    ticker: str,
    before_date: str,
) -> float:
    """Simple average volume over the 20 trading days immediately before before_date."""
    rows = ohlcv_conn.execute(
        """
        SELECT volume FROM ohlcv
        WHERE ticker = ? AND trade_date < ?
        ORDER BY trade_date DESC
        LIMIT 20
        """,
        (ticker, before_date),
    ).fetchall()
    if not rows:
        return 0.0
    return sum(r["volume"] for r in rows) / len(rows)


def _is_false_breakout(
    rows: List[sqlite3.Row],
    entry_price_rupees: float,
    vol_20d_avg: float,
) -> bool:
    """
    True if the close fell below entry_price within the first _FALSE_BREAKOUT_SESSIONS
    sessions AND there was no volume confirmation on that session
    (session volume < 1.2x 20-day avg).
    """
    for r in rows[:_FALSE_BREAKOUT_SESSIONS]:
        if r["close"] < entry_price_rupees:
            if vol_20d_avg <= 0 or r["volume"] < _FALSE_BREAKOUT_VOL_RATIO * vol_20d_avg:
                return True
    return False


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run(
    portfolio_conn: sqlite3.Connection,
    position_id: int,
    clock,  # core.clock.Clock -- kept for future use (audit timestamps)
) -> Optional["ForensicsResult"]:
    """
    Classify a closed position and persist forensics columns to positions.

    Opens its own read-only connections to ohlcv.db and macro.db (Option C).
    Errors during classification fall back to UNCLASSIFIED and are logged, never raised.
    Returns None only when the position row cannot be found.
    """
    pos = portfolio_conn.execute(
        """
        SELECT id, agent_id, ticker,
               avg_entry_price_paise, entry_date,
               exit_date, exit_reason, hold_days,
               realized_pnl_paise, realized_pnl_pct
        FROM positions WHERE id = ?
        """,
        (position_id,),
    ).fetchone()

    if pos is None:
        logger.error("forensics.run: position_id=%s not found -- skipping", position_id)
        return None

    agent_id: str = pos["agent_id"]
    ticker: str = pos["ticker"]
    entry_date: str = pos["entry_date"]
    exit_date: str = pos["exit_date"]
    exit_reason: str = pos["exit_reason"] or ""
    hold_days: int = pos["hold_days"] or 0
    realized_pnl_pct: float = pos["realized_pnl_pct"] or 0.0
    entry_price_rupees: float = (pos["avg_entry_price_paise"] or 0) / 100.0

    ohlcv_conn = get_connection(settings.OHLCV_DB_PATH)
    macro_conn = get_connection(settings.MACRO_DB_PATH)

    try:
        result = _classify(
            portfolio_conn=portfolio_conn,
            ohlcv_conn=ohlcv_conn,
            macro_conn=macro_conn,
            position_id=position_id,
            agent_id=agent_id,
            ticker=ticker,
            entry_date=entry_date,
            exit_date=exit_date,
            exit_reason=exit_reason,
            hold_days=hold_days,
            realized_pnl_pct=realized_pnl_pct,
            entry_price_rupees=entry_price_rupees,
        )
    except Exception:
        logger.exception(
            "forensics.run: unhandled error for position_id=%s; using UNCLASSIFIED",
            position_id,
        )
        result = ForensicsResult(
            position_id=position_id,
            forensics_type="UNCLASSIFIED",
            regime_at_exit="UNKNOWN",
            diagnosis_json=json.dumps({"error": "classification_failed"}),
            matched=False,
        )
    finally:
        ohlcv_conn.close()
        macro_conn.close()

    portfolio_conn.execute(
        """
        UPDATE positions
        SET forensics_type = ?, regime_at_exit = ?, diagnosis_json = ?
        WHERE id = ?
        """,
        (result.forensics_type, result.regime_at_exit, result.diagnosis_json, position_id),
    )
    logger.info(
        "forensics: position_id=%s ticker=%s class=%s",
        position_id, ticker, result.forensics_type,
    )
    return result


# ---------------------------------------------------------------------------
# Persona strategy resolution (Option A)
# ---------------------------------------------------------------------------

def _resolve_persona_profile(agent_id: str) -> dict:
    """
    Option A: Resolves strategy archetype and thresholds from agents.personas.get_persona(agent_id).
    Falls back gracefully if the agent_id is not in the registry (e.g., baseline).
    """
    from agents.personas import get_persona

    normalized_id = (agent_id or "").lower().replace("agent-", "")
    if normalized_id.startswith("baseline"):
        return {
            "strategy_type": "MOMENTUM",
            "min_win_pnl_pct": 4.0,
            "min_win_hold_days": 3,
            "eval_horizon_days": 5,
        }
    try:
        persona = get_persona(normalized_id)
        return {
            "strategy_type": getattr(persona, "strategy_type", "MOMENTUM"),
            "min_win_pnl_pct": getattr(persona, "min_win_pnl_pct", 4.0),
            "min_win_hold_days": getattr(persona, "min_win_hold_days", 3),
            "eval_horizon_days": getattr(persona, "eval_horizon_days", 5),
        }
    except Exception:
        return {
            "strategy_type": "MOMENTUM",
            "min_win_pnl_pct": 4.0,
            "min_win_hold_days": 3,
            "eval_horizon_days": 5,
        }


# ---------------------------------------------------------------------------
# Classification engine
# ---------------------------------------------------------------------------

def _classify(
    portfolio_conn: sqlite3.Connection,
    ohlcv_conn: sqlite3.Connection,
    macro_conn: sqlite3.Connection,
    position_id: int,
    agent_id: str,
    ticker: str,
    entry_date: str,
    exit_date: str,
    exit_reason: str,
    hold_days: int,
    realized_pnl_pct: float,
    entry_price_rupees: float,
) -> ForensicsResult:
    profile = _resolve_persona_profile(agent_id)
    strategy_type = profile["strategy_type"]
    min_win_pnl_pct = profile["min_win_pnl_pct"]
    min_win_hold_days = profile["min_win_hold_days"]
    eval_horizon_days = profile["eval_horizon_days"]

    is_win = (
        realized_pnl_pct >= min_win_pnl_pct and hold_days >= min_win_hold_days
    )

    ohlcv_rows = _fetch_ohlcv_window(ohlcv_conn, ticker, entry_date, exit_date)
    vix_rows = _fetch_vix_window(macro_conn, entry_date, exit_date)
    entry_rsi = _fetch_entry_rsi(portfolio_conn, ticker, entry_date)

    # Aggregate VIX metrics
    vix_at_entry: Optional[float] = vix_rows[0]["india_vix"] if vix_rows else None
    vix_at_exit: Optional[float] = vix_rows[-1]["india_vix"] if vix_rows else None
    regime_at_exit: str = vix_rows[-1]["regime"] if vix_rows else "UNKNOWN"
    high_vol_days = sum(1 for r in vix_rows if r["regime"] in _HIGH_VOL_REGIMES)
    total_vix_days = len(vix_rows)

    max_move = _max_abs_move_pct(ohlcv_rows)
    vol_20d_avg = _volume_20d_avg(ohlcv_conn, ticker, entry_date)

    raw: dict = {
        "ticker": ticker,
        "agent_id": agent_id,
        "strategy_type": strategy_type,
        "min_win_pnl_pct": min_win_pnl_pct,
        "min_win_hold_days": min_win_hold_days,
        "eval_horizon_days": eval_horizon_days,
        "entry_date": entry_date,
        "exit_date": exit_date,
        "hold_days": hold_days,
        "realized_pnl_pct": round(realized_pnl_pct, 4),
        "entry_price_rupees": round(entry_price_rupees, 2),
        "exit_reason": exit_reason,
        "vix_at_entry": vix_at_entry,
        "vix_at_exit": vix_at_exit,
        "regime_at_exit": regime_at_exit,
        "high_vol_regime_days": high_vol_days,
        "total_macro_days_in_window": total_vix_days,
        "max_single_day_move_pct": round(max_move, 4),
        "entry_rsi_14": entry_rsi,
        "vol_20d_avg_at_entry": round(vol_20d_avg, 1) if vol_20d_avg else None,
        "ohlcv_rows_in_window": len(ohlcv_rows),
        "is_win": is_win,
    }

    # ------------------------------------------------------------------
    # Loss classification path
    # ------------------------------------------------------------------
    if not is_win:
        # 1. Corp action artifact
        if exit_reason == "CORP_ACTION_CLOSE":
            return _mk(position_id, "CORP_ACTION_ARTIFACT", regime_at_exit, raw,
                       "Exit reason was CORP_ACTION_CLOSE.")

        # 2. Broad market drag (VIX-regime proxy)
        drag_ratio = high_vol_days / total_vix_days if total_vix_days > 0 else 0.0
        if drag_ratio >= _BROAD_DRAG_VIX_DAYS_RATIO:
            return _mk(
                position_id, "BROAD_MARKET_DRAG", regime_at_exit, raw,
                (
                    f"ELEVATED/PANIC VIX on {high_vol_days}/{total_vix_days} holding days "
                    f"({drag_ratio:.0%}). Proxy for Nifty-50-fell->2% (not yet ingested)."
                ),
                extra={"broad_drag_ratio": round(drag_ratio, 4)},
            )

        # 3. Regime mismatch
        if (
            vix_at_exit is not None
            and vix_at_exit > _REGIME_MISMATCH_VIX_THRESHOLD
            and vix_at_entry is not None
            and vix_at_exit > vix_at_entry
        ):
            return _mk(
                position_id, "REGIME_MISMATCH", regime_at_exit, raw,
                (
                    f"VIX at exit {vix_at_exit:.1f} > {_REGIME_MISMATCH_VIX_THRESHOLD} "
                    f"and rose from {vix_at_entry:.1f} at entry."
                ),
            )

        # 4. Earnings shock
        if max_move >= _EARNINGS_SHOCK_PCT:
            return _mk(
                position_id, "EARNINGS_SHOCK", regime_at_exit, raw,
                f"Single-day abs move {max_move:.2f}% >= {_EARNINGS_SHOCK_PCT}%.",
            )

        # 5. False breakout (ONLY for momentum & hybrid strategies)
        if strategy_type in ("MOMENTUM", "HYBRID"):
            if ohlcv_rows and _is_false_breakout(ohlcv_rows, entry_price_rupees, vol_20d_avg):
                return _mk(
                    position_id, "FALSE_BREAKOUT", regime_at_exit, raw,
                    (
                        f"Close fell below entry ({entry_price_rupees:.2f}) within "
                        f"first {_FALSE_BREAKOUT_SESSIONS} sessions without volume surge."
                    ),
                )

        # 6. Value trap (for contrarian / value strategies, e.g. Howard Marks)
        if strategy_type == "VALUE_CONTRARIAN" and hold_days >= eval_horizon_days and realized_pnl_pct <= -5.0:
            return _mk(
                position_id, "VALUE_TRAP", regime_at_exit, raw,
                (
                    f"Contrarian entry held {hold_days}d >= {eval_horizon_days}d horizon with "
                    f"realized loss {realized_pnl_pct:.2f}%."
                ),
            )

        # 7. Institutional sponsorship breach (for GROWTH_COMPOUNDER e.g. Jhunjhunwala)
        if strategy_type == "GROWTH_COMPOUNDER":
            inst_delta = _fetch_institutional_delta(portfolio_conn, ticker, exit_date)
            if inst_delta is not None and inst_delta < 0.0:
                return _mk(
                    position_id, "INSTITUTIONAL_SPONSORSHIP_BREACH", regime_at_exit, raw,
                    (
                        f"Growth compounder suffered institutional outflow: FII+DII QoQ change was "
                        f"{inst_delta:+.2f}% at exit window."
                    ),
                    extra={"fii_dii_qoq_delta_pct": inst_delta},
                )

        # 8. Fundamental de-rating (for GARP & compounder strategies, e.g. Lynch & RJ)
        if strategy_type in ("GARP", "GROWTH_COMPOUNDER") and hold_days >= eval_horizon_days and realized_pnl_pct <= -5.0:
            return _mk(
                position_id, "FUNDAMENTAL_DERATING", regime_at_exit, raw,
                (
                    f"Long-horizon holding held {hold_days}d >= {eval_horizon_days}d horizon with "
                    f"loss {realized_pnl_pct:.2f}%; thesis failed to compound over evaluation window."
                ),
            )

        # 8. Fallback
        return _mk(position_id, "UNCLASSIFIED", regime_at_exit, raw, "No loss class matched.")

    # ------------------------------------------------------------------
    # Win classification path
    # ------------------------------------------------------------------

    # 1. Earnings momentum
    if max_move >= _EARNINGS_MOMENTUM_PCT:
        return _mk(
            position_id, "EARNINGS_MOMENTUM", regime_at_exit, raw,
            f"Win + single-day abs move {max_move:.2f}% >= {_EARNINGS_MOMENTUM_PCT}%.",
        )

    # 2. Mean reversion
    if entry_rsi is not None and entry_rsi < _MEAN_REVERSION_RSI_MAX:
        return _mk(
            position_id, "MEAN_REVERSION", regime_at_exit, raw,
            f"Win + entry RSI {entry_rsi:.1f} < {_MEAN_REVERSION_RSI_MAX}.",
        )

    # 3. Valuation re-rating / compounding win (for GARP & Compounders)
    if strategy_type in ("GARP", "GROWTH_COMPOUNDER"):
        return _mk(
            position_id, "VALUATION_RERATING", regime_at_exit, raw,
            f"Multi-week fundamental win held {hold_days}d with return {realized_pnl_pct:.2f}%.",
        )

    # 4. Contrarian rebound (Value Contrarian)
    if strategy_type == "VALUE_CONTRARIAN":
        return _mk(
            position_id, "CONTRARIAN_REBOUND", regime_at_exit, raw,
            f"Contrarian recovery win held {hold_days}d with return {realized_pnl_pct:.2f}%.",
        )

    # 5. Trend continuation (default win)
    return _mk(
        position_id, "TREND_CONTINUATION", regime_at_exit, raw,
        "Win with sustained trend following momentum rules.",
    )


def _mk(
    position_id: int,
    forensics_type: str,
    regime_at_exit: str,
    raw: dict,
    reason: str = "",
    extra: Optional[dict] = None,
) -> ForensicsResult:
    diag = dict(raw)
    diag["forensics_type"] = forensics_type
    diag["reason"] = reason
    if extra:
        diag.update(extra)
    return ForensicsResult(
        position_id=position_id,
        forensics_type=forensics_type,
        regime_at_exit=regime_at_exit,
        diagnosis_json=json.dumps(diag, default=str),
    )
