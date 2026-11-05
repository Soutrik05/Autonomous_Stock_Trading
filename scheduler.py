"""
APScheduler process that calls the one-shot job entry points on their nightly/intraday schedule.
All schedule timings are in IST (Asia/Kolkata).
See Plan_v3 §1.4.
"""
import logging
import sqlite3
import sys
from zoneinfo import ZoneInfo
from apscheduler.schedulers.blocking import BlockingScheduler

from broker.expiry import expire_pending_orders
from broker.monitor import poll_once
from broker.quotes import LiveQuoteProvider
from broker.settlement import run_settlement
from features.builder import run as run_build_features
from core.clock import Clock, SystemClock
from core.database import get_connection
from ingestion.cli import run as run_ingestion
from watchlist.watchlist_refresh import run as run_watchlist_refresh
from scripts.backup import backup_portfolio_db, upload_backup_to_s3
from settings import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("scheduler")
IST = ZoneInfo("Asia/Kolkata")


def job_intraday_monitor() -> None:
    """Intraday monitor: polls pending orders and open positions every 10 min (09:20-15:20)."""
    clock = SystemClock()
    conn = get_connection(settings.PORTFOLIO_DB_PATH)
    try:
        quote_provider = LiveQuoteProvider(conn)
        res = poll_once(conn, clock, quote_provider)
        logger.info("Intraday monitor poll: %s", res)
    except Exception as exc:
        logger.exception("Intraday monitor poll failed: %s", exc)
    finally:
        conn.close()


def job_order_expiry() -> None:
    """15:30 IST: Marks unfilled pending orders as expired."""
    clock = SystemClock()
    conn = get_connection(settings.PORTFOLIO_DB_PATH)
    try:
        res = expire_pending_orders(conn, clock)
        logger.info("Order expiry: %s", res)
    except Exception as exc:
        logger.exception("Order expiry failed: %s", exc)
    finally:
        conn.close()


def job_settlement() -> None:
    """15:35 IST: Updates positions.last_price, computes daily NAV and records Nifty 500 close."""
    clock = SystemClock()
    conn = get_connection(settings.PORTFOLIO_DB_PATH)
    try:
        quote_provider = LiveQuoteProvider(conn)
        res = run_settlement(conn, clock, quote_provider=quote_provider)
        logger.info("Settlement and daily NAV: %s", res)
    except Exception as exc:
        logger.exception("Settlement failed: %s", exc)
    finally:
        conn.close()


def is_nightly_pipeline_complete(conn: sqlite3.Connection, run_date: str) -> bool:
    """Checks whether ingestion was skipped as holiday or watchlist refresh succeeded."""
    try:
        row = conn.execute(
            "SELECT status FROM pipeline_runs WHERE job = 'watchlist' AND run_date = ?",
            (run_date,),
        ).fetchone()
        if row and row["status"] == "SUCCESS":
            return True

        ingest_row = conn.execute(
            "SELECT status FROM pipeline_runs WHERE job = 'ingestion' AND run_date = ?",
            (run_date,),
        ).fetchone()
        if ingest_row and ingest_row["status"] == "SKIPPED_HOLIDAY":
            return True

        return False
    except sqlite3.OperationalError:
        return False


def execute_nightly_pipeline_pass(clock: Clock, conn: sqlite3.Connection, run_date: str) -> str:
    """
    Executes one full pass of the data pipeline: ingestion -> features -> watchlist.
    Returns SUCCESS, SKIPPED_HOLIDAY, or FAILED.
    """
    from scripts.init_db import init_db
    init_db(conn, clock)

    logger.info("Executing nightly ingestion for %s...", run_date)
    ingestion_status = run_ingestion(clock=clock, portfolio_conn=conn)
    logger.info("Ingestion status: %s", ingestion_status)

    if ingestion_status == "SKIPPED_HOLIDAY":
        logger.info("Market closed on %s (SKIPPED_HOLIDAY); pipeline complete.", run_date)
        return "SKIPPED_HOLIDAY"

    if ingestion_status != "SUCCESS":
        logger.warning("Ingestion did not succeed (%s); halting pass.", ingestion_status)
        return "FAILED"

    logger.info("Building feature snapshots for %s...", run_date)
    features_res = run_build_features(as_of_date=run_date, clock=clock, portfolio_conn=conn)
    logger.info("Feature snapshots result: %s", features_res)

    features_status = features_res.get("status") if isinstance(features_res, dict) else features_res
    if features_status != "SUCCESS":
        logger.warning("Feature building did not succeed (%s); halting pass.", features_res)
        return "FAILED"

    logger.info("Refreshing watchlists for %s...", run_date)
    watchlist_res = run_watchlist_refresh(as_of_date=run_date, agent_id="all", clock=clock, portfolio_conn=conn)
    logger.info("Watchlist refresh result: %s", watchlist_res)

    if isinstance(watchlist_res, dict) and watchlist_res.get("status") != "SUCCESS":
        return "FAILED"

    logger.info("Computing forward returns for past decisions as of %s...", run_date)
    try:
        from evaluation.forward_returns import compute_forward_returns
        ohlcv_conn = get_connection(settings.OHLCV_DB_PATH)
        try:
            fwd_res = compute_forward_returns(portfolio_conn=conn, ohlcv_conn=ohlcv_conn, clock=clock)
            logger.info("Forward returns result: %s", fwd_res)
        finally:
            ohlcv_conn.close()
    except Exception as exc:
        logger.warning("Failed to compute forward returns: %s", exc)

    return "SUCCESS"


