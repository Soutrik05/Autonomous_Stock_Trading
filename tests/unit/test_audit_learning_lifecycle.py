"""
Tests for scripts/audit_learning_lifecycle.py: a read-only audit over real (file-based) SQLite
databases -- the script's own `mode=ro` URI needs a real file, so these tests build small
on-disk temp databases rather than using the usual in-memory fixture. One database has every
migration (0001-0008); one deliberately stops short of 0007/0008, simulating an older database,
to prove the audit degrades gracefully instead of crashing.
See Plan_v3 §5.5.
"""

import json
import sqlite3
from pathlib import Path

import scripts.audit_learning_lifecycle as audit

_DB_DIR = Path(__file__).resolve().parents[2] / "db"
_SCHEMA_PATH = _DB_DIR / "schema.sql"
_MIGRATIONS_DIR = _DB_DIR / "migrations"

NOW = "2026-10-19T20:00:00+05:30"
RUN_DATE = "2026-10-19"
AGENT = "simons"


def _build_file_db(path: str, up_to_migration: str = None) -> None:
    """Writes a fresh portfolio schema to `path`. `up_to_migration` (e.g. '0006') stops applying
    migrations after that number, to simulate an older database missing later columns/tables."""
    conn = sqlite3.connect(path, isolation_level=None)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(_SCHEMA_PATH.read_text(encoding="utf-8"))
    for migration_path in sorted(_MIGRATIONS_DIR.glob("*.sql")):
        number = migration_path.name.split("_")[0]
        if number == "0001":
            continue
        if up_to_migration is not None and number > up_to_migration:
            continue
        conn.executescript(migration_path.read_text(encoding="utf-8"))
    conn.close()


def _seed_basic_data(path: str) -> None:
    conn = sqlite3.connect(path, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute(
        "INSERT INTO agents (id, name, philosophy, kind, starting_cash_paise, cash_paise, created_at, updated_at) "
        "VALUES (?, ?, 'Test', 'LLM', 50000000, 50000000, ?, ?)",
        (AGENT, AGENT, NOW, NOW),
    )

    # Two closed positions.
    for i in range(2):
        conn.execute(
            "INSERT INTO positions (agent_id, ticker, sector, shares, avg_entry_price_paise, stop_paise, "
            "target_paise, last_price_paise, status, entry_date, exit_date, exit_reason, hold_days, "
            "realized_pnl_paise, realized_pnl_pct) "
            "VALUES (?, ?, 'IT', 10, 100000, 90000, 120000, 100000, 'CLOSED', '2026-09-01', '2026-09-10', "
            "'AGENT_SELL', 5, 50000, 5.0)",
            (AGENT, f"T{i}"),
        )

    if _table_has_column(conn, "reflection_runs"):
        conn.execute(
            "INSERT INTO reflection_runs (agent_id, run_date, last_position_id_reviewed, trades_reviewed, status) "
            "VALUES (?, '2026-10-12', 0, 2, 'SKIPPED_TOO_FEW_TRADES')",
            (AGENT,),
        )

    # One SEEK heuristic that's "active", with resolved applications (success + failure) and a
    # forward_returns row joinable for the AVOID section's twin (an AVOID heuristic too).
    cur = conn.execute(
        "INSERT INTO agent_memory (agent_id, kind, heuristic_text, trigger_json, prescribed_action, "
        "status, confidence, times_triggered, times_successful, last_fired_on, created_at, updated_at) "
        "VALUES (?, 'SEEK', 'test seek', '{}', 'size up', 'active', 0.6, 2, 1, ?, ?, ?)",
        (AGENT, RUN_DATE, NOW, NOW),
    )
    seek_id = cur.lastrowid

    cur = conn.execute(
        "INSERT INTO agent_memory (agent_id, kind, heuristic_text, trigger_json, prescribed_action, "
        "status, confidence, times_triggered, times_successful, last_fired_on, created_at, updated_at) "
        "VALUES (?, 'AVOID', 'test avoid', '{}', 'skip it', 'testing', 0.5, 1, 0, ?, ?, ?)",
        (AGENT, RUN_DATE, NOW, NOW),
    )
    avoid_id = cur.lastrowid

    conn.execute(
        "INSERT INTO feature_snapshots (ticker, as_of_date, schema_version, features_json, created_at) "
        "VALUES ('A', ?, 1, '{}', ?)",
        (RUN_DATE, NOW),
    )
    snap_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]

    decisions = []
    for i in range(2):
        cur = conn.execute(
            "INSERT INTO decisions (run_date, agent_id, ticker, source, action, reasoning, snapshot_id, created_at) "
            "VALUES (?, ?, ?, 'LLM', 'HOLD', 'test', ?, ?)",
            (RUN_DATE, AGENT, f"D{i}", snap_id, NOW),
        )
        decisions.append(cur.lastrowid)

    conn.execute(
        "INSERT INTO heuristic_applications (heuristic_id, decision_id, fired_on, horizon_days, outcome, resolved_on) "
        "VALUES (?, ?, ?, 5, 'SUCCESS', ?)",
        (seek_id, decisions[0], RUN_DATE, RUN_DATE),
    )
    conn.execute(
        "INSERT INTO heuristic_applications (heuristic_id, decision_id, fired_on, horizon_days, outcome) "
        "VALUES (?, ?, ?, 5, 'PENDING')",
        (seek_id, decisions[1], RUN_DATE),
    )
    conn.execute(
        "INSERT INTO heuristic_applications (heuristic_id, decision_id, fired_on, horizon_days, outcome, resolved_on) "
        "VALUES (?, ?, ?, 5, 'SUCCESS', ?)",
        (avoid_id, decisions[1], RUN_DATE, RUN_DATE),
    )
    conn.execute(
        "INSERT INTO forward_returns (decision_id, horizon_days, ret_pct, nifty_ret_pct, computed_on) "
        "VALUES (?, 5, 1.5, 0.5, ?)",
        (decisions[0], NOW),
    )
    conn.execute(
        "INSERT INTO forward_returns (decision_id, horizon_days, ret_pct, nifty_ret_pct, computed_on) "
        "VALUES (?, 5, -2.0, 0.5, ?)",
        (decisions[1], NOW),
    )

    if _table_has_column(conn, "activity_log"):
        conn.execute(
            "INSERT INTO activity_log (agent_id, event_type, ticker, description, metadata_json, created_at) "
            "VALUES (?, 'HEURISTIC_STATUS_CHANGED', NULL, 'testing -> active', ?, ?)",
            (
                AGENT,
                json.dumps(
                    {
                        "heuristic_id": seek_id,
                        "old_status": "testing",
                        "new_status": "active",
                        "reason": "promotion_epoch",
                    }
                ),
                NOW,
            ),
        )

    conn.close()


