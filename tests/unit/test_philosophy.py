"""
Unit tests for evaluation/philosophy.py.
Verifies the 3-Dimensional Persona Fidelity Engine:
  1. Entry Selection Fidelity against quantitative hurdles from PersonaConfig.
  2. Holding Horizon Fidelity against persona strategy types.
  3. Cognitive Citation Fidelity against authorized metric domains.
"""

import sqlite3

from evaluation.philosophy import (
    evaluate_agent_philosophy_adherence,
    evaluate_citation_fidelity,
    evaluate_decision_philosophy,
    evaluate_horizon_fidelity,
    resolve_persona,
)


def test_resolve_persona():
    assert resolve_persona("lynch") is not None
    assert resolve_persona("baseline-lynch-rules") is not None
    assert resolve_persona("baseline-rj-rules") is not None
    assert resolve_persona("jhunjhunwala") is not None
    assert resolve_persona("simons") is not None
    assert resolve_persona("varsity") is not None
    assert resolve_persona("unknown_agent") is None


def test_lynch_hurdles_fidelity():
    persona = resolve_persona("lynch")
    assert persona is not None
    assert persona.strategy_type == "GARP"

    # Fully compliant GARP candidate
    compliant_features = {
        "peg": 0.85,
        "roce_pct": 16.5,
        "debt_to_equity": 0.4,
        "cfo_to_pat": 1.1,
        "pat_growth_yoy_pct": 22.0,
    }
    res = evaluate_decision_philosophy("lynch", {}, compliant_features)
    assert res["passed"] is True
    assert res["fundamental_passed"] is True
    assert res["tenets_passed"] == 5
    assert res["tenets_checked"] == 5

    # Non-compliant candidate (Extreme valuation PEG 3.5, low ROCE, high debt)
    bad_features = {
        "peg": 3.5,
        "roce_pct": 5.0,
        "debt_to_equity": 2.8,
        "cfo_to_pat": 0.3,
        "pat_growth_yoy_pct": -8.0,
    }
    res_bad = evaluate_decision_philosophy("lynch", {}, bad_features)
    assert res_bad["passed"] is False
    assert res_bad["fundamental_passed"] is False
    assert res_bad["tenets_passed"] == 0


def test_jhunjhunwala_hurdles_fidelity():
    persona = resolve_persona("jhunjhunwala")
    assert persona is not None
    assert persona.strategy_type == "GROWTH_COMPOUNDER"

    good_features = {
        "volume_surge": 1.4,
        "ema_20_above_50": 1,
        "pat_growth_yoy_pct": 20.0,
        "roce_pct": 22.0,
        "promoter_holding_pct": 55.0,
        "debt_to_equity": 0.6,
        "pe": 32.0,
    }
    res = evaluate_decision_philosophy("jhunjhunwala", {}, good_features)
    assert res["passed"] is True
    assert res["technical_passed"] is True
    assert res["fundamental_passed"] is True


def test_simons_momentum_and_rrr_fidelity():
    decision_good = {
        "entry_high_paise": 250000,
        "stop_paise": 240000,  # risk = 100
        "target_paise": 270000,  # reward = 200 (RRR = 2.0 >= 1.0)
    }
    features_breakout = {
        "ema_20_above_50": 1,
        "rsi_14": 60.0,
        "volume_surge": 1.8,
        "macd_hist": 4.5,
        "adx_14": 28.0,
        "kaufman_er_20": 0.55,
    }
    res = evaluate_decision_philosophy("simons", decision_good, features_breakout)
    assert res["passed"] is True
    assert res["technical_passed"] is True

    # Poor RRR violates Simons discipline
    decision_poor_rrr = {
        "entry_high_paise": 250000,
        "stop_paise": 230000,  # risk = 200
        "target_paise": 255000,  # reward = 50 (RRR = 0.25 < 1.0)
    }
    res_bad_rrr = evaluate_decision_philosophy("simons", decision_poor_rrr, features_breakout)
    assert res_bad_rrr["passed"] is False


def test_holding_horizon_fidelity():
    # 1. Simons (QUANT_MOMENTUM): short swing compliant vs dead hold drift
    simons_positions_faithful = [
        {"hold_days": 3, "exit_reason": "TARGET_HIT", "forensics_type": None, "realized_pnl_pct": 4.5},
        {"hold_days": 8, "exit_reason": "STOP_HIT", "forensics_type": None, "realized_pnl_pct": -2.0},
    ]
    h_simons_good = evaluate_horizon_fidelity("simons", simons_positions_faithful)
    assert h_simons_good["score"] == 100.0

    simons_positions_drift = [
        {"hold_days": 45, "exit_reason": "DISCRETIONARY_SELL", "forensics_type": None, "realized_pnl_pct": -1.0},
    ]
    h_simons_bad = evaluate_horizon_fidelity("simons", simons_positions_drift)
    assert h_simons_bad["score"] == 10.0

    # 2. Lynch (GARP): patient compounder compliant vs impatient shakeout
    lynch_positions_patient = [
        {"hold_days": 45, "exit_reason": "TARGET_HIT", "forensics_type": None, "realized_pnl_pct": 18.0},
    ]
    h_lynch_good = evaluate_horizon_fidelity("lynch", lynch_positions_patient)
    assert h_lynch_good["score"] == 100.0

    # Premature technical shakeout on noise (hold_days=4 without thesis breakdown)
    lynch_positions_impatient = [
        {
            "hold_days": 4,
            "exit_reason": "DISCRETIONARY_SELL",
            "forensics_type": "PREMATURE_EXIT",
            "realized_pnl_pct": 0.5,
        },
    ]
    h_lynch_bad = evaluate_horizon_fidelity("lynch", lynch_positions_impatient)
    assert h_lynch_bad["score"] == 20.0

    # Emergency risk cut (hold_days=4 but STOP_HIT) is respected
    lynch_emergency_cut = [
        {"hold_days": 4, "exit_reason": "STOP_HIT", "forensics_type": "BROAD_MARKET_DRAG", "realized_pnl_pct": -6.5},
    ]
    h_lynch_cut = evaluate_horizon_fidelity("lynch", lynch_emergency_cut)
    assert h_lynch_cut["score"] == 80.0


    # Early target exit with large profit (hold_days=15, pnl=+22.5%) is fully compliant
    lynch_early_target = [
        {"hold_days": 15, "exit_reason": "AGENT_SELL", "forensics_type": "EARNINGS_MOMENTUM", "realized_pnl_pct": 22.5},
    ]
    h_lynch_target = evaluate_horizon_fidelity("lynch", lynch_early_target)
    assert h_lynch_target["score"] == 100.0


