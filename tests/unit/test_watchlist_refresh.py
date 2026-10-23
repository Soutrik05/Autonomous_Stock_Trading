"""
Unit tests for precompute/watchlist_refresh.py: Stage 0 liquidity/circuit gates, Stage 1
persona hurdles, the sector cap, TTL lock/expiry, and the review pool — all against in-memory
databases and fake FeatureSnapshots (no live network, no real OHLCV fetch).
See Plan_v3 §6.
"""
import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pytest

from core.clock import FakeClock
from datetime import datetime
from ingestion.sync_ohlcv import ensure_schema as ensure_ohlcv_schema
from precompute.watchlist_refresh import get_review_pool, run
from settings import settings

PORTFOLIO_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "db" / "schema.sql"
AS_OF = "2026-03-02"
NOW = "2026-03-02T22:00:00+05:30"


def make_portfolio_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(PORTFOLIO_SCHEMA_PATH.read_text(encoding="utf-8"))
    return conn


def make_ohlcv_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    ensure_ohlcv_schema(conn)
    return conn


def mark_features_success(conn, run_date=AS_OF):
    conn.execute(
        "INSERT INTO pipeline_runs (job, run_date, status, started_at, finished_at, detail) "
        "VALUES ('features', ?, 'SUCCESS', ?, ?, NULL)",
        (run_date, NOW, NOW),
    )


def insert_symbol(conn, ticker, sector="TestSector"):
    conn.execute(
        "INSERT INTO symbols (ticker, instrument_key, isin, company_name, sector, is_active) "
        "VALUES (?, ?, 'ISIN0000000', 'Test Co', ?, 1)",
        (ticker, f"NSE_EQ|{ticker}", sector),
    )


def insert_ohlcv(ohlcv_conn, ticker, as_of=AS_OF, n_days=20, volume=600_000, close=100.0, boost_last_n=0, boost_volume=None):
    """Writes n_days of daily rows ending at as_of. If boost_last_n > 0, the most recent
    boost_last_n rows use boost_volume instead (to control SMA5 vs SMA20)."""
    end = date.fromisoformat(as_of)
    for i in range(n_days):
        d = end - timedelta(days=n_days - 1 - i)
        v = boost_volume if (boost_last_n and i >= n_days - boost_last_n) else volume
        ohlcv_conn.execute(
            "INSERT INTO ohlcv (ticker, trade_date, open, high, low, close, volume) VALUES (?,?,?,?,?,?,?)",
            (ticker, d.isoformat(), close, close, close, close, v),
        )


def set_status(ohlcv_conn, ticker, status="OK"):
    ohlcv_conn.execute(
        "INSERT INTO ticker_status (ticker, status, updated_at) VALUES (?, ?, ?)", (ticker, status, NOW)
    )


def insert_snapshot(portfolio_conn, ticker, features, as_of=AS_OF):
    portfolio_conn.execute(
        "INSERT INTO feature_snapshots (ticker, as_of_date, schema_version, features_json, created_at) "
        "VALUES (?, ?, 1, ?, ?)",
        (ticker, as_of, json.dumps(features), NOW),
    )


def passing_simons_features(close=100.0, ema_200=90.0, rsi=60.0, volume_surge=1.5, macd_hist=1.0):
    return {
        "close": close, "ema_200": ema_200, "ema_20_above_50": True, "rsi_14": rsi,
        "volume_surge": volume_surge, "macd_hist": macd_hist,
    }


def seed_qualifying_candidate(portfolio_conn, ohlcv_conn, ticker, sector="TestSector", **feature_overrides):
    """A ticker that passes Stage 0 (high turnover + SMA5>SMA20) and, unless overridden, Stage 1."""
    insert_symbol(portfolio_conn, ticker, sector)
    insert_ohlcv(ohlcv_conn, ticker, volume=600_000, close=100.0, boost_last_n=5, boost_volume=900_000)
    set_status(ohlcv_conn, ticker, "OK")
    features = passing_simons_features()
    features.update(feature_overrides)
    insert_snapshot(portfolio_conn, ticker, features)
    return features


# --- Stage 0 -------------------------------------------------------------------------------------

def test_stage0_excludes_low_turnover_stock():
    portfolio, ohlcv = make_portfolio_db(), make_ohlcv_db()
    mark_features_success(portfolio)
    seed_qualifying_candidate(portfolio, ohlcv, "GOODVOL")

    insert_symbol(portfolio, "LOWVOL")
    insert_ohlcv(ohlcv, "LOWVOL", volume=10_000, close=100.0)  # turnover = 1,000,000 << 5 crore
    set_status(ohlcv, "LOWVOL", "OK")
    insert_snapshot(portfolio, "LOWVOL", passing_simons_features())

    result = run(as_of_date=AS_OF, agent_id="simons", clock=FakeClock(datetime(2026, 3, 2, 22, 0)),
                 portfolio_conn=portfolio, ohlcv_conn=ohlcv)
    tickers = [r["ticker"] for r in result["watchlist"]]
    assert "GOODVOL" in tickers
    assert "LOWVOL" not in tickers


