"""
Applies all numbered migrations in db/migrations/, then seeds the five LLM agents and the baseline agent.
See Plan_v3 §7.
"""
import re
import sqlite3
from pathlib import Path
from typing import List, Tuple

from core.clock import Clock, SystemClock
from core.database import get_connection
from settings import settings

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "db" / "migrations"

# (id, name, philosophy, kind)
AGENTS: List[Tuple[str, str, str, str]] = [
    ("simons", "Jim Simons", "Quant Momentum", "LLM"),
    ("lynch", "Peter Lynch", "GARP (Growth At a Reasonable Price)", "LLM"),
    ("marks", "Howard Marks", "Contrarian", "LLM"),
    ("jhunjhunwala", "Rakesh Jhunjhunwala", "Growth & Promoter Quality", "LLM"),
    ("stockminds-core", "StockMinds Core", "Zerodha Varsity Balanced", "LLM"),
    ("baseline-simons-rules", "Baseline Simons Rules", "Rules-only momentum baseline", "BASELINE"),
]

_MIGRATION_VERSION_RE = re.compile(r"^(\d+)_")


def discover_migrations(migrations_dir: Path = MIGRATIONS_DIR) -> List[Tuple[int, Path]]:
    """Returns (version, path) pairs for every db/migrations/NNNN_*.sql file, sorted by version."""
    migrations = []
    for path in migrations_dir.glob("*.sql"):
        match = _MIGRATION_VERSION_RE.match(path.name)
        if not match:
            continue
        migrations.append((int(match.group(1)), path))
    return sorted(migrations, key=lambda pair: pair[0])


def applied_versions(conn: sqlite3.Connection) -> set:
    """Returns the set of migration versions already recorded in schema_version, or empty if the
    table does not exist yet."""
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
    ).fetchall()
    if not tables:
        return set()
    rows = conn.execute("SELECT version FROM schema_version").fetchall()
    return {row["version"] for row in rows}


def apply_migrations(conn: sqlite3.Connection, clock: Clock, migrations_dir: Path = MIGRATIONS_DIR) -> None:
    """Applies every migration not yet recorded in schema_version, in version order."""
    already_applied = applied_versions(conn)
    for version, path in discover_migrations(migrations_dir):
        if version in already_applied:
            continue
        conn.executescript(path.read_text(encoding="utf-8"))
        conn.execute(
            "INSERT OR IGNORE INTO schema_version (version, applied_at) VALUES (?, ?)",
            (version, clock.now_iso()),
        )


def seed_agents(conn: sqlite3.Connection, clock: Clock) -> None:
    """Inserts the five LLM personas and the baseline agent if they do not already exist."""
    now = clock.now_iso()
    for agent_id, name, philosophy, kind in AGENTS:
        conn.execute(
            """
            INSERT OR IGNORE INTO agents
                (id, name, philosophy, kind, starting_cash_paise, cash_paise, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                agent_id,
                name,
                philosophy,
                kind,
                settings.INITIAL_CASH_PER_AGENT_PAISE,
                settings.INITIAL_CASH_PER_AGENT_PAISE,
                now,
                now,
            ),
        )


def init_db(conn: sqlite3.Connection, clock: Clock = None) -> None:
    """Applies migrations then seeds agents. Safe to call more than once on the same connection."""
    clock = clock or SystemClock()
    apply_migrations(conn, clock)
    seed_agents(conn, clock)


def main() -> None:
    conn = get_connection(settings.PORTFOLIO_DB_PATH)
    try:
        init_db(conn, SystemClock())
    finally:
        conn.close()


if __name__ == "__main__":
    main()