def test_cognitive_citation_fidelity():
    # Lynch citing allowed fundamental & quality metrics
    dec_faithful = [
        {"cited_metrics_json": '{"peg": 0.9, "roce_pct": 18.5, "pat_growth_yoy_pct": 14.0}'},
    ]
    c_good = evaluate_citation_fidelity("lynch", dec_faithful)
    assert c_good["score"] == 100.0
    assert c_good["valid_cited"] == 3

    # Lynch citing unauthorized conditional quant indicators and imaginary metric
    dec_drift = [
        {"cited_metrics_json": '{"peg": 0.9, "kaufman_er_20": 0.6, "skew_60": 1.2, "imaginary_score": 99}'},
    ]
    c_bad = evaluate_citation_fidelity("lynch", dec_drift)
    # Only peg is valid for Lynch; kaufman_er_20, skew_60, and imaginary_score are unauthorized
    assert c_bad["score"] == 25.0
    assert c_bad["valid_cited"] == 1
    assert c_bad["total_cited"] == 4


def test_agent_philosophy_adherence_db_composite():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE feature_snapshots (
            id INTEGER PRIMARY KEY,
            features_json TEXT
        );
        CREATE TABLE decisions (
            id INTEGER PRIMARY KEY,
            agent_id TEXT,
            action TEXT,
            ticker TEXT,
            shares INTEGER,
            entry_high_paise INTEGER,
            stop_paise INTEGER,
            target_paise INTEGER,
            cited_metrics_json TEXT,
            snapshot_id INTEGER
        );
        CREATE TABLE positions (
            id INTEGER PRIMARY KEY,
            agent_id TEXT,
            ticker TEXT,
            status TEXT,
            hold_days INTEGER,
            exit_reason TEXT,
            forensics_type TEXT,
            realized_pnl_pct REAL
        );
    """)

    # Seed 2 decisions: 1 compliant, 1 non-compliant for lynch
    conn.execute(
        """INSERT INTO feature_snapshots VALUES (1,
        '{"peg": 0.9, "roce_pct": 15.0, "debt_to_equity": 0.4, "cfo_to_pat": 0.9, "pat_growth_yoy_pct": 15.0}')"""
    )
    conn.execute(
        """INSERT INTO feature_snapshots VALUES (2,
        '{"peg": 3.5, "roce_pct": 4.0, "debt_to_equity": 2.5, "cfo_to_pat": 0.2, "pat_growth_yoy_pct": -10.0}')"""
    )

    conn.execute(
        """INSERT INTO decisions VALUES (
            1, 'lynch', 'BUY', 'INFY', 10, 200000, 180000, 240000,
            '{"peg": 0.9, "roce_pct": 15.0}', 1
        )"""
    )
    conn.execute(
        """INSERT INTO decisions VALUES (
            2, 'lynch', 'BUY', 'JUNK', 10, 100000, 90000, 120000,
            '{"peg": 3.5, "kaufman_er_20": 0.8, "skew_60": 0.5}', 2
        )"""
    )

    # Seed 1 closed position held patiently for 40 days
    conn.execute(
        """INSERT INTO positions VALUES (
            1, 'lynch', 'INFY', 'CLOSED', 40, 'TARGET_HIT', NULL, 15.0
        )"""
    )

    adh = evaluate_agent_philosophy_adherence(conn, "lynch")
    assert adh["agent_id"] == "lynch"
    assert adh["total_buys"] == 2
    assert adh["compliant_buys"] == 1
    assert adh["selection_fidelity"] == 50.0  # 1 of 2 compliant
    assert adh["horizon_fidelity"] == 100.0  # 40 days >= 30
    assert adh["citation_fidelity"] == 60.0  # 3 of 5 metrics valid (INFY: peg, roce; JUNK: peg vs kaufman, skew)
    # Composite = 0.40 * 50 + 0.40 * 100 + 0.20 * 60 = 20.0 + 40.0 + 12.0 = 72.0
    assert adh["composite_score"] == 72.0
    assert adh["status"] == "MODERATE_DRIFT"
    assert adh["adherence_pct"] == 72.0
    conn.close()
