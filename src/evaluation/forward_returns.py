"""
Nightly job that backfills each decision's forward return and the Nifty 500 forward return per horizon.
See Plan_v3 §5.3.
"""

import logging
import sqlite3

from core.clock import Clock, SystemClock
from core.config import settings

logger = logging.getLogger(__name__)


def get_forward_trading_dates(ohlcv_conn: sqlite3.Connection, start_date: str, min_coverage: int = 200) -> list[str]:
    """Returns sorted unique trading dates strictly after start_date having sufficient market volume/coverage."""
    rows = ohlcv_conn.execute(
        """
        SELECT trade_date FROM ohlcv
        WHERE trade_date > ?
        GROUP BY trade_date
        HAVING count(*) >= ?
        ORDER BY trade_date ASC
        """,
        (start_date, min_coverage),
    ).fetchall()
    return [r[0] if isinstance(r, (tuple, list)) else r["trade_date"] for r in rows]


def get_universe_mean_return(ohlcv_conn: sqlite3.Connection, start_date: str, end_date: str) -> float:
    """Computes equal-weighted average return of universe stocks between start_date and end_date as Nifty 500 proxy."""
    query = """
    SELECT AVG((c_end.close - c_start.close) / c_start.close * 100.0) AS avg_ret
    FROM ohlcv c_start
    JOIN ohlcv c_end ON c_start.ticker = c_end.ticker AND c_end.trade_date = ?
    WHERE c_start.trade_date = ? AND c_start.close > 0
    """
    row = ohlcv_conn.execute(query, (end_date, start_date)).fetchone()
    if row and row[0] is not None:
        return float(row[0])
    return 0.0


def compute_forward_returns(
    portfolio_conn: sqlite3.Connection,
    ohlcv_conn: sqlite3.Connection,
    clock: Clock | None = None,
    horizons: list[int] | None = None,
    min_date_coverage: int = 200,
) -> dict:
    """
    Backfills forward returns for decisions in portfolio_conn using prices from ohlcv_conn.
    Calculates stock return and Nifty 500 proxy return over horizons (default [1, 5, 10, 20]).
    """
    clock = clock or SystemClock()
    now_iso = clock.now_iso()
    horizons = horizons or getattr(settings, "FORWARD_HORIZONS", [1, 5, 10, 20])

    # Fetch only decisions that do not yet have all horizons computed
    decisions = portfolio_conn.execute(
        """
        SELECT d.id, d.run_date, d.ticker, d.agent_id, d.action
        FROM decisions d
        LEFT JOIN (
            SELECT decision_id, COUNT(*) AS computed_count
            FROM forward_returns
            GROUP BY decision_id
        ) fr ON d.id = fr.decision_id
        WHERE fr.computed_count IS NULL OR fr.computed_count < ?
        ORDER BY d.run_date ASC, d.id ASC
        """,
        (len(horizons),),
    ).fetchall()

    if not decisions:
        return {"status": "SUCCESS", "decisions_checked": 0, "rows_written": 0}

    cand_ids = [d["id"] for d in decisions]
    # Fetch all already computed (decision_id, horizon_days) pairs in bulk
    placeholders = ",".join("?" * len(cand_ids))
    existing_rows = portfolio_conn.execute(
        f"SELECT decision_id, horizon_days FROM forward_returns WHERE decision_id IN ({placeholders})",
        cand_ids,
    ).fetchall()
    already_computed = {
        (
            r[0] if isinstance(r, (tuple, list)) else r["decision_id"],
            r[1] if isinstance(r, (tuple, list)) else r["horizon_days"],
        )
        for r in existing_rows
    }

    # Cache forward dates per run_date
    dates_cache: dict[str, list[str]] = {}
    benchmark_cache: dict[tuple[str, str], float] = {}

    rows_written = 0
    for d in decisions:
        did = d["id"]
        run_date = d["run_date"]
        ticker = d["ticker"]

        if run_date not in dates_cache:
            dates_cache[run_date] = get_forward_trading_dates(ohlcv_conn, run_date, min_coverage=min_date_coverage)
        forward_dates = dates_cache[run_date]

        # Fetch T0 close price
        t0_row = ohlcv_conn.execute(
            "SELECT close FROM ohlcv WHERE ticker = ? AND trade_date = ?",
            (ticker, run_date),
        ).fetchone()
        if not t0_row or not t0_row[0]:
            continue
        t0_close = float(t0_row[0])

        for h in horizons:
            # Check if already computed
            if (did, h) in already_computed:
                continue

            # Check if enough forward dates have elapsed
            if len(forward_dates) < h:
                continue

            target_date = forward_dates[h - 1]

            # Fetch Target date close price
            th_row = ohlcv_conn.execute(
                "SELECT close FROM ohlcv WHERE ticker = ? AND trade_date = ?",
                (ticker, target_date),
            ).fetchone()
            if not th_row or not th_row[0]:
                continue
            th_close = float(th_row[0])

            ret_pct = ((th_close - t0_close) / t0_close) * 100.0

            # Benchmark return
            bench_key = (run_date, target_date)
            if bench_key not in benchmark_cache:
                benchmark_cache[bench_key] = get_universe_mean_return(ohlcv_conn, run_date, target_date)
            nifty_ret_pct = benchmark_cache[bench_key]

            portfolio_conn.execute(
                """
                INSERT OR REPLACE INTO forward_returns
                (decision_id, horizon_days, ret_pct, nifty_ret_pct, computed_on)
                VALUES (?, ?, ?, ?, ?)
                """,
                (did, h, round(ret_pct, 4), round(nifty_ret_pct, 4), now_iso),
            )
            rows_written += 1

    portfolio_conn.commit()
    return {"status": "SUCCESS", "decisions_checked": len(decisions), "rows_written": rows_written}
