"""
APScheduler process that calls the one-shot job entry points on their nightly/intraday schedule.
All schedule timings are in IST (Asia/Kolkata).
See Plan_v3 §1.4.
"""
import logging
import sys
from zoneinfo import ZoneInfo
from apscheduler.schedulers.blocking import BlockingScheduler

from broker.expiry import expire_pending_orders
from broker.monitor import poll_once
from broker.quotes import LiveQuoteProvider
from broker.settlement import run_settlement
from core.build_features import run as run_build_features
from core.clock import SystemClock
from core.database import get_connection
from ingestion.cli import run as run_ingestion
from precompute.watchlist_refresh import run as run_watchlist_refresh
from scripts.backup import backup_portfolio_db
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


def job_nightly_ingestion_and_features() -> None:
    """20:00 IST: Sequentially runs ingestion -> feature building -> watchlist refresh."""
    clock = SystemClock()
    conn = get_connection(settings.PORTFOLIO_DB_PATH)
    try:
        run_date = clock.today().isoformat()
        logger.info("Starting nightly ingestion for %s...", run_date)
        ingestion_status = run_ingestion(clock=clock, portfolio_conn=conn)
        logger.info("Ingestion status: %s", ingestion_status)

        if ingestion_status != "SUCCESS":
            logger.warning("Ingestion did not succeed (%s); halting nightly pipeline.", ingestion_status)
            return

        logger.info("Building feature snapshots for %s...", run_date)
        features_status = run_build_features(as_of_date=run_date, clock=clock, portfolio_conn=conn)
        logger.info("Feature snapshots status: %s", features_status)

        if features_status != "SUCCESS":
            logger.warning("Feature building did not succeed (%s); halting nightly pipeline.", features_status)
            return

        logger.info("Refreshing watchlists for %s...", run_date)
        # Week 1: Simons watchlist
        watchlist_res = run_watchlist_refresh(as_of_date=run_date, agent_id="simons", clock=clock, portfolio_conn=conn)
        logger.info("Watchlist refresh result: %s", watchlist_res)
    except Exception as exc:
        logger.exception("Nightly data pipeline failed: %s", exc)
    finally:
        conn.close()


def job_nightly_backup() -> None:
    """21:45 IST: SQLite backup API snapshot of portfolio.db."""
    try:
        clock = SystemClock()
        res = backup_portfolio_db(clock=clock)
        logger.info("Nightly portfolio.db backup: %s", res)
    except Exception as exc:
        logger.exception("Nightly backup failed: %s", exc)


def job_agent_runner() -> None:
    """22:00 IST: Runs agent decisions (LLM Simons and Rules Simons in Week 1)."""
    from agents.runner import run as run_agents

    clock = SystemClock()
    conn = get_connection(settings.PORTFOLIO_DB_PATH)
    try:
        run_date = clock.today().isoformat()
        logger.info("Running agent decisions for %s...", run_date)
        # In Week 1: Simons and Baseline Simons Rules
        res = run_agents(["simons", "baseline-simons-rules"], as_of_date=run_date, clock=clock, portfolio_conn=conn)
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
    scheduler = build_scheduler()
    for job in scheduler.get_jobs():
        logger.info("Registered job %s: trigger=%s", job.id, job.trigger)

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")


if __name__ == "__main__":
    main()
