"""
SQLite connection factory: WAL journal mode and a 5,000 ms busy timeout on every connection.
See Plan_v3 §1.5.
"""

import sqlite3

from core.config import settings


def get_connection(db_path: str = None) -> sqlite3.Connection:
    """Opens a SQLite connection with WAL journal mode, 64MB cache, memory temp store, and mmap."""
    path = db_path or settings.PORTFOLIO_DB_PATH
    conn = sqlite3.connect(path, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-64000")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute("PRAGMA mmap_size=268435456")
    conn.execute(f"PRAGMA busy_timeout={settings.DB_BUSY_TIMEOUT_MS}")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn
