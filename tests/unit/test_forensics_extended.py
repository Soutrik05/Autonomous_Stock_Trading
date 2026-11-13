"""
Tests for the additive forensics extensions (extra numbers, secondary tags, post-exit
enrichment) added on top of learning/forensics.py's existing classification engine. Reuses the
exact in-memory fixtures/helpers from tests/unit/test_forensics.py -- see that file for the
_db_container monkeypatch that makes forensics.run() (and here, also enrich_post_exit()) use
in-memory ohlcv/macro connections.
See Plan_v3 section 5.2.
"""

import json

import learning.forensics as forensics
from learning.forensics import SECONDARY_TAGS
from learning.prompts import build_reflection_system_prompt, build_reflection_user_prompt
from tests.unit.test_forensics import (  # noqa: F401 -- reused as pytest fixtures
    _add_macro,
    _add_ohlcv,
    _add_snapshot,
    _db_container,
    _insert_position,
    clock,
    macro_conn,
    ohlcv_conn,
    pconn,
)


def _add_varied_ohlcv(conn, ticker: str, rows: list) -> None:
    """Inserts distinct per-day candles, unlike test_forensics.py's _add_ohlcv (one repeated
    candle). Each row is {"date", "open", "high", "low", "close", "volume"}."""
    for r in rows:
        conn.execute(
            "INSERT OR REPLACE INTO ohlcv (ticker, trade_date, open, high, low, close, volume) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (ticker, r["date"], r["open"], r["high"], r["low"], r["close"], r.get("volume", 100_000)),
        )


# --- 1: the new numbers, computed correctly ------------------------------------------------------


def test_new_numbers_computed_correctly_for_a_known_price_series(pconn, ohlcv_conn, macro_conn, clock):
    ticker = "RELIANCE"
    # 10 pre-entry sessions, close rising 80 -> 98 (2 per day), entry day close = 100.
    pre_entry = [
        {
            "date": f"2025-01-{22 + i:02d}",
            "open": 78 + 2 * i,
            "high": 79 + 2 * i,
            "low": 77 + 2 * i,
            "close": 80 + 2 * i,
        }
        for i in range(10)
    ]
    hold_window = [
        {"date": "2025-02-01", "open": 100, "high": 101, "low": 99, "close": 100},  # entry day
        {"date": "2025-02-02", "open": 100, "high": 103, "low": 98, "close": 102},
        {"date": "2025-02-03", "open": 95, "high": 96, "low": 93, "close": 94},  # gap down from 102
        {"date": "2025-02-04", "open": 94, "high": 108, "low": 93, "close": 107},  # mfe peak (high=108)
        {"date": "2025-02-05", "open": 107, "high": 109, "low": 105, "close": 106},  # exit day
    ]
    _add_varied_ohlcv(ohlcv_conn, ticker, pre_entry + hold_window)
    _add_macro(macro_conn, "2025-02-01", 5, vix=15.0, regime="NORMAL")

    pid = _insert_position(
        pconn,
        ticker=ticker,
        entry_price_paise=100_00,
        pnl_pct=6.0,
        hold_days=4,
        exit_reason="AGENT_SELL",
        entry_date="2025-02-01",
        exit_date="2025-02-05",
    )
    r = forensics.run(pconn, pid, clock)
    diag = json.loads(r.diagnosis_json)

    assert diag["mae_pct"] == -7.0  # lowest low 93 vs entry 100
    assert diag["mfe_pct"] == 9.0  # highest high 109 (exit day) vs entry 100
    assert diag["profit_given_back_pct"] == 3.0  # mfe 9.0 - realized_pnl_pct 6.0
    assert diag["run_up_before_entry_pct"] == 25.0  # (100-80)/80*100
    assert diag["largest_gap_down_pct"] == -6.8627  # (95-102)/102*100, rounded


# --- 2: missing/short data gives None, never crashes --------------------------------------------


def test_missing_or_too_short_data_gives_none_without_crashing():
    assert forensics._compute_mae_pct([], 100.0) is None
    assert forensics._compute_mfe_pct([], 100.0) is None
    assert forensics._compute_profit_given_back_pct(None, 5.0) is None
    assert forensics._compute_largest_gap_down_pct([{"open": 100, "close": 100}]) is None  # only 1 row


