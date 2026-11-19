"""
Nightly job that builds and saves one FeatureSnapshot per (ticker, date) for every active,
non-STALE symbol. Run as `python -m features.builder --date YYYY-MM-DD [--ticker X] [--force]`.
"""

import argparse
import json
import math
import sqlite3
from datetime import date
from typing import Any

import pandas as pd

from core.calendar import is_trading_day
from core.clock import Clock, SystemClock
from core.config import settings
from core.database import get_connection
from features.contracts import FEATURE_SCHEMA_VERSION, FeatureSnapshot, allowed_metric_names
from features.indicators import add_indicators

JOB_NAME = "features"
MIN_SESSIONS_REQUIRED = 200

# Day-3c data-date integrity guard (see features/builder.py run()): on a trading day, a
# ticker whose latest stored OHLCV candle isn't dated as_of_date is "stale". A few stragglers
# are tolerated (skipped individually); more than this fraction fails the whole job.
MAX_STALE_FRACTION = 0.20

# Technical columns add_indicators() appends, and how to cast each back from pandas/numpy
# into a plain JSON-safe Python value (NaN -> None).
_TECHNICAL_COLUMNS = [
    "ema_20",
    "ema_50",
    "ema_200",
    "ema_20_above_50",
    "rsi_14",
    "macd_hist",
    "adx_14",
    "atr_14",
    "volume_surge",
    "obv_slope_sign",
    "dist_52w_high_pct",
    "dist_52w_low_pct",
    "kaufman_er_20",
    "zscore_close_20",
    "parkinson_vol_ratio",
    "skew_60",
]
_BOOL_COLUMNS = {"ema_20_above_50"}
_INT_COLUMNS = {"obv_slope_sign"}

_FUNDAMENTAL_COLUMNS = [
    "roce_pct",
    "roe_pct",
    "pe",
    "pb",
    "peg",
    "debt_to_equity",
    "cfo_to_pat",
    "pat_growth_yoy_pct",
    "revenue_growth_yoy_pct",
    "promoter_holding_pct",
]


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
    return pd.DataFrame([dict(r) for r in rows], columns=["trade_date", "open", "high", "low", "close", "volume"])


def _non_stale_active_tickers(portfolio_conn, ohlcv_conn, ticker_filter: str | None):
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


def _latest_ohlcv_date(ohlcv_conn: sqlite3.Connection, ticker: str, as_of_date: str | None = None) -> date | None:
    if as_of_date is not None:
        row = ohlcv_conn.execute(
            "SELECT MAX(trade_date) AS d FROM ohlcv WHERE ticker = ? AND trade_date <= ?",
            (ticker, as_of_date),
        ).fetchone()
    else:
        row = ohlcv_conn.execute("SELECT MAX(trade_date) AS d FROM ohlcv WHERE ticker = ?", (ticker,)).fetchone()
    value = row["d"] if row else None
    return date.fromisoformat(value) if value else None


def check_data_freshness(
    ohlcv_conn: sqlite3.Connection, portfolio_conn: sqlite3.Connection, tickers: list[str], as_of_date: str
) -> dict:
    """On a trading day, checks whether each ticker's latest stored OHLCV candle is dated
    as_of_date. Not applicable (and always passes) on a non-trading day, since no new candle is
    expected then. Returns {"applicable", "checked", "stale", "stale_tickers", "stale_fraction"}."""
    as_of = date.fromisoformat(as_of_date)
    if not is_trading_day(portfolio_conn, as_of):
        return {"applicable": False, "checked": 0, "stale": 0, "stale_tickers": [], "stale_fraction": 0.0}

    if not tickers:
        return {"applicable": True, "checked": 0, "stale": 0, "stale_tickers": [], "stale_fraction": 0.0}

    # Bulk query to identify all tickers with an OHLCV candle on as_of_date
    placeholders = ",".join("?" * len(tickers))
    rows = ohlcv_conn.execute(
        f"SELECT ticker FROM ohlcv WHERE trade_date = ? AND ticker IN ({placeholders})",
        (as_of_date, *tickers),
    ).fetchall()
    fresh_set = {r[0] if isinstance(r, (tuple, list)) else r["ticker"] for r in rows}
    stale_tickers = [t for t in tickers if t not in fresh_set]
    checked = len(tickers)
    stale = len(stale_tickers)
    return {
        "applicable": True,
        "checked": checked,
        "stale": stale,
        "stale_tickers": stale_tickers,
        "stale_fraction": (stale / checked) if checked else 0.0,
    }