def job_nightly_ingestion_and_features() -> None:
    """20:00 IST: Primary nightly pipeline pass."""
    clock = SystemClock()
    conn = get_connection(settings.PORTFOLIO_DB_PATH)
    try:
        from scripts.init_db import init_db
        init_db(conn, clock)

        run_date = clock.today().isoformat()
        if is_nightly_pipeline_complete(conn, run_date):
            logger.info("Nightly pipeline already completed for %s; skipping 20:00 pass.", run_date)
            return

        status = execute_nightly_pipeline_pass(clock, conn, run_date)
        if status == "FAILED":
            logger.warning(
                "Nightly pipeline failed initial 20:00 pass. Automated retries scheduled for 20:30 and 21:00 IST."
            )
    except Exception as exc:
        logger.exception("Nightly pipeline 20:00 pass encountered unhandled error: %s", exc)
    finally:
        conn.close()


def job_nightly_pipeline_retry(checkpoint_label: str, is_final: bool = False) -> None:
    """Checkpoint retry job scheduled at 20:30 and 21:00 IST."""
    from notifications.alerts import record_pipeline_failure

    clock = SystemClock()
    conn = get_connection(settings.PORTFOLIO_DB_PATH)
    try:
        run_date = clock.today().isoformat()
        if is_nightly_pipeline_complete(conn, run_date):
            logger.info("Nightly pipeline already complete for %s; skipping checkpoint %s.", run_date, checkpoint_label)
            return

        logger.info("Starting nightly pipeline retry checkpoint: %s for %s...", checkpoint_label, run_date)
        status = execute_nightly_pipeline_pass(clock, conn, run_date)

        if status == "SUCCESS":
            logger.info("Nightly pipeline recovered successfully at checkpoint %s for %s.", checkpoint_label, run_date)
        elif status == "FAILED":
            logger.warning("Nightly pipeline failed retry at checkpoint %s for %s.", checkpoint_label, run_date)
            if is_final:
                detail = f"All nightly pipeline retries exhausted up to checkpoint {checkpoint_label} for {run_date}."
                record_pipeline_failure(conn, "nightly_pipeline", run_date, detail, clock)
    except Exception as exc:
        logger.exception("Nightly pipeline retry checkpoint %s failed with error: %s", checkpoint_label, exc)
        if is_final:
            record_pipeline_failure(conn, "nightly_pipeline", run_date, str(exc), clock)
    finally:
        conn.close()


def job_retry_2030() -> None:
    job_nightly_pipeline_retry("20:30_checkpoint", is_final=False)


def job_retry_2100() -> None:
    job_nightly_pipeline_retry("21:00_checkpoint", is_final=True)


def check_and_run_startup_catchup(clock: Clock, conn: sqlite3.Connection) -> None:
    """Checks whether the service started after 20:00 on a trading day with an incomplete pipeline."""
    today = clock.today()
    if today.weekday() >= 5:  # Weekend
        return

    now_dt = clock.now()
    if now_dt.hour >= 20:
        run_date = today.isoformat()
        if not is_nightly_pipeline_complete(conn, run_date):
            logger.info(
                "Startup catch-up: Nightly pipeline not yet completed for %s. Executing catch-up pass...",
                run_date,
            )
            execute_nightly_pipeline_pass(clock, conn, run_date)


def job_nightly_backup() -> None:
    """21:45 IST: SQLite backup API snapshot of portfolio.db."""
    try:
        clock = SystemClock()
        res = backup_portfolio_db(clock=clock)
        logger.info("Nightly portfolio.db backup: %s", res)
        if res:
            upload_backup_to_s3(res)
    except Exception as exc:
        logger.exception("Nightly backup failed: %s", exc)