def test_run_up_returns_none_with_insufficient_history(pconn, ohlcv_conn, macro_conn, clock):
    # Only 3 days of history before entry -- fewer than LATE_ENTRY_LOOKBACK_SESSIONS(10) + 1.
    _add_ohlcv(ohlcv_conn, "RELIANCE", "2025-01-29", 3, close=98.0)
    _add_ohlcv(ohlcv_conn, "RELIANCE", "2025-02-01", 5, close=100.0)
    _add_macro(macro_conn, "2025-02-01", 5, vix=15.0, regime="NORMAL")
    pid = _insert_position(pconn, pnl_pct=-1.0, hold_days=3, entry_date="2025-02-01", exit_date="2025-02-05")
    r = forensics.run(pconn, pid, clock)
    diag = json.loads(r.diagnosis_json)
    assert diag["run_up_before_entry_pct"] is None


# --- 3: each secondary tag fires at/above threshold, not just below -----------------------------


def _base_diag(**overrides) -> dict:
    diag = {
        "broad_drag_ratio": 0.0,
        "run_up_before_entry_pct": None,
        "largest_gap_down_pct": None,
        "mae_pct": None,
        "mfe_pct": None,
        "profit_given_back_pct": None,
        "realized_pnl_pct": 0.0,
    }
    diag.update(overrides)
    return diag


def test_weak_market_tag_fires_at_threshold_and_not_below():
    fires = forensics._compute_secondary_tags(_base_diag(broad_drag_ratio=0.5), "UNCLASSIFIED")
    not_fires = forensics._compute_secondary_tags(_base_diag(broad_drag_ratio=0.49), "UNCLASSIFIED")
    assert "WEAK_MARKET" in fires
    assert "WEAK_MARKET" not in not_fires


def test_late_entry_tag_fires_at_threshold_and_not_below():
    fires = forensics._compute_secondary_tags(_base_diag(run_up_before_entry_pct=12.0), "UNCLASSIFIED")
    not_fires = forensics._compute_secondary_tags(_base_diag(run_up_before_entry_pct=11.9), "UNCLASSIFIED")
    assert "LATE_ENTRY" in fires
    assert "LATE_ENTRY" not in not_fires


def test_gap_down_tag_fires_at_threshold_and_not_below():
    fires = forensics._compute_secondary_tags(_base_diag(largest_gap_down_pct=-3.0), "UNCLASSIFIED")
    not_fires = forensics._compute_secondary_tags(_base_diag(largest_gap_down_pct=-2.9), "UNCLASSIFIED")
    assert "GAP_DOWN" in fires
    assert "GAP_DOWN" not in not_fires


def test_deep_drawdown_then_recovered_tag_fires_and_not_below():
    fires = forensics._compute_secondary_tags(
        _base_diag(mae_pct=-8.0, realized_pnl_pct=5.0),
        "UNCLASSIFIED",
    )
    not_fires_shallow = forensics._compute_secondary_tags(
        _base_diag(mae_pct=-7.9, realized_pnl_pct=5.0),
        "UNCLASSIFIED",
    )
    not_fires_no_recovery = forensics._compute_secondary_tags(
        _base_diag(mae_pct=-10.0, realized_pnl_pct=-6.0),
        "UNCLASSIFIED",
    )
    assert "DEEP_DRAWDOWN_THEN_RECOVERED" in fires
    assert "DEEP_DRAWDOWN_THEN_RECOVERED" not in not_fires_shallow
    assert "DEEP_DRAWDOWN_THEN_RECOVERED" not in not_fires_no_recovery


def test_gave_back_profit_tag_fires_and_not_below():
    fires = forensics._compute_secondary_tags(
        _base_diag(mfe_pct=5.0, profit_given_back_pct=4.0),
        "UNCLASSIFIED",
    )
    not_fires = forensics._compute_secondary_tags(
        _base_diag(mfe_pct=5.0, profit_given_back_pct=3.9),
        "UNCLASSIFIED",
    )
    assert "GAVE_BACK_PROFIT" in fires
    assert "GAVE_BACK_PROFIT" not in not_fires


# --- 4: several tags at once, sorted, primary label excluded -------------------------------------


def test_several_tags_can_coexist_sorted_and_exclude_the_primary_label():
    diag = _base_diag(
        broad_drag_ratio=0.9,
        run_up_before_entry_pct=20.0,
        largest_gap_down_pct=-5.0,
        mae_pct=-10.0,
        realized_pnl_pct=5.0,
    )
    tags = forensics._compute_secondary_tags(diag, "WEAK_MARKET")  # primary == one of the tags
    assert tags == sorted(tags)
    assert "WEAK_MARKET" not in tags  # excluded even though its condition is met
    assert {"LATE_ENTRY", "GAP_DOWN", "DEEP_DRAWDOWN_THEN_RECOVERED"}.issubset(set(tags))


# --- 5: primary label is unchanged from before this change ---------------------------------------


