"""
Unit tests for precompute/watchlist_refresh.py: Stage 0 liquidity/circuit gates, Stage 1
persona hurdles, the sector cap, TTL lock/expiry, and the review pool — all against in-memory
databases and fake FeatureSnapshots (no live network, no real OHLCV fetch).
See Plan_v3 §6.
"""

import json
import sqlite3
from datetime import date, datetime, timedelta

import pytest

from core.clock import FakeClock
from core.config import settings
from ingestion.sync_ohlcv import ensure_schema as ensure_ohlcv_schema
from tests.conftest import (
    make_passing_simons_features,
    make_portfolio_db,
)
from watchlist.watchlist_refresh import (
    compute_sector_percentiles,
    get_review_pool,
    run,
    stage1_filter,
)

AS_OF = "2026-03-02"
NOW = "2026-03-02T22:00:00+05:30"


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


def insert_ohlcv(
    ohlcv_conn, ticker, as_of=AS_OF, n_days=20, volume=600_000, close=100.0, boost_last_n=0, boost_volume=None
):
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
    ohlcv_conn.execute("INSERT INTO ticker_status (ticker, status, updated_at) VALUES (?, ?, ?)", (ticker, status, NOW))


def insert_snapshot(portfolio_conn, ticker, features, as_of=AS_OF):
    portfolio_conn.execute(
        "INSERT INTO feature_snapshots (ticker, as_of_date, schema_version, features_json, created_at) "
        "VALUES (?, ?, 1, ?, ?)",
        (ticker, as_of, json.dumps(features), NOW),
    )


def passing_simons_features(**overrides):
    return make_passing_simons_features(**overrides)


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
    portfolio, ohlcv = make_portfolio_db(foreign_keys=False), make_ohlcv_db()
    mark_features_success(portfolio)
    seed_qualifying_candidate(portfolio, ohlcv, "GOODVOL")

    insert_symbol(portfolio, "LOWVOL")
    insert_ohlcv(ohlcv, "LOWVOL", volume=10_000, close=100.0)  # turnover = 1,000,000 << 5 crore
    set_status(ohlcv, "LOWVOL", "OK")
    insert_snapshot(portfolio, "LOWVOL", passing_simons_features())

    result = run(
        as_of_date=AS_OF,
        agent_id="simons",
        clock=FakeClock(datetime(2026, 3, 2, 22, 0)),
        portfolio_conn=portfolio,
        ohlcv_conn=ohlcv,
    )
    tickers = [r["ticker"] for r in result["watchlist"]]
    assert "GOODVOL" in tickers
    assert "LOWVOL" not in tickers


def test_stage0_excludes_locked_circuit_stock():
    portfolio, ohlcv = make_portfolio_db(foreign_keys=False), make_ohlcv_db()
    mark_features_success(portfolio)
    seed_qualifying_candidate(portfolio, ohlcv, "GOODVOL")

    insert_symbol(portfolio, "FROZEN")
    insert_ohlcv(ohlcv, "FROZEN", volume=600_000, close=100.0, boost_last_n=5, boost_volume=900_000)
    set_status(ohlcv, "FROZEN", "LOCKED_CIRCUIT")
    insert_snapshot(portfolio, "FROZEN", passing_simons_features())

    result = run(
        as_of_date=AS_OF,
        agent_id="simons",
        clock=FakeClock(datetime(2026, 3, 2, 22, 0)),
        portfolio_conn=portfolio,
        ohlcv_conn=ohlcv,
    )
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
    portfolio, ohlcv = make_portfolio_db(foreign_keys=False), make_ohlcv_db()
    mark_features_success(portfolio)
    seed_qualifying_candidate(portfolio, ohlcv, "BASELINE")
    seed_qualifying_candidate(portfolio, ohlcv, "VIOLATOR", **overrides)

    result = run(
        as_of_date=AS_OF,
        agent_id="simons",
        clock=FakeClock(datetime(2026, 3, 2, 22, 0)),
        portfolio_conn=portfolio,
        ohlcv_conn=ohlcv,
    )
    tickers = [r["ticker"] for r in result["watchlist"]]
    assert "BASELINE" in tickers
    assert "VIOLATOR" not in tickers


