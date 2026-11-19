"""
Manual smoke test for learning/engine.py's weekly reflection against the REAL configured LLM
(settings.REFLECTION_LLM_PROVIDER and its fallback). Builds a throwaway SQLite database in a
temp directory -- storage/portfolio.db is never opened, read, or written.

Makes 1-3 real LLM calls (primary, its own retry if needed, one fallback attempt if the
primary fails). Never prints, logs, or writes any API key or .env content -- only which
environment variable is missing, if one is.

Run it with:
    python -m scripts.smoke_test_reflection
See Plan_v3 §5.4. Not run automatically by the test suite -- this is a manual, human-run script.
"""

import json
import sys
import tempfile
from datetime import timedelta
from pathlib import Path

import pytest

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent / "src"
for p in (str(WORKSPACE_ROOT), str(WORKSPACE_ROOT.parent)):
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

BANNER = "SMOKE TEST: fake data, temp database, makes 1-3 real LLM calls"

AGENT_ID = "simons"


def _print_banner() -> None:
    print("=" * len(BANNER))
    print(BANNER)
    print("=" * len(BANNER))


def _check_api_keys_configured():
    """Tries to build the real primary/fallback providers exactly as learning.engine.run does
    when no client is injected. Returns (ok, message). Never prints a key value -- LLMConfigError
    messages (see llm/client.py::require_setting/_require_env) only ever name the missing
    environment variable."""
    from learning.engine import _default_providers
    from llm.client import LLMConfigError

    try:
        primary, fallback = _default_providers()
        return True, (primary, fallback)
    except LLMConfigError as exc:
        return False, str(exc)


def _insert_decision_with_snapshot(conn, clock, ticker: str, as_of_date: str, features: dict) -> int:
    now_iso = clock.now_iso()
    cur = conn.execute(
        "INSERT INTO feature_snapshots (ticker, as_of_date, schema_version, features_json, created_at) "
        "VALUES (?, ?, 1, ?, ?)",
        (ticker, as_of_date, json.dumps(features), now_iso),
    )
    snapshot_id = cur.lastrowid
    cur = conn.execute(
        "INSERT INTO decisions (run_date, agent_id, ticker, source, action, reasoning, snapshot_id, created_at) "
        "VALUES (?, ?, ?, 'LLM', 'BUY', 'smoke test entry', ?, ?)",
        (as_of_date, AGENT_ID, ticker, snapshot_id, now_iso),
    )
    return cur.lastrowid


def _insert_fake_closed_position(
    conn,
    ohlcv_conn,
    clock,
    ticker: str,
    entry_date: str,
    exit_date: str,
    entry_features: dict,
    hold_days: int,
    realized_pnl_pct: float,
    exit_reason: str,
    forensics_type: str,
    diagnosis: dict,
    post_exit_sessions: int = 5,
) -> int:

    decision_id = _insert_decision_with_snapshot(conn, clock, ticker, entry_date, entry_features)
    diagnosis = dict(diagnosis)
    diagnosis.setdefault("forensics_type", forensics_type)
    cur = conn.execute(
        """
        INSERT INTO positions
            (agent_id, ticker, sector, shares, avg_entry_price_paise, stop_paise, target_paise,
             last_price_paise, status, entry_date, entry_decision_id, exit_date, exit_price_paise,
             exit_reason, hold_days, realized_pnl_paise, realized_pnl_pct, forensics_type,
             regime_at_exit, diagnosis_json)
        VALUES (?, ?, 'IT', 10, 100000, 90000, 120000, 100000, 'CLOSED', ?, ?, ?, 105000, ?, ?, 50000, ?, ?, 'NORMAL', ?)
        """,
        (
            AGENT_ID,
            ticker,
            entry_date,
            decision_id,
            exit_date,
            exit_reason,
            hold_days,
            realized_pnl_pct,
            forensics_type,
            json.dumps(diagnosis),
        ),
    )
    position_id = cur.lastrowid

    from datetime import date

    d = date.fromisoformat(exit_date) + timedelta(days=1)
    for _ in range(post_exit_sessions):
        ohlcv_conn.execute(
            "INSERT OR REPLACE INTO ohlcv (ticker, trade_date, open, high, low, close, volume) "
            "VALUES (?, ?, 100.0, 101.0, 99.0, 100.0, 100000)",
            (ticker, d.isoformat()),
        )
        d += timedelta(days=1)

    return position_id


def _seed_fake_trades(conn, ohlcv_conn, clock):
    today = clock.today()
    exit_date = (today - timedelta(days=10)).isoformat()
    entry_date = (today - timedelta(days=25)).isoformat()

    _insert_fake_closed_position(
        conn,
        ohlcv_conn,
        clock,
        "FAKEA",
        entry_date,
        exit_date,
        entry_features={"rsi_14": 58.0, "ema_20_above_50": True, "volume_surge": 1.4, "macd_hist": 0.8},
        hold_days=3,
        realized_pnl_pct=-3.2,
        exit_reason="STOP_HIT",
        forensics_type="FALSE_BREAKOUT",
        diagnosis={
            "reason": "Close fell below entry within first 3 sessions without volume surge.",
            "mae_pct": -5.1,
            "mfe_pct": 0.8,
            "profit_given_back_pct": 4.0,
            "run_up_before_entry_pct": 18.5,
            "largest_gap_down_pct": -2.1,
            "secondary_tags": ["LATE_ENTRY"],
        },
    )
    _insert_fake_closed_position(
        conn,
        ohlcv_conn,
        clock,
        "FAKEB",
        entry_date,
        exit_date,
        entry_features={"rsi_14": 61.0, "ema_20_above_50": True, "volume_surge": 1.3, "macd_hist": 0.6},
        hold_days=2,
        realized_pnl_pct=-2.8,
        exit_reason="STOP_HIT",
        forensics_type="FALSE_BREAKOUT",
        diagnosis={
            "reason": "Close fell below entry within first 3 sessions without volume surge.",
            "mae_pct": -4.4,
            "mfe_pct": 0.5,
            "profit_given_back_pct": 3.3,
            "run_up_before_entry_pct": 21.0,
            "largest_gap_down_pct": -1.8,
            "secondary_tags": ["LATE_ENTRY"],
        },
    )
    _insert_fake_closed_position(
        conn,
        ohlcv_conn,
        clock,
        "FAKEC",
        entry_date,
        exit_date,
        entry_features={"rsi_14": 50.0, "ema_20_above_50": True, "volume_surge": 1.1, "macd_hist": 0.2},
        hold_days=6,
        realized_pnl_pct=-4.5,
        exit_reason="AGENT_SELL",
        forensics_type="BROAD_MARKET_DRAG",
        diagnosis={
            "reason": "ELEVATED/PANIC VIX on 6/8 holding days (75%).",
            "broad_drag_ratio": 0.75,
            "mae_pct": -6.0,
            "mfe_pct": 0.3,
            "profit_given_back_pct": 4.8,
            "run_up_before_entry_pct": 2.0,
            "largest_gap_down_pct": -1.0,
            "secondary_tags": ["WEAK_MARKET"],
        },
    )
    _insert_fake_closed_position(
        conn,
        ohlcv_conn,
        clock,
        "FAKED",
        entry_date,
        exit_date,
        entry_features={"rsi_14": 62.0, "ema_20_above_50": True, "volume_surge": 1.6, "macd_hist": 1.2},
        hold_days=5,
        realized_pnl_pct=6.5,
        exit_reason="AGENT_SELL",
        forensics_type="TREND_CONTINUATION",
        diagnosis={
            "reason": "Win with sustained trend following momentum rules.",
            "mae_pct": -1.0,
            "mfe_pct": 9.0,
            "profit_given_back_pct": 2.5,
            "run_up_before_entry_pct": 3.0,
            "largest_gap_down_pct": None,
            "secondary_tags": [],
        },
    )


