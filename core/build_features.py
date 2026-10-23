"""
Nightly job that builds and saves one FeatureSnapshot per (ticker, date) for every active,
non-STALE symbol. Run as `python -m core.build_features --date YYYY-MM-DD [--ticker X] [--force]`.
See Plan_v3 §1.4, §2.1.
"""
import argparse
import json
import math
import sqlite3
from typing import Optional

import pandas as pd

from core.clock import Clock, SystemClock
from core.database import get_connection
from core.features import FEATURE_SCHEMA_VERSION, FeatureSnapshot, allowed_metric_names
from settings import settings
from technical import add_indicators

JOB_NAME = "features"
MIN_SESSIONS_REQUIRED = 200

# Technical columns add_indicators() appends, and how to cast each back from pandas/numpy
# into a plain JSON-safe Python value (NaN -> None).
_TECHNICAL_COLUMNS = [
    "ema_20", "ema_50", "ema_200", "ema_20_above_50", "rsi_14", "macd_hist", "adx_14",
    "atr_14", "volume_surge", "obv_slope_sign", "dist_52w_high_pct", "dist_52w_low_pct",
]
_BOOL_COLUMNS = {"ema_20_above_50"}
_INT_COLUMNS = {"obv_slope_sign"}


def _clean(value, as_bool=False, as_int=False):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    if as_bool:
        return bool(value)
    if as_int:
        return int(value)
    return float(value)


def _load_ohlcv(ohlcv_conn: sqlite3.Connection, ticker: str) -> pd.DataFrame:
    rows = ohlcv_conn.execute(
        "SELECT trade_date, open, high, low, close, volume FROM ohlcv WHERE ticker = ? ORDER BY trade_date",
        (ticker,),
    ).fetchall()
    return pd.DataFrame(
        [dict(r) for r in rows], columns=["trade_date", "open", "high", "low", "close", "volume"]
    )


def _non_stale_active_tickers(portfolio_conn, ohlcv_conn, ticker_filter: Optional[str]):
    query = "SELECT ticker FROM symbols WHERE is_active = 1"
    params = []
    if ticker_filter:
        query += " AND ticker = ?"
        params.append(ticker_filter)
    query += " ORDER BY ticker"
    all_tickers = [r["ticker"] for r in portfolio_conn.execute(query, params).fetchall()]
    stale = {
        r["ticker"]
        for r in ohlcv_conn.execute("SELECT ticker FROM ticker_status WHERE status = 'STALE_DATA'").fetchall()
    }
    return [t for t in all_tickers if t not in stale]


def _macro_row(macro_conn, as_of_date: str):
    row = macro_conn.execute(
        "SELECT india_vix, regime FROM macro_daily WHERE trade_date = ?", (as_of_date,)
    ).fetchone()
    if row is None:
        return None, None
    return row["india_vix"], row["regime"]


def _pipeline_status(conn, job: str, run_date: str) -> Optional[str]:
    row = conn.execute("SELECT status FROM pipeline_runs WHERE job = ? AND run_date = ?", (job, run_date)).fetchone()
    return row["status"] if row else None


def _upsert_terminal_run(conn, run_date: str, status: str, clock: Clock, detail: str = None) -> None:
    now = clock.now_iso()
    conn.execute(
        """
        INSERT INTO pipeline_runs (job, run_date, status, started_at, finished_at, detail)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(job, run_date) DO UPDATE SET
            status = excluded.status, started_at = excluded.started_at,
            finished_at = excluded.finished_at, detail = excluded.detail
        """,
        (JOB_NAME, run_date, status, now, now, detail),
    )


def _start_run(conn, run_date: str, clock: Clock) -> None:
    conn.execute(
        """
        INSERT INTO pipeline_runs (job, run_date, status, started_at, finished_at, detail)
        VALUES (?, ?, 'RUNNING', ?, NULL, NULL)
        ON CONFLICT(job, run_date) DO UPDATE SET
            status = 'RUNNING', started_at = excluded.started_at, finished_at = NULL, detail = NULL
        """,
        (JOB_NAME, run_date, clock.now_iso()),
    )


def _finish_run(conn, run_date: str, status: str, clock: Clock, detail: str = None) -> None:
    conn.execute(
        "UPDATE pipeline_runs SET status = ?, finished_at = ?, detail = ? WHERE job = ? AND run_date = ?",
        (status, clock.now_iso(), detail, JOB_NAME, run_date),
    )


