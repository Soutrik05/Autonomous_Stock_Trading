"""
Backfills dcf_iv_share in storage/market/fundamental.db using existing raw_json
and compute_dcf_intrinsic_value from ingestion.sync_fundamentals.
"""

import json
import logging
import sqlite3
import sys
from pathlib import Path

# Add root and src to sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir / "src"))
sys.path.insert(0, str(root_dir))

from core.config import settings
from ingestion.sync_fundamentals import parse_fundamental_metrics

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("backfill_dcf")


def run_backfill(dry_run: bool = False) -> dict:
    fund_db = settings.FUNDAMENTAL_DB_PATH
    port_db = settings.PORTFOLIO_DB_PATH
    ohlcv_db = settings.OHLCV_DB_PATH

    logger.info("Opening databases: %s, %s, %s", fund_db, port_db, ohlcv_db)
    fconn = sqlite3.connect(fund_db)
    pconn = sqlite3.connect(port_db)
    oconn = sqlite3.connect(ohlcv_db)

    # Ensure dcf_iv_share column exists in fundamental_ratios
    cols = [r[1] for r in fconn.execute("PRAGMA table_info(fundamental_ratios)").fetchall()]
    if "dcf_iv_share" not in cols:
        logger.info("Adding dcf_iv_share column to fundamental_ratios...")
        fconn.execute("ALTER TABLE fundamental_ratios ADD COLUMN dcf_iv_share REAL")

    # Load sector mappings
    sectors = dict(pconn.execute("SELECT ticker, sector FROM symbols").fetchall())

    # Load all rows from fundamental_ratios
    rows = fconn.execute("SELECT ticker, as_of_date, raw_json FROM fundamental_ratios").fetchall()
    logger.info("Found %d rows in fundamental_ratios", len(rows))

    total = len(rows)
    non_fin = 0
    calculated = 0
    skipped_fin = 0
    no_raw = 0

    updates = []
    for ticker, as_of_date, raw_json in rows:
        sector = sectors.get(ticker, "")
        sec_lower = sector.strip().lower()
        if sec_lower in ("financial services", "financials", "banking", "banks", "nbfc"):
            skipped_fin += 1
            continue

        non_fin += 1
        if not raw_json:
            no_raw += 1
            continue

        try:
            data = json.loads(raw_json)
        except Exception as e:
            logger.warning("Failed to parse raw_json for %s: %s", ticker, e)
            continue

        # Get latest available close price for shares outstanding estimate
        cp_row = oconn.execute(
            "SELECT close FROM ohlcv WHERE ticker = ? ORDER BY trade_date DESC LIMIT 1",
            (ticker,),
        ).fetchone()
        current_price = float(cp_row[0]) if cp_row and cp_row[0] else 100.0

        key_ratios = data.get("key_ratios", [])
        income_stmt = data.get("income_statement", {})
        balance_sheet = data.get("balance_sheet", {})
        cash_flow = data.get("cash_flow", {})
        share_holdings = data.get("share_holdings", [])

        res = parse_fundamental_metrics(
            ticker=ticker,
            as_of_date=as_of_date or "2026-01-01",
            key_ratios=key_ratios,
            income_stmt=income_stmt,
            balance_sheet=balance_sheet,
            cash_flow=cash_flow,
            share_holdings=share_holdings,
            sector=sector,
            current_price=current_price,
        )

        dcf_iv = res.get("dcf_iv_share")
        if dcf_iv is not None and dcf_iv > 0:
            calculated += 1
            updates.append((dcf_iv, ticker))

    logger.info(
        "Summary: total=%d, non_fin=%d, skipped_fin=%d, no_raw=%d, calculated=%d",
        total,
        non_fin,
        skipped_fin,
        no_raw,
        calculated,
    )

    if not dry_run and updates:
        logger.info("Writing %d dcf_iv_share updates to %s...", len(updates), fund_db)
        fconn.executemany(
            "UPDATE fundamental_ratios SET dcf_iv_share = ? WHERE ticker = ?",
            updates,
        )
        fconn.commit()
        logger.info("Backfill committed successfully.")

        # Update existing feature_snapshots in portfolio.db
        logger.info("Updating dcf_discount_pct in portfolio.db feature_snapshots...")
        iv_by_ticker = {t: iv for iv, t in updates}
        snap_rows = pconn.execute(
            "SELECT ticker, as_of_date, schema_version, features_json FROM feature_snapshots"
        ).fetchall()
        snap_updates = []
        for ticker, as_of_date, schema_version, f_json in snap_rows:
            if ticker in iv_by_ticker and f_json:
                try:
                    f_dict = json.loads(f_json)
                    close_p = f_dict.get("close")
                    iv_share = iv_by_ticker[ticker]
                    if close_p and close_p > 0 and iv_share > 0:
                        f_dict["dcf_discount_pct"] = round(((iv_share - close_p) / close_p) * 100.0, 2)
                        snap_updates.append((json.dumps(f_dict), ticker, as_of_date, schema_version))
                except Exception:
                    pass

        if snap_updates:
            logger.info("Updating %d feature_snapshots with dcf_discount_pct...", len(snap_updates))
            pconn.executemany(
                "UPDATE feature_snapshots SET features_json = ? WHERE ticker = ? AND as_of_date = ? AND schema_version = ?",
                snap_updates,
            )
            pconn.commit()
            logger.info("portfolio.db feature_snapshots updated successfully.")

    fconn.close()
    pconn.close()
    oconn.close()

    return {
        "total": total,
        "non_fin": non_fin,
        "calculated": calculated,
        "skipped_fin": skipped_fin,
    }


if __name__ == "__main__":
    run_backfill(dry_run=False)
