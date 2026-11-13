"""
Read-only audit of the learning lifecycle across one or more portfolio databases.

Opens every database with sqlite3's `mode=ro` URI flag -- it is never possible for this script
to write anything, even by accident, so it is safe to point at a live storage/portfolio.db or
any storage/backtest/*.db file. Works on older databases that predate migrations 0005-0008
(missing tables or columns are noted and skipped, never a crash).

Run it with:
    python -m scripts.audit_learning_lifecycle --db storage/portfolio.db
    python -m scripts.audit_learning_lifecycle --db a.db --db b.db --out report.md
See Plan_v3 §5.5 and docs/learning_notes.md.
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

_WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent / "src"
for _p in (str(_WORKSPACE_ROOT), str(_WORKSPACE_ROOT.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


# ---------------------------------------------------------------------------
# Connection / schema introspection helpers
# ---------------------------------------------------------------------------


def open_readonly(path: str) -> sqlite3.Connection:
    uri = f"file:{Path(path).resolve().as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)).fetchone() is not None


def column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    return any(row["name"] == column for row in conn.execute(f"PRAGMA table_info({table})"))


def list_agents(conn: sqlite3.Connection) -> list[str]:
    if not table_exists(conn, "agents"):
        return []
    return [r["id"] for r in conn.execute("SELECT id FROM agents ORDER BY id").fetchall()]


# ---------------------------------------------------------------------------
# Per-section report builders -- each appends plain lines, never raises on a
# missing table/column (that's the whole point: older databases must not crash this).
# ---------------------------------------------------------------------------


def section_trades_and_runs(conn: sqlite3.Connection, agent_id: str, lines: list[str]) -> int:
    """Returns closed_trades count (used by the attention list)."""
    closed = 0
    if table_exists(conn, "positions"):
        closed = conn.execute(
            "SELECT COUNT(*) AS n FROM positions WHERE agent_id = ? AND status = 'CLOSED'", (agent_id,)
        ).fetchone()["n"]
    lines.append(f"- Closed trades: {closed}")

    if table_exists(conn, "reflection_runs"):
        rows = conn.execute(
            "SELECT status, COUNT(*) AS n FROM reflection_runs WHERE agent_id = ? GROUP BY status",
            (agent_id,),
        ).fetchall()
        by_status = {r["status"]: r["n"] for r in rows}
        lines.append(f"- reflection_runs by status: {by_status if by_status else '(none yet)'}")
        lines.append(f"- SKIPPED_TOO_FEW_TRADES runs: {by_status.get('SKIPPED_TOO_FEW_TRADES', 0)}")
    else:
        lines.append("- reflection_runs table missing (pre-migration database) -- skipping")

    return closed


def section_heuristics(conn: sqlite3.Connection, agent_id: str, lines: list[str]) -> int:
    """Returns the count of heuristics that ever reached active/reinforced (attention list)."""
    if not table_exists(conn, "agent_memory"):
        lines.append("- agent_memory table missing -- skipping")
        return 0

    status_rows = conn.execute(
        "SELECT status, COUNT(*) AS n FROM agent_memory WHERE agent_id = ? GROUP BY status", (agent_id,)
    ).fetchall()
    by_status = {r["status"]: r["n"] for r in status_rows}
    lines.append(f"- Heuristics by status: {by_status if by_status else '(none)'}")

    kind_rows = conn.execute(
        "SELECT kind, COUNT(*) AS n FROM agent_memory WHERE agent_id = ? GROUP BY kind", (agent_id,)
    ).fetchall()
    by_kind = {r["kind"]: r["n"] for r in kind_rows}
    lines.append(f"- SEEK/AVOID split: {by_kind if by_kind else '(none)'}")

    ever_active_ids = set()
    if table_exists(conn, "activity_log"):
        rows = conn.execute(
            "SELECT metadata_json FROM activity_log WHERE agent_id = ? AND event_type = 'HEURISTIC_STATUS_CHANGED'",
            (agent_id,),
        ).fetchall()
        for r in rows:
            try:
                meta = json.loads(r["metadata_json"]) if r["metadata_json"] else {}
            except (json.JSONDecodeError, TypeError):
                continue
            if meta.get("new_status") in ("active", "reinforced"):
                ever_active_ids.add(meta.get("heuristic_id"))
        lines.append(f"- Ever reached active or reinforced: {len(ever_active_ids)}")
    else:
        lines.append("- activity_log table missing -- cannot compute 'ever active' -- skipping")

    return len(ever_active_ids)


def section_applications(conn: sqlite3.Connection, agent_id: str, lines: list[str]) -> None:
    if not (table_exists(conn, "heuristic_applications") and table_exists(conn, "agent_memory")):
        lines.append("- heuristic_applications/agent_memory missing -- skipping")
        return

    outcome_rows = conn.execute(
        "SELECT ha.outcome, COUNT(*) AS n FROM heuristic_applications ha "
        "JOIN agent_memory am ON am.id = ha.heuristic_id WHERE am.agent_id = ? GROUP BY ha.outcome",
        (agent_id,),
    ).fetchall()
    lines.append(
        f"- Applications by outcome: {({r['outcome']: r['n'] for r in outcome_rows}) if outcome_rows else '(none)'}"
    )

    horizon_rows = conn.execute(
        "SELECT ha.horizon_days, COUNT(*) AS n FROM heuristic_applications ha "
        "JOIN agent_memory am ON am.id = ha.heuristic_id WHERE am.agent_id = ? GROUP BY ha.horizon_days",
        (agent_id,),
    ).fetchall()
    lines.append(
        f"- Applications by horizon_days: {({r['horizon_days']: r['n'] for r in horizon_rows}) if horizon_rows else '(none)'}"
    )


def _rolling_rate(resolved_rows: list[sqlite3.Row], window: int) -> float | None:
    """resolved_rows must already be ordered ascending by resolved_on, id."""
    tail = resolved_rows[-window:]
    if len(tail) < window:
        return None
    successes = sum(1 for r in tail if r["outcome"] == "SUCCESS")
    return successes / window


def section_per_heuristic(
    conn: sqlite3.Connection,
    agent_id: str,
    lines: list[str],
    rolling_window: int,
) -> list[dict]:
    """Returns a list of {heuristic_id, status, rolling_rate} dicts, used by the attention list."""
    flagged: list[dict] = []
    if not table_exists(conn, "agent_memory"):
        return flagged

    heuristics = conn.execute(
        "SELECT id, kind, heuristic_text, status, times_triggered FROM agent_memory WHERE agent_id = ? ORDER BY id",
        (agent_id,),
    ).fetchall()

    has_applications = table_exists(conn, "heuristic_applications")
    has_activity_log = table_exists(conn, "activity_log")

    for h in heuristics:
        text = (h["heuristic_text"] or "")[:80]
        lines.append(f"- Heuristic #{h['id']} [{h['kind']}/{h['status']}]: {text}")
        lines.append(f"    times_fired={h['times_triggered']}")

        rolling_rate = None
        if has_applications:
            resolved_rows = conn.execute(
                "SELECT outcome, resolved_on FROM heuristic_applications WHERE heuristic_id = ? "
                "AND outcome IN ('SUCCESS', 'FAILURE') ORDER BY resolved_on ASC, id ASC",
                (h["id"],),
            ).fetchall()
            n = len(resolved_rows)
            successes = sum(1 for r in resolved_rows if r["outcome"] == "SUCCESS")
            lifetime_rate = (successes / n) if n else None
            rolling_rate = _rolling_rate(resolved_rows, rolling_window)
            lines.append(
                f"    lifetime: n={n} success_rate={'n/a' if lifetime_rate is None else round(lifetime_rate, 3)}"
            )
            lines.append(
                f"    last {rolling_window} resolved: "
                f"{'not enough yet' if rolling_rate is None else f'success_rate={round(rolling_rate, 3)}'}"
            )
        else:
            lines.append("    heuristic_applications table missing -- skipping rates")

        if has_activity_log:
            changes = conn.execute(
                "SELECT created_at, metadata_json FROM activity_log "
                "WHERE agent_id = ? AND event_type = 'HEURISTIC_STATUS_CHANGED' ORDER BY id ASC",
                (agent_id,),
            ).fetchall()
            for c in changes:
                try:
                    meta = json.loads(c["metadata_json"]) if c["metadata_json"] else {}
                except (json.JSONDecodeError, TypeError):
                    continue
                if meta.get("heuristic_id") == h["id"]:
                    lines.append(
                        f"    {c['created_at']}: {meta.get('old_status')} -> {meta.get('new_status')} "
                        f"({meta.get('reason', '')})"
                    )

        if h["status"] in ("active", "reinforced"):
            flagged.append({"heuristic_id": h["id"], "status": h["status"], "rolling_rate": rolling_rate})

    return flagged


def section_avoid_missed_winners(
    conn: sqlite3.Connection,
    agent_id: str,
    lines: list[str],
    cost_hurdle: float,
) -> None:
    required = ("agent_memory", "heuristic_applications", "forward_returns")
    if not all(table_exists(conn, t) for t in required):
        lines.append("- Required tables missing for the AVOID missed-winners check -- skipping")
        return

    avoid_heuristics = conn.execute(
        "SELECT id, heuristic_text FROM agent_memory WHERE agent_id = ? AND kind = 'AVOID'", (agent_id,)
    ).fetchall()
    if not avoid_heuristics:
        lines.append("- No AVOID heuristics for this agent")
        return

    for h in avoid_heuristics:
        rows = conn.execute(
            "SELECT fr.ret_pct FROM heuristic_applications ha "
            "JOIN forward_returns fr ON fr.decision_id = ha.decision_id AND fr.horizon_days = ha.horizon_days "
            "WHERE ha.heuristic_id = ?",
            (h["id"],),
        ).fetchall()
        if not rows:
            lines.append(f"- AVOID #{h['id']}: no resolved forward returns joined yet")
            continue
        rets = [r["ret_pct"] for r in rows]
        avg_ret = sum(rets) / len(rets)
        missed_pct = sum(1 for r in rets if r > cost_hurdle) / len(rets) * 100
        text = (h["heuristic_text"] or "")[:60]
        lines.append(
            f"- AVOID #{h['id']} ({text}): avg_forward_return={avg_ret:.2f}% "
            f"missed_winners={missed_pct:.1f}% (n={len(rets)}, cost_hurdle={cost_hurdle}%)"
        )


# ---------------------------------------------------------------------------
# Top-level per-database/per-agent orchestration
# ---------------------------------------------------------------------------


def audit_one_database(db_path: str, rolling_window: int, cost_hurdle: float) -> list[str]:
    """Returns the full report lines for one database (attention items first, then detail)."""
    lines: list[str] = []
    attention: list[str] = []
    detail_lines: list[str] = []

    conn = open_readonly(db_path)
    try:
        agents = list_agents(conn)
        if not agents:
            detail_lines.append("No agents table or no rows -- nothing to audit in this database.")
        for agent_id in agents:
            detail_lines.append(f"\n### Agent `{agent_id}`\n")

            closed = section_trades_and_runs(conn, agent_id, detail_lines)
            if closed < 3:
                attention.append(f"- `{agent_id}`: only {closed} closed trade(s) so far.")

            ever_active = section_heuristics(conn, agent_id, detail_lines)
            has_heuristics = (
                table_exists(conn, "agent_memory")
                and conn.execute("SELECT 1 FROM agent_memory WHERE agent_id = ? LIMIT 1", (agent_id,)).fetchone()
                is not None
            )
            if has_heuristics and ever_active == 0:
                attention.append(f"- `{agent_id}`: has heuristics but NONE ever reached active or reinforced.")

            section_applications(conn, agent_id, detail_lines)

            flagged = section_per_heuristic(conn, agent_id, detail_lines, rolling_window)
            for f in flagged:
                if f["rolling_rate"] is not None and f["rolling_rate"] < 0.45:
                    attention.append(
                        f"- `{agent_id}` heuristic #{f['heuristic_id']}: status={f['status']} but recent "
                        f"(last {rolling_window}) success rate is {f['rolling_rate']:.2f} (< 0.45)."
                    )

            section_avoid_missed_winners(conn, agent_id, detail_lines, cost_hurdle)
    finally:
        conn.close()

    lines.append(f"## {db_path}\n")
    if attention:
        lines.append("**Attention:**")
        lines.extend(attention)
    else:
        lines.append("**Attention:** nothing flagged.")
    lines.extend(detail_lines)
    return lines


def build_report(db_paths: list[str], rolling_window: int, cost_hurdle: float) -> str:
    header = [
        "# Learning lifecycle audit",
        f"(rolling window = {rolling_window}, cost hurdle = {cost_hurdle}%)",
        "",
    ]
    body: list[str] = []
    for path in db_paths:
        body.extend(audit_one_database(path, rolling_window, cost_hurdle))
        body.append("")
    return "\n".join(header + body)


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only audit of the learning lifecycle.")
    parser.add_argument(
        "--db",
        dest="db_paths",
        action="append",
        required=True,
        help="Path to a portfolio/backtest SQLite database. Repeatable.",
    )
    parser.add_argument("--out", dest="out_path", default=None, help="Optional markdown output file.")
    args = parser.parse_args()

    from core.config import settings

    report = build_report(
        args.db_paths,
        settings.HEURISTIC_ROLLING_WINDOW,
        settings.HEURISTIC_SUCCESS_COST_HURDLE_PCT,
    )
    print(report)
    if args.out_path:
        Path(args.out_path).write_text(report, encoding="utf-8")
        print(f"\nWritten to {args.out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