# --- Sector cap ----------------------------------------------------------------------------------


def test_sector_cap_enforcement():
    portfolio, ohlcv = make_portfolio_db(foreign_keys=False), make_ohlcv_db()
    mark_features_success(portfolio)
    # 5 candidates, same sector, decreasing intensity (via decreasing macd_hist -> lower score).
    for i, macd in enumerate([5.0, 4.0, 3.0, 2.0, 1.0]):
        seed_qualifying_candidate(portfolio, ohlcv, f"SEC{i}", sector="Crowded", macd_hist=macd)

    # Simons has persona-level sector_cap = 3 configured in PersonaConfig
    result = run(
        as_of_date=AS_OF,
        agent_id="simons",
        clock=FakeClock(datetime(2026, 3, 2, 22, 0)),
        portfolio_conn=portfolio,
        ohlcv_conn=ohlcv,
    )
    crowded = [r for r in result["watchlist"] if r["sector"] == "Crowded"]
    assert len(crowded) == 3
    assert {r["ticker"] for r in crowded} == {"SEC0", "SEC1", "SEC2"}  # the three highest-intensity


# --- TTL lock / expiry -----------------------------------------------------------------------------


def test_unexpired_row_survives_and_expired_row_is_replaced():
    portfolio, ohlcv = make_portfolio_db(foreign_keys=False), make_ohlcv_db()
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

    result = run(
        as_of_date=AS_OF,
        agent_id="simons",
        clock=FakeClock(datetime(2026, 3, 2, 22, 0)),
        portfolio_conn=portfolio,
        ohlcv_conn=ohlcv,
    )
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
    portfolio = make_portfolio_db(foreign_keys=False)
    portfolio.execute(
        "INSERT INTO agents (id, name, philosophy, kind, starting_cash_paise, cash_paise, created_at, updated_at) "
        "VALUES ('simons', 'Jim Simons', 'Quant', 'LLM', 50000000, 50000000, ?, ?)",
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
    portfolio = make_portfolio_db(foreign_keys=False)
    portfolio.execute(
        "INSERT INTO agents (id, name, philosophy, kind, starting_cash_paise, cash_paise, created_at, updated_at) "
        "VALUES ('simons', 'Jim Simons', 'Quant', 'LLM', 50000000, 50000000, ?, ?)",
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
    portfolio, ohlcv = make_portfolio_db(foreign_keys=False), make_ohlcv_db()
    mark_features_success(portfolio)
    # No symbols at all -> nothing can survive Stage 0.

    result = run(
        as_of_date=AS_OF,
        agent_id="simons",
        clock=FakeClock(datetime(2026, 3, 2, 22, 0)),
        portfolio_conn=portfolio,
        ohlcv_conn=ohlcv,
    )

    assert result["status"] == "SUCCESS"
    assert result["counts"] == {"stage0": 0, "stage1": 0, "final": 0}
    assert result["watchlist"] == []

    log_row = portfolio.execute(
        "SELECT * FROM activity_log WHERE agent_id='simons' AND event_type='FUNNEL_COUNTS'"
    ).fetchone()
    assert log_row is not None
    assert json.loads(log_row["metadata_json"]) == {"stage0": 0, "stage1": 0, "final": 0}


# --- Sector percentiles -------------------------------------------------------------------------------


def test_compute_sector_percentiles_large_cohort_vs_small_cohort():
    # Large cohort (size 10 >= 8): within-sector percentiles
    sectors = {f"T_LRG_{i}": "SectorLarge" for i in range(10)}
    scores = {f"T_LRG_{i}": float(i * 10) for i in range(10)}  # 0, 10, 20, ..., 90

    # Small cohort (size 3 < 8): falls back to whole universe
    sectors.update({"T_SML_1": "SectorSmall", "T_SML_2": "SectorSmall", "T_SML_3": "SectorSmall"})
    scores.update({"T_SML_1": 15.0, "T_SML_2": 45.0, "T_SML_3": 85.0})

    percentiles = compute_sector_percentiles(scores, sectors, min_cohort=8)

    # In SectorLarge, T_LRG_9 has highest score (90) -> 100.0%
    assert percentiles["T_LRG_9"] == 100.0
    # T_LRG_0 has score 0 (1/10) -> 10.0%
    assert percentiles["T_LRG_0"] == 10.0
    # T_LRG_4 has score 40 (5/10) -> 50.0%
    assert percentiles["T_LRG_4"] == 50.0

    # Small cohort fell back to universe (13 total items: 0, 10, 15, 20, 30, 40, 45, 50, 60, 70, 80, 85, 90)
    # T_SML_3 (score 85) is <= 85 -> 12 items out of 13 -> 12/13 * 100 = 92.3%
    assert percentiles["T_SML_3"] == pytest.approx(12 / 13 * 100.0, rel=1e-3)


def test_stage1_filter_respects_sector_percentile_min():
    from agents.personas import get_persona

    persona = get_persona("simons")

    stage0 = ["T1", "T2"]
    # Both satisfy Simons technical hurdles
    features = {
        "T1": {
            "ema_20_above_50": True,
            "rsi_14": 60.0,
            "volume_surge": 1.5,
            "macd_hist": 2.0,
            "adx_14": 25.0,
            "kaufman_er_20": 0.50,
        },
        "T2": {
            "ema_20_above_50": True,
            "rsi_14": 60.0,
            "volume_surge": 1.5,
            "macd_hist": 2.0,
            "adx_14": 25.0,
            "kaufman_er_20": 0.50,
        },
    }
    percentiles = {"T1": 80.0, "T2": 40.0}

    orig = settings.SECTOR_PERCENTILE_MIN
    try:
        # When SECTOR_PERCENTILE_MIN = 0 (default off), both pass
        object.__setattr__(settings, "SECTOR_PERCENTILE_MIN", 0.0)
        survivors = stage1_filter(stage0, features, persona, sector_percentiles=percentiles)
        assert survivors == ["T1", "T2"]

        # When SECTOR_PERCENTILE_MIN = 50.0, T2 (40%) is filtered out
        object.__setattr__(settings, "SECTOR_PERCENTILE_MIN", 50.0)
        survivors = stage1_filter(stage0, features, persona, sector_percentiles=percentiles)
        assert survivors == ["T1"]
    finally:
        object.__setattr__(settings, "SECTOR_PERCENTILE_MIN", orig)


def test_stage2_sort_lynch_multi_factor_percentile():
    from agents.personas import get_persona
    from watchlist.watchlist_refresh import stage2_sort

    persona = get_persona("lynch")

    stage1 = ["STOCK_A", "STOCK_B", "STOCK_C"]
    features = {
        "STOCK_A": {"peg": 0.4, "roce_pct": 28.0, "cfo_to_pat": 1.2, "pat_growth_yoy_pct": 20.0},
        "STOCK_B": {"peg": 0.8, "roce_pct": 20.0, "cfo_to_pat": 0.9, "pat_growth_yoy_pct": 10.0},
        "STOCK_C": {"peg": 0.95, "roce_pct": 16.0, "cfo_to_pat": 0.85, "pat_growth_yoy_pct": 9.0},
    }
    sectors = {"STOCK_A": "Auto", "STOCK_B": "IT", "STOCK_C": "FMCG"}
    sorted_candidates = stage2_sort(stage1, features, sectors, persona)

    assert sorted_candidates[0]["ticker"] == "STOCK_A"
    assert sorted_candidates[1]["ticker"] == "STOCK_B"
    assert sorted_candidates[2]["ticker"] == "STOCK_C"
    assert 0.0 <= sorted_candidates[0]["intensity_score"] <= 1.0
    assert sorted_candidates[0]["intensity_score"] > sorted_candidates[1]["intensity_score"]


def test_stage2_sort_marks_multi_factor_percentile():
    from agents.personas import get_persona
    from watchlist.watchlist_refresh import stage2_sort

    persona = get_persona("marks")

    stage1 = ["STOCK_A", "STOCK_B", "STOCK_C"]
    features = {
        "STOCK_A": {
            "rsi_14": 22.0,
            "dist_52w_low_pct": 3.0,
            "roce_pct": 25.0,
            "cfo_to_pat": 1.3,
            "debt_to_equity": 0.2,
            "regime": "PANIC",
        },
        "STOCK_B": {
            "rsi_14": 30.0,
            "dist_52w_low_pct": 12.0,
            "roce_pct": 15.0,
            "cfo_to_pat": 0.9,
            "debt_to_equity": 0.5,
            "regime": "NORMAL",
        },
        "STOCK_C": {
            "rsi_14": 34.0,
            "dist_52w_low_pct": 19.0,
            "roce_pct": 11.0,
            "cfo_to_pat": 0.6,
            "debt_to_equity": 0.8,
            "regime": "NORMAL",
        },
    }
    sectors = {"STOCK_A": "Metals", "STOCK_B": "Infra", "STOCK_C": "Textiles"}
    sorted_candidates = stage2_sort(stage1, features, sectors, persona)

    assert sorted_candidates[0]["ticker"] == "STOCK_A"
    assert sorted_candidates[1]["ticker"] == "STOCK_B"
    assert sorted_candidates[2]["ticker"] == "STOCK_C"
    assert 0.0 <= sorted_candidates[0]["intensity_score"] <= 1.0
    assert sorted_candidates[0]["intensity_score"] > sorted_candidates[1]["intensity_score"]


def test_stage2_sort_rj_multi_factor_percentile():
    from agents.personas import get_persona
    from watchlist.watchlist_refresh import stage2_sort

    persona = get_persona("jhunjhunwala")

    stage1 = ["STOCK_A", "STOCK_B", "STOCK_C"]
    features = {
        "STOCK_A": {
            "pat_growth_yoy_pct": 35.0,
            "fii_dii_qoq_delta_pct": 2.5,
            "volume_surge": 2.2,
            "roce_pct": 28.0,
            "promoter_holding_pct": 55.0,
        },
        "STOCK_B": {
            "pat_growth_yoy_pct": 20.0,
            "fii_dii_qoq_delta_pct": 0.0,
            "volume_surge": 1.4,
            "roce_pct": 20.0,
            "promoter_holding_pct": 45.0,
        },
        "STOCK_C": {
            "pat_growth_yoy_pct": 12.0,
            "fii_dii_qoq_delta_pct": -1.0,
            "volume_surge": 1.2,
            "roce_pct": 16.0,
            "promoter_holding_pct": 41.0,
        },
    }
    sectors = {"STOCK_A": "Auto", "STOCK_B": "CapGoods", "STOCK_C": "Consumer"}
    sorted_candidates = stage2_sort(stage1, features, sectors, persona)

    assert sorted_candidates[0]["ticker"] == "STOCK_A"
    assert sorted_candidates[1]["ticker"] == "STOCK_B"
    assert sorted_candidates[2]["ticker"] == "STOCK_C"
    assert 0.0 <= sorted_candidates[0]["intensity_score"] <= 1.0
    assert sorted_candidates[0]["intensity_score"] > sorted_candidates[1]["intensity_score"]


def test_stage2_sort_varsity_multi_factor_percentile():
    from agents.personas import get_persona
    from watchlist.watchlist_refresh import stage2_sort

    persona = get_persona("varsity")

    stage1 = ["STOCK_A", "STOCK_B", "STOCK_C"]
    features = {
        "STOCK_A": {
            "volume_surge": 2.0,
            "rsi_14": 60.0,
            "roce_pct": 25.0,
            "debt_to_equity": 0.3,
            "news_sentiment": 0.5,
        },
        "STOCK_B": {
            "volume_surge": 1.3,
            "rsi_14": 55.0,
            "roce_pct": 18.0,
            "debt_to_equity": 0.8,
            "news_sentiment": 0.0,
        },
        "STOCK_C": {
            "volume_surge": 1.0,
            "rsi_14": 48.0,
            "roce_pct": 13.0,
            "debt_to_equity": 1.4,
            "news_sentiment": 0.0,
        },
    }
    sectors = {"STOCK_A": "IT", "STOCK_B": "Pharma", "STOCK_C": "Energy"}
    sorted_candidates = stage2_sort(stage1, features, sectors, persona)

    assert sorted_candidates[0]["ticker"] == "STOCK_A"
    assert sorted_candidates[1]["ticker"] == "STOCK_B"
    assert sorted_candidates[2]["ticker"] == "STOCK_C"
    assert 0.0 <= sorted_candidates[0]["intensity_score"] <= 1.0
    assert sorted_candidates[0]["intensity_score"] > sorted_candidates[1]["intensity_score"]


def test_stage3_retains_marks_candidate_below_ema200():
    from agents.personas import get_persona
    from watchlist.watchlist_refresh import stage3_update_watchlist

    portfolio = make_portfolio_db(foreign_keys=False)
    marks_persona = get_persona("marks")

    # Insert locked Marks row with unexpired TTL
    portfolio.execute(
        "INSERT INTO agent_watchlist (agent_id, ticker, sector, added_on, ttl_days, expires_on, intensity_score) "
        "VALUES ('marks', 'MARKS_OVERSOLD', 'Metals', '2026-03-01', 7, '2026-03-08', 0.85)"
    )

    stage0_tickers = ["MARKS_OVERSOLD"]
    # Candle is trading well below 200 EMA (close 80 < ema_200 100), typical for 52-week low distress
    features_by_ticker = {"MARKS_OVERSOLD": {"close": 80.0, "ema_200": 100.0, "rsi_14": 28.0, "dist_52w_low_pct": 5.0}}

    res = stage3_update_watchlist(
        portfolio_conn=portfolio,
        persona=marks_persona,
        as_of_date=AS_OF,
        stage0_tickers=stage0_tickers,
        ranked_candidates=[],
        features_by_ticker=features_by_ticker,
        clock=FakeClock(datetime(2026, 3, 2, 22, 0)),
    )

    # Marks has require_above_ema200=False, so the candidate must NOT be purged
    final_tickers = [r["ticker"] for r in res["final"]]
    assert "MARKS_OVERSOLD" in final_tickers
    remaining = portfolio.execute("SELECT ticker FROM agent_watchlist WHERE agent_id = 'marks'").fetchall()
    assert [r["ticker"] for r in remaining] == ["MARKS_OVERSOLD"]


def test_stage3_purges_simons_candidate_below_ema200():
    from agents.personas import get_persona
    from watchlist.watchlist_refresh import stage3_update_watchlist

    portfolio = make_portfolio_db(foreign_keys=False)
    simons_persona = get_persona("simons")

    # Insert locked Simons row with unexpired TTL
    portfolio.execute(
        "INSERT INTO agent_watchlist (agent_id, ticker, sector, added_on, ttl_days, expires_on, intensity_score) "
        "VALUES ('simons', 'BROKEN_TREND', 'Auto', '2026-03-01', 3, '2026-03-04', 0.90)"
    )

    stage0_tickers = ["BROKEN_TREND"]
    # Candle is below 200 EMA (structural breakdown for momentum)
    features_by_ticker = {"BROKEN_TREND": {"close": 80.0, "ema_200": 100.0}}

    res = stage3_update_watchlist(
        portfolio_conn=portfolio,
        persona=simons_persona,
        as_of_date=AS_OF,
        stage0_tickers=stage0_tickers,
        ranked_candidates=[],
        features_by_ticker=features_by_ticker,
        clock=FakeClock(datetime(2026, 3, 2, 22, 0)),
    )

    # Simons has require_above_ema200=True, so the broken trend must be purged
    final_tickers = [r["ticker"] for r in res["final"]]
    assert "BROKEN_TREND" not in final_tickers
    remaining = portfolio.execute("SELECT ticker FROM agent_watchlist WHERE agent_id = 'simons'").fetchall()
    assert remaining == []