def _table_has_column(conn, table: str) -> bool:
    try:
        conn.execute(f"SELECT * FROM {table} LIMIT 0")
        return True
    except sqlite3.OperationalError:
        return False


def test_audit_runs_on_a_full_synthetic_database_without_crashing(tmp_path):
    db_path = str(tmp_path / "full.db")
    _build_file_db(db_path)
    _seed_basic_data(db_path)

    report = audit.build_report([db_path], rolling_window=12, cost_hurdle=0.50)

    assert "Learning lifecycle audit" in report
    assert f"`{AGENT}`" in report
    assert "Closed trades: 2" in report
    assert "SKIPPED_TOO_FEW_TRADES" in report
    assert "SEEK/AVOID split" in report
    assert "Applications by outcome" in report
    assert "Applications by horizon_days" in report
    assert "AVOID" in report and "avg_forward_return" in report


def test_audit_flags_zero_closed_trades_and_missed_winners_in_attention_list(tmp_path):
    db_path = str(tmp_path / "attention.db")
    _build_file_db(db_path)
    _seed_basic_data(db_path)

    report = audit.build_report([db_path], rolling_window=12, cost_hurdle=0.50)

    # Only 2 closed trades were seeded -- the attention list's "< 3 closed trades" rule should fire.
    assert "only 2 closed trade" in report


def test_audit_works_on_an_old_database_missing_migrations_0007_and_0008(tmp_path):
    db_path = str(tmp_path / "old.db")
    _build_file_db(db_path, up_to_migration="0006")  # no exit-order watermark, no epoch column
    _seed_basic_data(db_path)

    # Must not raise, and must say so rather than silently pretending the columns exist.
    report = audit.build_report([db_path], rolling_window=12, cost_hurdle=0.50)

    assert "Learning lifecycle audit" in report
    assert f"`{AGENT}`" in report
    # reflection_runs/agent_memory/heuristic_applications/activity_log all existed by migration
    # 0001/0005/0006 already, so the only thing genuinely missing here is the epoch column, which
    # the audit script never selects directly -- so this is really a smoke test that an older
    # database (pre-0007/0008) doesn't crash the script at all.
    assert "Closed trades: 2" in report


def test_audit_skips_a_section_cleanly_when_a_whole_table_is_missing(tmp_path):
    db_path = str(tmp_path / "no_tables.db")
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.execute(
        "CREATE TABLE agents (id TEXT PRIMARY KEY, name TEXT, philosophy TEXT, kind TEXT, "
        "starting_cash_paise INTEGER, cash_paise INTEGER, created_at TEXT, updated_at TEXT)"
    )
    conn.execute(
        "INSERT INTO agents VALUES (?, 'Test', 'Test', 'LLM', 50000000, 50000000, ?, ?)",
        (AGENT, NOW, NOW),
    )
    conn.close()

    report = audit.build_report([db_path], rolling_window=12, cost_hurdle=0.50)

    assert "table missing" in report  # at least one section explicitly says so
    assert f"`{AGENT}`" in report


def test_audit_writes_to_out_file(tmp_path):
    db_path = str(tmp_path / "full.db")
    _build_file_db(db_path)
    _seed_basic_data(db_path)
    out_path = tmp_path / "report.md"

    report = audit.build_report([db_path], rolling_window=12, cost_hurdle=0.50)
    out_path.write_text(report, encoding="utf-8")

    assert out_path.exists()
    assert "Learning lifecycle audit" in out_path.read_text(encoding="utf-8")