def _macro_row(macro_conn, as_of_date: str):
    row = macro_conn.execute("SELECT india_vix, regime FROM macro_daily WHERE trade_date = ?", (as_of_date,)).fetchone()
    if row is None:
        return None, None
    return row["india_vix"], row["regime"]


def _pipeline_status(conn, job: str, run_date: str) -> str | None:
    row = conn.execute("SELECT status FROM pipeline_runs WHERE job = ? AND run_date = ?", (job, run_date)).fetchone()
    return row["status"] if row else None


def _upsert_terminal_run(conn, run_date: str, status: str, clock: Clock, detail: str | None = None) -> None:
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


def _finish_run(conn, run_date: str, status: str, clock: Clock, detail: str | None = None) -> None:
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


def _bulk_upsert_snapshots(portfolio_conn, snapshots: list[FeatureSnapshot], clock: Clock) -> None:
    if not snapshots:
        return
    now_iso = clock.now_iso()
    params = [(s.ticker, s.as_of_date, s.schema_version, json.dumps(s.features), now_iso) for s in snapshots]
    portfolio_conn.executemany(
        """
        INSERT INTO feature_snapshots (ticker, as_of_date, schema_version, features_json, created_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(ticker, as_of_date, schema_version) DO UPDATE SET
            features_json = excluded.features_json, created_at = excluded.created_at
        """,
        params,
    )


def _load_fundamental_row(fundamental_conn: sqlite3.Connection | None, ticker: str) -> dict | None:
    if fundamental_conn is None:
        return None
    try:
        row = fundamental_conn.execute(
            "SELECT * FROM fundamental_ratios WHERE ticker = ?",
            (ticker,),
        ).fetchone()
        return dict(row) if row else None
    except sqlite3.OperationalError:
        return None


def compute_snapshot_features(
    df: pd.DataFrame,
    india_vix,
    regime,
    fundamental_row: dict | None = None,
    news_sentiment: float | None = None,
    news_article_count: int | None = None,
) -> dict:
    """Runs the technical indicators on `df` and returns the latest row's values, merged into a
    dict pre-seeded with every allowed_metric_names() key set to None. If fundamental_row is provided,
    merges key fundamental and ownership ratios. If news_sentiment is provided, merges news metrics."""
    enriched = add_indicators(df)
    latest = enriched.iloc[-1]

    features = {name: None for name in allowed_metric_names()}
    features["close"] = _clean(latest["close"])
    for col in _TECHNICAL_COLUMNS:
        features[col] = _clean(latest[col], as_bool=col in _BOOL_COLUMNS, as_int=col in _INT_COLUMNS)
    features["india_vix"] = india_vix
    features["regime"] = regime

    if fundamental_row:
        for col in _FUNDAMENTAL_COLUMNS:
            if col in fundamental_row and fundamental_row[col] is not None:
                features[col] = _clean(fundamental_row[col])

        if "fundamentals_source" in fundamental_row:
            features["fundamentals_source"] = fundamental_row["fundamentals_source"]

        # Dynamic nightly DCF discount computation:
        # dcf_discount_pct = (dcf_iv_share - close) / close * 100.0
        iv_share = _clean(fundamental_row.get("dcf_iv_share")) if "dcf_iv_share" in fundamental_row else None
        close_price = features.get("close")
        if iv_share is not None and close_price is not None and close_price > 0:
            features["dcf_discount_pct"] = round(((iv_share - close_price) / close_price) * 100.0, 2)
        else:
            features["dcf_discount_pct"] = None

    if news_sentiment is not None:
        features["news_sentiment"] = _clean(news_sentiment)
    if news_article_count is not None:
        features["news_article_count"] = _clean(news_article_count, as_int=True)

    return features


