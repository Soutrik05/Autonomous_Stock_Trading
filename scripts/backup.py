"""
Nightly backup of portfolio.db to backups/ using the SQLite backup API; keeps the last 14 copies.
See Plan_v3 §1.4, §1.5.
"""

import argparse
import logging
import sqlite3
import sys
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from core.clock import Clock, SystemClock
from core.config import settings

logger = logging.getLogger(__name__)


def backup_portfolio_db(
    source_path: str | None = None,
    backup_dir: str | None = None,
    clock: Clock | None = None,
    max_copies: int = 14,
) -> str | None:
    """Uses SQLite backup API to create an atomic snapshot of portfolio.db, then prunes older backups."""
    clock = clock or SystemClock()
    src = Path(source_path or settings.PORTFOLIO_DB_PATH)
    if not src.exists():
        logger.warning("Source database %s does not exist; skipping backup.", src)
        return None

    b_dir = Path(backup_dir or settings.BACKUP_DIR)
    b_dir.mkdir(parents=True, exist_ok=True)

    today_str = clock.today().isoformat()
    dest = b_dir / f"portfolio_{today_str}.db"

    src_conn = sqlite3.connect(str(src))
    dst_conn = sqlite3.connect(str(dest))
    try:
        src_conn.backup(dst_conn)
    finally:
        dst_conn.close()
        src_conn.close()

    # Prune older backups beyond max_copies
    existing_backups = sorted(b_dir.glob("portfolio_*.db"), key=lambda p: p.name)
    if len(existing_backups) > max_copies:
        for to_delete in existing_backups[:-max_copies]:
            try:
                to_delete.unlink()
            except OSError as exc:
                logger.warning("Failed to prune old backup %s: %s", to_delete, exc)

    return str(dest)


def main() -> None:
    parser = argparse.ArgumentParser(description="Nightly portfolio.db backup.")
    parser.add_argument("--source", default=None, help="Source db path")
    parser.add_argument("--backup-dir", default=None, help="Backup destination folder")
    args = parser.parse_args()

    out = backup_portfolio_db(source_path=args.source, backup_dir=args.backup_dir)
    print(f"backup: {out}")


if __name__ == "__main__":
    main()