def _upsert_snapshot(portfolio_conn, snapshot: FeatureSnapshot, clock: Clock) -> None:
    portfolio_conn.execute(
        """
        INSERT INTO feature_snapshots (ticker, as_of_date, schema_version, features_json, created_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(ticker, as_of_date, schema_version) DO UPDATE SET
            features_json = excluded.features_json, created_at = excluded.created_at
        """,
        (snapshot.ticker, snapshot.as_of_date, snapshot.schema_version, json.dumps(snapshot.features), clock.now_iso()),
    )


def compute_snapshot_features(df: pd.DataFrame, india_vix, regime) -> dict:
    """Runs the technical indicators on `df` and returns the latest row's values, merged into a
    dict pre-seeded with every allowed_metric_names() key set to None (fundamental, ownership and
    news features are not available yet)."""
    enriched = add_indicators(df)
    latest = enriched.iloc[-1]

    features = {name: None for name in allowed_metric_names()}
    features["close"] = _clean(latest["close"])
    for col in _TECHNICAL_COLUMNS:
        features[col] = _clean(latest[col], as_bool=col in _BOOL_COLUMNS, as_int=col in _INT_COLUMNS)
    features["india_vix"] = india_vix
    features["regime"] = regime
    return features


def run(as_of_date: str = None, clock: Clock = None, ticker: str = None, force: bool = False,
        portfolio_conn: sqlite3.Connection = None, ohlcv_conn: sqlite3.Connection = None,
        macro_conn: sqlite3.Connection = None) -> dict:
    """Builds and writes FeatureSnapshots for `as_of_date` (default clock.today()). Returns
    {"status": SUCCESS|FAILED, "written": n, "skipped": n}."""
    clock = clock or SystemClock()
    owns_portfolio = portfolio_conn is None
    owns_ohlcv = ohlcv_conn is None
    owns_macro = macro_conn is None
    portfolio_conn = portfolio_conn or get_connection(settings.PORTFOLIO_DB_PATH)
    ohlcv_conn = ohlcv_conn or get_connection(settings.OHLCV_DB_PATH)
    macro_conn = macro_conn or get_connection(settings.MACRO_DB_PATH)
    try:
        run_date = as_of_date or clock.today().isoformat()

        if not force:
            ingestion_status = _pipeline_status(portfolio_conn, "ingestion", run_date)
            if ingestion_status != "SUCCESS":
                detail = f"ingestion status for {run_date} is {ingestion_status!r}, expected SUCCESS"
                _upsert_terminal_run(portfolio_conn, run_date, "FAILED", clock, detail=detail)
                return {"status": "FAILED", "written": 0, "skipped": 0, "detail": detail}

        _start_run(portfolio_conn, run_date, clock)
        try:
            india_vix, regime = _macro_row(macro_conn, run_date)
            tickers = _non_stale_active_tickers(portfolio_conn, ohlcv_conn, ticker)

            written, skipped = 0, 0
            for t in tickers:
                df = _load_ohlcv(ohlcv_conn, t)
                if len(df) < MIN_SESSIONS_REQUIRED:
                    skipped += 1
                    continue
                features = compute_snapshot_features(df, india_vix, regime)
                snapshot = FeatureSnapshot(t, run_date, FEATURE_SCHEMA_VERSION, features)
                _upsert_snapshot(portfolio_conn, snapshot, clock)
                written += 1
        except Exception as exc:
            _finish_run(portfolio_conn, run_date, "FAILED", clock, detail=str(exc)[:500])
            raise

        _finish_run(portfolio_conn, run_date, "SUCCESS", clock, detail=f"written={written} skipped={skipped}")
        return {"status": "SUCCESS", "written": written, "skipped": skipped}
    finally:
        if owns_portfolio:
            portfolio_conn.close()
        if owns_ohlcv:
            ohlcv_conn.close()
        if owns_macro:
            macro_conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Nightly FeatureSnapshot builder.")
    parser.add_argument("--date", dest="date_str", default=None, help="YYYY-MM-DD, default: today (IST)")
    parser.add_argument("--ticker", dest="ticker", default=None, help="Only this one ticker")
    parser.add_argument("--force", dest="force", action="store_true", help="Skip the ingestion=SUCCESS check")
    args = parser.parse_args()
    result = run(as_of_date=args.date_str, ticker=args.ticker, force=args.force)
    print(f"features: {result['status']} written={result['written']} skipped={result['skipped']}")


if __name__ == "__main__":
    main()