def run(
    as_of_date: str | None = None,
    clock: Clock | None = None,
    ticker: str | None = None,
    force: bool = False,
    portfolio_conn: sqlite3.Connection | None = None,
    ohlcv_conn: sqlite3.Connection | None = None,
    macro_conn: sqlite3.Connection | None = None,
    fundamental_conn: sqlite3.Connection | None = None,
    news_conn: sqlite3.Connection | None = None,
    data_provider: Any | None = None,
) -> dict:
    """Builds and writes FeatureSnapshots for `as_of_date` (default clock.today()). Returns
    {"status": SUCCESS|FAILED, "written": n, "skipped": n}."""
    clock = clock or SystemClock()
    owns_portfolio = portfolio_conn is None
    owns_ohlcv = ohlcv_conn is None
    owns_macro = macro_conn is None
    owns_fundamental = fundamental_conn is None
    owns_news = news_conn is None
    portfolio_conn = portfolio_conn or get_connection(settings.PORTFOLIO_DB_PATH)
    ohlcv_conn = ohlcv_conn or get_connection(settings.OHLCV_DB_PATH)
    macro_conn = macro_conn or get_connection(settings.MACRO_DB_PATH)
    if fundamental_conn is None:
        try:
            fundamental_conn = get_connection(settings.FUNDAMENTAL_DB_PATH)
        except Exception:
            fundamental_conn = None
    if news_conn is None:
        try:
            news_conn = get_connection(settings.NEWS_DB_PATH)
        except Exception:
            news_conn = None
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

            freshness = check_data_freshness(ohlcv_conn, portfolio_conn, tickers, run_date)
            if freshness["applicable"] and freshness["stale_fraction"] > MAX_STALE_FRACTION:
                detail = (
                    f"data-date integrity check failed: {freshness['stale']}/{freshness['checked']} "
                    f"tickers ({freshness['stale_fraction']:.1%}) have a latest OHLCV candle date "
                    f"other than {run_date} (a trading day); exceeds the {MAX_STALE_FRACTION:.0%} "
                    f"tolerance. Sample stale tickers: {freshness['stale_tickers'][:10]}"
                )
                _finish_run(portfolio_conn, run_date, "FAILED", clock, detail=detail[:500])
                return {"status": "FAILED", "written": 0, "skipped": 0, "detail": detail}
            stale_set = set(freshness["stale_tickers"])

            written, skipped = 0, 0
            snapshots_to_write = []
            for t in tickers:
                if t in stale_set:
                    skipped += 1
                    continue
                if data_provider is not None:
                    df = data_provider.get_ohlcv_window(t, run_date)
                    if len(df) < MIN_SESSIONS_REQUIRED:
                        skipped += 1
                        continue
                    fundamental_row = data_provider.get_fundamental_row(t, run_date)
                    news_sentiment, news_count = data_provider.get_news_sentiment(t, run_date, lookback_days=7)
                else:
                    df = _load_ohlcv(ohlcv_conn, t)
                    if len(df) < MIN_SESSIONS_REQUIRED:
                        skipped += 1
                        continue
                    fundamental_row = _load_fundamental_row(fundamental_conn, t)
                    news_sentiment, news_count = None, None
                    if news_conn is not None:
                        try:
                            from ingestion.sync_news import get_ticker_news_sentiment

                            news_sentiment, news_count, _ = get_ticker_news_sentiment(
                                news_conn, t, run_date, lookback_days=7
                            )
                        except Exception:
                            pass
                features = compute_snapshot_features(
                    df,
                    india_vix,
                    regime,
                    fundamental_row=fundamental_row,
                    news_sentiment=news_sentiment,
                    news_article_count=news_count,
                )
                snapshots_to_write.append(FeatureSnapshot(t, run_date, FEATURE_SCHEMA_VERSION, features))

            _bulk_upsert_snapshots(portfolio_conn, snapshots_to_write, clock)
            written = len(snapshots_to_write)
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
        if owns_fundamental and fundamental_conn is not None:
            fundamental_conn.close()
        if owns_news and news_conn is not None:
            news_conn.close()


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