def test_stage0_excludes_locked_circuit_stock():
    portfolio, ohlcv = make_portfolio_db(), make_ohlcv_db()
    mark_features_success(portfolio)
    seed_qualifying_candidate(portfolio, ohlcv, "GOODVOL")

    insert_symbol(portfolio, "FROZEN")
    insert_ohlcv(ohlcv, "FROZEN", volume=600_000, close=100.0, boost_last_n=5, boost_volume=900_000)
    set_status(ohlcv, "FROZEN", "LOCKED_CIRCUIT")
    insert_snapshot(portfolio, "FROZEN", passing_simons_features())

    result = run(as_of_date=AS_OF, agent_id="simons", clock=FakeClock(datetime(2026, 3, 2, 22, 0)),
                 portfolio_conn=portfolio, ohlcv_conn=ohlcv)
    tickers = [r["ticker"] for r in result["watchlist"]]
    assert "FROZEN" not in tickers


# --- Stage 1 -------------------------------------------------------------------------------------

@pytest.mark.parametrize(
    "overrides",
    [
        {"ema_20_above_50": False},
        {"rsi_14": 40.0},
        {"rsi_14": 80.0},
        {"volume_surge": 1.0},
        {"macd_hist": -0.5},
    ],
)
def test_stage1_respects_each_hurdle(overrides):
    portfolio, ohlcv = make_portfolio_db(), make_ohlcv_db()
    mark_features_success(portfolio)
    seed_qualifying_candidate(portfolio, ohlcv, "BASELINE")
    seed_qualifying_candidate(portfolio, ohlcv, "VIOLATOR", **overrides)

    result = run(as_of_date=AS_OF, agent_id="simons", clock=FakeClock(datetime(2026, 3, 2, 22, 0)),
                 portfolio_conn=portfolio, ohlcv_conn=ohlcv)
    tickers = [r["ticker"] for r in result["watchlist"]]
    assert "BASELINE" in tickers
    assert "VIOLATOR" not in tickers


# --- Sector cap ----------------------------------------------------------------------------------

def test_sector_cap_of_two():
    portfolio, ohlcv = make_portfolio_db(), make_ohlcv_db()
    mark_features_success(portfolio)
    # 4 candidates, same sector, decreasing intensity (via decreasing macd_hist -> lower score).
    for i, macd in enumerate([4.0, 3.0, 2.0, 1.0]):
        seed_qualifying_candidate(portfolio, ohlcv, f"SEC{i}", sector="Crowded", macd_hist=macd)

    result = run(as_of_date=AS_OF, agent_id="simons", clock=FakeClock(datetime(2026, 3, 2, 22, 0)),
                 portfolio_conn=portfolio, ohlcv_conn=ohlcv)
    crowded = [r for r in result["watchlist"] if r["sector"] == "Crowded"]
    assert len(crowded) == settings.SECTOR_CAP_PER_AGENT == 2
    assert {r["ticker"] for r in crowded} == {"SEC0", "SEC1"}  # the two highest-intensity


# --- TTL lock / expiry -----------------------------------------------------------------------------

def test_unexpired_row_survives_and_expired_row_is_replaced():
    portfolio, ohlcv = make_portfolio_db(), make_ohlcv_db()
    mark_features_success(portfolio)

    # LOCKED: pre-existing row, not expired, still passes Stage0, close > ema_200.
    seed_qualifying_candidate(portfolio, ohlcv, "LOCKED", sector="SectorA")
    portfolio.execute(
        "INSERT INTO agent_watchlist (agent_id, ticker, sector, added_on, ttl_days, expires_on, intensity_score) "
        "VALUES ('simons', 'LOCKED', 'SectorA', '2026-02-27', 3, '2026-03-04', 999.0)"
    )

    # EXPIRED: pre-existing row whose TTL has already lapsed as of AS_OF. It also no longer
    # passes Stage 1 today (macd_hist <= 0), so it cannot come back in as a fresh pick either --
    # isolating "removed because expired" from "happened to re-qualify on its own".
    seed_qualifying_candidate(portfolio, ohlcv, "EXPIRED", sector="SectorB", macd_hist=-1.0)
    portfolio.execute(
        "INSERT INTO agent_watchlist (agent_id, ticker, sector, added_on, ttl_days, expires_on, intensity_score) "
        "VALUES ('simons', 'EXPIRED', 'SectorB', '2026-02-25', 3, '2026-02-28', 888.0)"
    )

    # A fresh new candidate that should be able to take a free slot.
    seed_qualifying_candidate(portfolio, ohlcv, "FRESH", sector="SectorC")

    result = run(as_of_date=AS_OF, agent_id="simons", clock=FakeClock(datetime(2026, 3, 2, 22, 0)),
                 portfolio_conn=portfolio, ohlcv_conn=ohlcv)
    final_by_ticker = {r["ticker"]: r for r in result["watchlist"]}

    assert "LOCKED" in final_by_ticker
    assert final_by_ticker["LOCKED"]["intensity_score"] == pytest.approx(999.0)  # untouched by the lock

    row = portfolio.execute(
        "SELECT added_on FROM agent_watchlist WHERE agent_id='simons' AND ticker='LOCKED'"
    ).fetchone()
    assert row["added_on"] == "2026-02-27"  # not refreshed

    assert "EXPIRED" not in final_by_ticker
    assert "FRESH" in final_by_ticker