def job_agent_runner() -> None:
    """22:00 IST: Runs agent decisions for all 5 LLM personas and baseline."""
    from agents.personas import all_personas
    from agents.runner import run as run_agents

    clock = SystemClock()
    conn = get_connection(settings.PORTFOLIO_DB_PATH)
    try:
        run_date = clock.today().isoformat()
        logger.info("Running agent decisions for %s...", run_date)
        agent_ids = [p.id for p in all_personas()] + ["baseline-simons-rules"]
        res = run_agents(agent_ids, as_of_date=run_date, clock=clock, portfolio_conn=conn)
        logger.info("Agent decisions result: %s", res)
    except Exception as exc:
        logger.exception("Agent runner failed: %s", exc)
    finally:
        conn.close()


def build_scheduler() -> BlockingScheduler:
    """Constructs the configured APScheduler with all IST jobs per Plan_v3 §1.4."""
    scheduler = BlockingScheduler(timezone=IST)

    # 1. Intraday monitor: every 10 min from 09:20 to 15:20 on Mon-Fri
    # In cron syntax: hour 9 (min 20-50), hour 10-14 (every 10m), hour 15 (min 0-20)
    scheduler.add_job(
        job_intraday_monitor,
        "cron",
        day_of_week="mon-fri",
        hour="9",
        minute="20,30,40,50",
        id="intraday_monitor_morning",
    )
    scheduler.add_job(
        job_intraday_monitor,
        "cron",
        day_of_week="mon-fri",
        hour="10-14",
        minute="*/10",
        id="intraday_monitor_midday",
    )
    scheduler.add_job(
        job_intraday_monitor,
        "cron",
        day_of_week="mon-fri",
        hour="15",
        minute="0,10,20",
        id="intraday_monitor_afternoon",
    )

    # 2. Expiry at 15:30 IST Mon-Fri
    scheduler.add_job(
        job_order_expiry,
        "cron",
        day_of_week="mon-fri",
        hour=15,
        minute=30,
        id="order_expiry",
    )

    # 3. Settlement and Daily NAV at 15:35 IST Mon-Fri
    scheduler.add_job(
        job_settlement,
        "cron",
        day_of_week="mon-fri",
        hour=15,
        minute=35,
        id="settlement",
    )

    # 4. Ingestion, features, watchlist at 20:00 IST Mon-Fri
    scheduler.add_job(
        job_nightly_ingestion_and_features,
        "cron",
        day_of_week="mon-fri",
        hour=20,
        minute=0,
        id="nightly_ingestion",
    )

    # 4b. Pipeline retry checkpoint 1 at 20:30 IST Mon-Fri
    scheduler.add_job(
        job_retry_2030,
        "cron",
        day_of_week="mon-fri",
        hour=20,
        minute=30,
        id="nightly_pipeline_retry_2030",
    )

    # 4c. Pipeline retry checkpoint 2 (final) at 21:00 IST Mon-Fri
    scheduler.add_job(
        job_retry_2100,
        "cron",
        day_of_week="mon-fri",
        hour=21,
        minute=0,
        id="nightly_pipeline_retry_2100",
    )

    # 5. Backup at 21:45 IST daily
    scheduler.add_job(
        job_nightly_backup,
        "cron",
        hour=21,
        minute=45,
        id="nightly_backup",
    )

    # 6. Agent decision runner at 22:00 IST Mon-Fri
    scheduler.add_job(
        job_agent_runner,
        "cron",
        day_of_week="mon-fri",
        hour=22,
        minute=0,
        id="agent_runner",
    )

    return scheduler


def main() -> None:
    logger.info("Initializing StockMinds APScheduler process (Asia/Kolkata)...")
    clock = SystemClock()

    # Bootstrap schema migrations and seed agents if database is empty/uninitialized
    conn = get_connection(settings.PORTFOLIO_DB_PATH)
    try:
        from scripts.init_db import init_db
        init_db(conn, clock)
        logger.info("Portfolio database verified/initialized at %s", settings.PORTFOLIO_DB_PATH)
        check_and_run_startup_catchup(clock, conn)
    except Exception as exc:
        logger.error("Failed to initialize or catch up portfolio database: %s", exc)
    finally:
        conn.close()

    scheduler = build_scheduler()
    for job in scheduler.get_jobs():
        logger.info("Registered job %s: trigger=%s", job.id, job.trigger)

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")


if __name__ == "__main__":
    main()