def test_primary_labels_unchanged_corp_action_and_earnings_shock(pconn, ohlcv_conn, macro_conn, clock):
    pid = _insert_position(pconn, exit_reason="CORP_ACTION_CLOSE", pnl_pct=-5.0, hold_days=2)
    _add_ohlcv(ohlcv_conn, "RELIANCE", "2025-01-01", 8)
    _add_macro(macro_conn, "2025-01-01", 8)
    r = forensics.run(pconn, pid, clock)
    assert r.forensics_type == "CORP_ACTION_ARTIFACT"

    pid2 = _insert_position(pconn, pnl_pct=-8.0, hold_days=2, entry_date="2025-01-10", exit_date="2025-01-18")
    _add_ohlcv(ohlcv_conn, "RELIANCE", "2025-01-10", 1, open_=100.0, close=90.0)
    _add_ohlcv(ohlcv_conn, "RELIANCE", "2025-01-11", 7, open_=90.0, close=89.0)
    _add_macro(macro_conn, "2025-01-10", 9, vix=15.0, regime="NORMAL")
    r2 = forensics.run(pconn, pid2, clock)
    assert r2.forensics_type == "EARNINGS_SHOCK"


def test_primary_labels_unchanged_win_classes(pconn, ohlcv_conn, macro_conn, clock):
    pid = _insert_position(pconn, pnl_pct=8.0, hold_days=5, exit_reason="AGENT_SELL")
    _add_ohlcv(ohlcv_conn, "RELIANCE", "2025-01-01", 1, open_=100.0, close=106.0)
    _add_ohlcv(ohlcv_conn, "RELIANCE", "2025-01-02", 7, open_=106.0, close=108.0)
    _add_macro(macro_conn, "2025-01-01", 8, vix=14.0, regime="NORMAL")
    r = forensics.run(pconn, pid, clock)
    assert r.forensics_type == "EARNINGS_MOMENTUM"


# --- 6: enrich_post_exit --------------------------------------------------------------------------


def test_enrich_post_exit_does_nothing_before_5_sessions_have_passed(pconn, ohlcv_conn, macro_conn, clock):
    pid = _insert_position(
        pconn, pnl_pct=2.0, hold_days=5, exit_reason="AGENT_SELL", entry_date="2025-01-01", exit_date="2025-01-08"
    )
    _add_ohlcv(ohlcv_conn, "RELIANCE", "2025-01-01", 8, close=100.0)
    _add_macro(macro_conn, "2025-01-01", 8, vix=14.0, regime="NORMAL")
    forensics.run(pconn, pid, clock)
    # Only 2 trading sessions exist after exit_date so far.
    _add_ohlcv(ohlcv_conn, "RELIANCE", "2025-01-09", 2, close=101.0)

    updated = forensics.enrich_post_exit(pconn, clock, as_of_date="2025-01-11", ohlcv_conn=ohlcv_conn)

    assert updated == 0
    diag = json.loads(pconn.execute("SELECT diagnosis_json FROM positions WHERE id=?", (pid,)).fetchone()[0])
    assert "post_exit" not in diag


def test_enrich_post_exit_writes_5d_then_adds_20d_later_without_losing_keys(pconn, ohlcv_conn, macro_conn, clock):
    pid = _insert_position(
        pconn, pnl_pct=2.0, hold_days=5, exit_reason="AGENT_SELL", entry_date="2025-01-01", exit_date="2025-01-08"
    )
    _add_ohlcv(ohlcv_conn, "RELIANCE", "2025-01-01", 8, close=100.0)
    _add_macro(macro_conn, "2025-01-01", 8, vix=14.0, regime="NORMAL")
    forensics.run(pconn, pid, clock)

    # 5 trading sessions after exit (01-09 .. 01-13), final close 110 -> +10%.
    _add_ohlcv(ohlcv_conn, "RELIANCE", "2025-01-09", 5, close=110.0)
    updated = forensics.enrich_post_exit(pconn, clock, as_of_date="2025-01-13", ohlcv_conn=ohlcv_conn)
    assert updated == 1

    diag = json.loads(pconn.execute("SELECT diagnosis_json FROM positions WHERE id=?", (pid,)).fetchone()[0])
    assert diag["post_exit"]["post_exit_ret_5d_pct"] == 10.0
    assert "post_exit_ret_20d_pct" not in diag["post_exit"]
    assert diag["forensics_type"]  # original key preserved
    assert diag["mae_pct"] is not None  # Part A key preserved

    # Running again the same day changes nothing (idempotent).
    updated_again = forensics.enrich_post_exit(pconn, clock, as_of_date="2025-01-13", ohlcv_conn=ohlcv_conn)
    assert updated_again == 0

    # 15 more sessions pass (20 total after exit), final close still 110.
    _add_ohlcv(ohlcv_conn, "RELIANCE", "2025-01-14", 15, close=110.0)
    updated_20d = forensics.enrich_post_exit(pconn, clock, as_of_date="2025-02-02", ohlcv_conn=ohlcv_conn)
    assert updated_20d == 1

    diag2 = json.loads(pconn.execute("SELECT diagnosis_json FROM positions WHERE id=?", (pid,)).fetchone()[0])
    assert diag2["post_exit"]["post_exit_ret_5d_pct"] == 10.0  # kept from before
    assert diag2["post_exit"]["post_exit_ret_20d_pct"] == 10.0  # newly added

    # Fully enriched now -- a third run changes nothing.
    assert forensics.enrich_post_exit(pconn, clock, as_of_date="2025-02-05", ohlcv_conn=ohlcv_conn) == 0