# --- Review pool -----------------------------------------------------------------------------------

def test_held_stock_that_left_the_watchlist_is_still_in_the_review_pool():
    portfolio = make_portfolio_db()
    portfolio.execute(
        "INSERT INTO agents (id, name, philosophy, kind, starting_cash_paise, cash_paise, created_at, updated_at) "
        "VALUES ('simons', 'Jim Simons', 'Quant', 'LLM', 10000000, 10000000, ?, ?)",
        (NOW, NOW),
    )
    portfolio.execute(
        "INSERT INTO positions (agent_id, ticker, sector, shares, avg_entry_price_paise, stop_paise, "
        "target_paise, last_price_paise, status, entry_date) "
        "VALUES ('simons', 'HELDGONE', 'SectorA', 10, 10000, 9000, 12000, 10500, 'OPEN', '2026-02-01')"
    )
    # HELDGONE is not in agent_watchlist at all (it left the watchlist already).
    portfolio.execute(
        "INSERT INTO agent_watchlist (agent_id, ticker, sector, added_on, ttl_days, expires_on, intensity_score) "
        "VALUES ('simons', 'OTHER', 'SectorB', '2026-03-01', 3, '2026-03-05', 5.0)"
    )

    pool = get_review_pool(portfolio, "simons", AS_OF)
    held = {p["ticker"]: p["is_held"] for p in pool}
    assert held.get("HELDGONE") is True
    assert held.get("OTHER") is False


def test_cap_never_drops_a_held_stock():
    portfolio = make_portfolio_db()
    portfolio.execute(
        "INSERT INTO agents (id, name, philosophy, kind, starting_cash_paise, cash_paise, created_at, updated_at) "
        "VALUES ('simons', 'Jim Simons', 'Quant', 'LLM', 10000000, 10000000, ?, ?)",
        (NOW, NOW),
    )
    # MAX_CANDIDATES_PER_RUN held positions (fills the whole cap on its own).
    for i in range(settings.MAX_CANDIDATES_PER_RUN):
        portfolio.execute(
            "INSERT INTO positions (agent_id, ticker, sector, shares, avg_entry_price_paise, stop_paise, "
            "target_paise, last_price_paise, status, entry_date) "
            "VALUES ('simons', ?, 'SectorA', 10, 10000, 9000, 12000, 10500, 'OPEN', '2026-02-01')",
            (f"HELD{i}",),
        )
    # Plenty of watchlist names competing for the (now zero) remaining slots.
    for i in range(10):
        portfolio.execute(
            "INSERT INTO agent_watchlist (agent_id, ticker, sector, added_on, ttl_days, expires_on, intensity_score) "
            "VALUES ('simons', ?, 'SectorB', '2026-03-01', 3, '2026-03-05', ?)",
            (f"WL{i}", float(i)),
        )

    pool = get_review_pool(portfolio, "simons", AS_OF)
    held_in_pool = [p for p in pool if p["is_held"]]
    assert len(held_in_pool) == settings.MAX_CANDIDATES_PER_RUN
    assert {p["ticker"] for p in held_in_pool} == {f"HELD{i}" for i in range(settings.MAX_CANDIDATES_PER_RUN)}


# --- Empty funnel ------------------------------------------------------------------------------------

def test_empty_funnel_writes_empty_watchlist_and_funnel_counts_row():
    portfolio, ohlcv = make_portfolio_db(), make_ohlcv_db()
    mark_features_success(portfolio)
    # No symbols at all -> nothing can survive Stage 0.

    result = run(as_of_date=AS_OF, agent_id="simons", clock=FakeClock(datetime(2026, 3, 2, 22, 0)),
                 portfolio_conn=portfolio, ohlcv_conn=ohlcv)

    assert result["status"] == "SUCCESS"
    assert result["counts"] == {"stage0": 0, "stage1": 0, "final": 0}
    assert result["watchlist"] == []

    log_row = portfolio.execute(
        "SELECT * FROM activity_log WHERE agent_id='simons' AND event_type='FUNNEL_COUNTS'"
    ).fetchone()
    assert log_row is not None
    assert json.loads(log_row["metadata_json"]) == {"stage0": 0, "stage1": 0, "final": 0}