def _print_results(conn, run_date: str) -> None:
    print("\n--- llm_calls rows (this run) ---")
    rows = conn.execute(
        "SELECT model, provider, parse_status, finish_reason, tokens_in, tokens_out, latency_ms, "
        "fallback_used, prompt, response FROM llm_calls WHERE agent_id = ? AND run_date = ? ORDER BY id",
        (AGENT_ID, run_date),
    ).fetchall()
    for i, r in enumerate(rows, 1):
        print(
            f"\n[call {i}] model={r['model']} provider={r['provider']} parse_status={r['parse_status']} "
            f"finish_reason={r['finish_reason']} tokens_in={r['tokens_in']} tokens_out={r['tokens_out']} "
            f"latency_ms={r['latency_ms']} fallback_used={bool(r['fallback_used'])}"
        )
        print(f"--- prompt sent (call {i}) ---\n{r['prompt']}")
        print(f"--- raw LLM answer (call {i}) ---\n{r['response']}")

    print("\n--- validation outcomes (activity_log) ---")
    for r in conn.execute(
        "SELECT event_type, description, metadata_json FROM activity_log "
        "WHERE agent_id = ? AND event_type IN ('HEURISTIC_CREATED', 'HEURISTIC_REJECTED') ORDER BY id",
        (AGENT_ID,),
    ).fetchall():
        print(f"[{r['event_type']}] {r['description']}")

    print("\n--- resulting agent_memory rows ---")
    for r in conn.execute("SELECT * FROM agent_memory WHERE agent_id = ?", (AGENT_ID,)).fetchall():
        print(dict(r))

    print("\n--- resulting reflection_runs rows ---")
    for r in conn.execute("SELECT * FROM reflection_runs WHERE agent_id = ? ORDER BY id DESC", (AGENT_ID,)).fetchall():
        print(dict(r))


def main() -> None:
    _print_banner()

    ok, result = _check_api_keys_configured()
    if not ok:
        print(f"\nNo usable LLM configuration found: {result}")
        print("Set the missing environment variable (see .env.example) and re-run. Exiting cleanly.")
        return
    primary, fallback = result

    import sqlite3

    from core.clock import SystemClock
    from core.database import get_connection
    from ingestion.sync_ohlcv import ensure_schema as ensure_ohlcv_schema
    from scripts.init_db import init_db

    clock = SystemClock()

    with tempfile.TemporaryDirectory(prefix="stockminds_smoke_") as tmp_dir:
        portfolio_path = str(Path(tmp_dir) / "portfolio.db")
        print(f"\nTemp portfolio database: {portfolio_path}")

        conn = get_connection(portfolio_path)
        ohlcv_conn = sqlite3.connect(":memory:", isolation_level=None)
        ohlcv_conn.row_factory = sqlite3.Row
        ensure_ohlcv_schema(ohlcv_conn)
        try:
            init_db(conn, clock)
            _seed_fake_trades(conn, ohlcv_conn, clock)

            run_date = clock.today().isoformat()
            print(f"\nCalling learning.engine.run for agent={AGENT_ID!r} as of {run_date}...")

            from learning.engine import run as run_reflection

            summary = run_reflection(
                conn,
                clock,
                llm_client=primary,
                fallback_client=fallback,
                agent_ids=[AGENT_ID],
                ohlcv_conn=ohlcv_conn,
            )
            print(f"\nSummary: {summary}")

            _print_results(conn, run_date)
        finally:
            conn.close()
            ohlcv_conn.close()

    print("\nDone. The temp database has been removed; storage/portfolio.db was never touched.")


@pytest.mark.live
def test_reflection_live_smoke():
    """Live smoke test: verifies configured LLM provider against reflection engine."""
    ok, err_msg = _check_api_keys_configured()
    if not ok:
        pytest.skip(f"Live LLM API keys not configured: {err_msg}")
    main()


if __name__ == "__main__":
    main()