# --- 7: post-exit tags -----------------------------------------------------------------------------


def test_exited_too_early_fires_when_the_stock_keeps_running():
    diag = {"forensics_type": "TREND_CONTINUATION", "realized_pnl_pct": 3.0, "secondary_tags": []}
    post_exit = {"post_exit_ret_20d_pct": 8.0}
    tags = forensics._apply_post_exit_tags(diag, post_exit, "AGENT_SELL", 100.0, [])
    assert "EXITED_TOO_EARLY" in tags


def test_good_exit_fires_when_the_stock_keeps_falling():
    diag = {"forensics_type": "UNCLASSIFIED", "realized_pnl_pct": -2.0, "secondary_tags": []}
    post_exit = {"post_exit_ret_5d_pct": -4.0}
    tags = forensics._apply_post_exit_tags(diag, post_exit, "AGENT_SELL", 100.0, [])
    assert "GOOD_EXIT" in tags


def test_stop_too_tight_fires_when_price_recovers_above_entry_within_5_sessions():
    diag = {"forensics_type": "UNCLASSIFIED", "realized_pnl_pct": -3.0, "secondary_tags": []}
    post_exit = {"post_exit_ret_5d_pct": 2.0}
    forward_rows = [
        {"close": 98.0},
        {"close": 99.0},
        {"close": 101.5},
        {"close": 100.5},
        {"close": 100.0},
    ]
    tags = forensics._apply_post_exit_tags(diag, post_exit, forensics.STOP_HIT_EXIT_REASON, 100.0, forward_rows)
    assert "STOP_TOO_TIGHT" in tags


# --- 8: the reflection prompt now contains numbers, tags and the persona description -------------


def test_reflection_prompt_contains_numbers_tags_and_persona_description():
    from agents.personas import get_persona
    from features.contracts import persona_allowed_metric_names
    from learning.forensics import LOSS_LABELS, WIN_LABELS

    persona = get_persona("simons")
    allowed_metrics = persona_allowed_metric_names(persona.technical_hurdles, persona.fundamental_hurdles)
    system_prompt = build_reflection_system_prompt(
        persona.name,
        persona.system_prompt,
        allowed_metrics,
        LOSS_LABELS,
        WIN_LABELS,
        SECONDARY_TAGS,
        3,
    )
    # The persona's full philosophy paragraph (not just a one-line summary) is present.
    assert persona.system_prompt.split("HOLDING HORIZON:")[0].strip()[:40] in system_prompt
    assert "Do not turn this agent" in system_prompt
    assert "different kind of investor" in system_prompt
    for tag in SECONDARY_TAGS:
        assert tag in system_prompt

    trade = {
        "ticker": "A",
        "entry_date": "2025-01-01",
        "exit_date": "2025-01-08",
        "hold_days": 5,
        "realized_pnl_pct": 3.0,
        "exit_reason": "AGENT_SELL",
        "forensics_type": "TREND_CONTINUATION",
        "diagnosis_reason": "test",
        "entry_features": {},
        "mae_pct": -2.0,
        "mfe_pct": 5.0,
        "profit_given_back_pct": 2.0,
        "run_up_before_entry_pct": 3.0,
        "largest_gap_down_pct": None,
        "secondary_tags": ["GAVE_BACK_PROFIT"],
        "post_exit": {"post_exit_ret_5d_pct": 1.5},
    }
    user_prompt = build_reflection_user_prompt([trade], [])
    assert "mae=" in user_prompt and "mfe=" in user_prompt
    assert "GAVE_BACK_PROFIT" in user_prompt
    assert "post_exit_ret_5d_pct" in user_prompt
