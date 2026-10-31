"""
SQLite connection factory: WAL journal mode and a 5,000 ms busy timeout on every connection.
See Plan_v3 §1.5.
"""
import sqlite3

from settings import settings


def get_connection(db_path: str = None) -> sqlite3.Connection:
    """Opens a SQLite connection with WAL journal mode and the configured busy timeout."""
    path = db_path or settings.PORTFOLIO_DB_PATH
    conn = sqlite3.connect(path, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(f"PRAGMA busy_timeout={settings.DB_BUSY_TIMEOUT_MS}")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn
