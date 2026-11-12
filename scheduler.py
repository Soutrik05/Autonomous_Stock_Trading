"""
APScheduler process that calls the one-shot job entry points on their nightly/intraday schedule.
All schedule timings are in IST (Asia/Kolkata).
See Plan_v3 §1.4.
"""

import logging
import signal
import sqlite3
import sys
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler

from broker.expiry import expire_pending_orders
from broker.monitor import poll_once
from broker.quotes import LiveQuoteProvider
from broker.settlement import run_settlement
from core.clock import Clock, SystemClock
from core.config import settings
from core.database import get_connection
from features.builder import run as run_build_features
from ingestion.cli import run as run_ingestion
from llm.client import LLMConfigError, build_provider, require_setting
from scripts.backup import backup_portfolio_db
from watchlist.watchlist_refresh import run as run_watchlist_refresh

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
    """22:00 IST: Primary nightly pipeline pass."""
    clock = SystemClock()
    conn = get_connection(settings.PORTFOLIO_DB_PATH)
    try:
        from scripts.init_db import init_db

        init_db(conn, clock)

        run_date = clock.today().isoformat()
        if is_nightly_pipeline_complete(conn, run_date):
            logger.info("Nightly pipeline already completed for %s; skipping 22:00 pass.", run_date)
            return

        status = execute_nightly_pipeline_pass(clock, conn, run_date)
        if status == "FAILED":
            logger.warning(
                "Nightly pipeline failed initial 22:00 pass. Automated retry scheduled for 22:30 IST."
            )
    except Exception as exc:
        logger.exception("Nightly pipeline 22:00 pass encountered unhandled error: %s", exc)
    finally:
        conn.close()


def job_nightly_pipeline_retry(checkpoint_label: str, is_final: bool = False) -> None:
    """Checkpoint retry job scheduled at 22:30 IST."""
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


def job_retry_2230() -> None:
    job_nightly_pipeline_retry("22:30_checkpoint", is_final=True)



def cleanup_orphaned_pipeline_runs(conn: sqlite3.Connection, clock: Clock) -> None:
    """Detects and resolves dangling RUNNING states left by ungraceful kills or container crashes."""
    try:
        rows = conn.execute(
            "SELECT job, run_date, started_at FROM pipeline_runs WHERE status = 'RUNNING'"
        ).fetchall()
        for r in rows:
            conn.execute(
                "UPDATE pipeline_runs SET status = 'INTERRUPTED', finished_at = ?, detail = ? "
                "WHERE job = ? AND run_date = ? AND status = 'RUNNING'",
                (
                    clock.now_iso(),
                    "Process interrupted: host restarted or container terminated before completion",
                    r["job"],
                    r["run_date"],
                ),
            )
        if rows:
            logger.warning("Auto-recovered %d orphaned RUNNING job(s) as INTERRUPTED.", len(rows))
    except sqlite3.OperationalError:
        pass


def register_signal_handlers(scheduler: BlockingScheduler) -> None:
    """Intercepts SIGTERM and SIGINT from Docker to clean up running states gracefully on shutdown."""
    def _shutdown(signum, frame):
        sig_name = "SIGTERM" if signum == signal.SIGTERM else "SIGINT"
        logger.warning("Received %s. Shutting down APScheduler and cleaning active jobs...", sig_name)
        try:
            conn = get_connection(settings.PORTFOLIO_DB_PATH)
            clock = SystemClock()
            conn.execute(
                "UPDATE pipeline_runs SET status = 'INTERRUPTED', finished_at = ?, detail = ? WHERE status = 'RUNNING'",
                (clock.now_iso(), f"Process interrupted: container shutdown ({sig_name})"),
            )
            conn.close()
        except Exception as exc:
            logger.exception("Failed to update pipeline_runs on %s: %s", sig_name, exc)
        finally:
            try:
                scheduler.shutdown(wait=False)
            except Exception:
                pass
            sys.exit(0)

    try:
        signal.signal(signal.SIGTERM, _shutdown)
        signal.signal(signal.SIGINT, _shutdown)
    except Exception as sig_err:
        logger.warning("Could not register POSIX signal handlers: %s", sig_err)


def ensure_database_bootstrapped(clock: Clock, conn: sqlite3.Connection) -> None:
    """Verifies that schema, seed agents, symbols master, and market calendar exist."""
    from scripts.init_db import init_db

    init_db(conn, clock)
    logger.info("Portfolio database schema verified at %s", settings.PORTFOLIO_DB_PATH)
    cleanup_orphaned_pipeline_runs(conn, clock)

    # 1. Check symbols master
    try:
        n_symbols = conn.execute("SELECT COUNT(*) FROM symbols WHERE is_active = 1").fetchone()[0]
    except sqlite3.OperationalError:
        n_symbols = 0

    if n_symbols == 0:
        logger.info("Symbols table is empty. Auto-bootstrapping Nifty 500 constituents...")
        try:
            from scripts.build_symbol_master import main as build_symbols_main

            build_symbols_main()
            logger.info("Symbol master bootstrap complete.")
        except Exception as sym_err:
            logger.exception("Failed to auto-seed symbol master: %s", sym_err)

    # 2. Check market calendar
    try:
        n_cal = conn.execute("SELECT COUNT(*) FROM market_calendar").fetchone()[0]
    except sqlite3.OperationalError:
        n_cal = 0

    if n_cal == 0:
        logger.info("Market calendar is empty. Auto-seeding market calendar...")
        try:
            from core.calendar import seed_calendar
            from ingestion.upstox_client import UpstoxClient

            client = UpstoxClient()
            seed_calendar(client, conn)
            logger.info("Market calendar seeded successfully.")
        except Exception as cal_err:
            logger.warning("Could not auto-seed market calendar: %s", cal_err)


def check_and_run_startup_catchup(clock: Clock, conn: sqlite3.Connection) -> None:
    """Checks whether the service started after 20:00 on a trading day with an incomplete pipeline,
    or if historical OHLCV data has 0 candles."""
    today = clock.today()
    if today.weekday() >= 5:  # Weekend
        return

    run_date = today.isoformat()

    needs_initial_ingest = False
    try:
        ohlcv_conn = get_connection(settings.OHLCV_DB_PATH)
        try:
            ohlcv_conn.execute(
                "CREATE TABLE IF NOT EXISTS ohlcv (ticker TEXT, trade_date TEXT, open REAL, high REAL, low REAL, close REAL, volume INTEGER, PRIMARY KEY (ticker, trade_date))"
            )
            n_candles = ohlcv_conn.execute("SELECT COUNT(*) FROM ohlcv").fetchone()[0]
            if n_candles == 0:
                logger.info("OHLCV database has 0 candles; initial ingestion is required.")
                needs_initial_ingest = True
        finally:
            ohlcv_conn.close()
    except Exception as ohlcv_err:
        logger.warning("Error inspecting OHLCV database: %s; flagging initial ingest.", ohlcv_err)
        needs_initial_ingest = True

    now_dt = clock.now()
    if needs_initial_ingest or (now_dt.hour >= 22 and not is_nightly_pipeline_complete(conn, run_date)):
        logger.info(
            "Startup catch-up: Executing ingestion and pipeline pass for %s (needs_initial=%s)...",
            run_date,
            needs_initial_ingest,
        )
        execute_nightly_pipeline_pass(clock, conn, run_date)


def job_nightly_backup() -> None:
    """23:45 IST: SQLite backup API snapshot of portfolio.db after daily agent runs and heuristics."""
    try:
        clock = SystemClock()
        res = backup_portfolio_db(clock=clock)
        logger.info("Nightly portfolio.db backup: %s", res)
    except Exception as exc:
        logger.exception("Nightly backup failed: %s", exc)


def job_agent_runner() -> None:
    """23:00 IST: Runs agent decisions for all 5 LLM personas and baseline."""
    from agents.personas import all_personas
    from agents.runner import run as run_agents
    from core.calendar import is_trading_day

    clock = SystemClock()
    conn = get_connection(settings.PORTFOLIO_DB_PATH)
    try:
        today_obj = clock.today()
        run_date = today_obj.isoformat()
        if not is_trading_day(conn, today_obj):
            logger.info("Market closed on %s (SKIPPED_HOLIDAY); skipping agent runner pass.", run_date)
            return
        logger.info("Running agent decisions for %s...", run_date)
        agent_ids = [p.id for p in all_personas()] + [
            "baseline-simons-rules",
            "baseline-varsity-rules",
            "baseline-lynch-rules",
            "baseline-marks-rules",
            "baseline-rj-rules",
        ]
        res = run_agents(agent_ids, as_of_date=run_date, clock=clock, portfolio_conn=conn)
        logger.info("Agent decisions result: %s", res)
    except Exception as exc:
        logger.exception("Agent runner failed: %s", exc)
    finally:
        conn.close()


def _is_agent_runner_complete(conn: sqlite3.Connection, run_date: str) -> bool:
    """Mirrors is_nightly_pipeline_complete's pattern, for the 22:00 agent-runner step: the
    'agents' pipeline_runs row is upserted by agents.runner.run_one_agent for every agent it
    processes that date, so a SUCCESS status there means the last agent in that run finished
    cleanly."""
    try:
        row = conn.execute(
            "SELECT status FROM pipeline_runs WHERE job = 'agents' AND run_date = ?",
            (run_date,),
        ).fetchone()
        return bool(row and row["status"] == "SUCCESS")
    except sqlite3.OperationalError:
        return False


def job_heuristic_nightly() -> None:
    """23:30 IST: nightly heuristic trigger evaluation and lifecycle update, after
    job_agent_runner, followed by forensics post-exit enrichment as a second, independently
    isolated step (one failing must never stop the other). Skipped entirely (not failed) if
    that day's agent-runner step hasn't finished."""
    from notifications.alerts import record_pipeline_failure

    clock = SystemClock()
    conn = get_connection(settings.PORTFOLIO_DB_PATH)
    run_date = clock.today().isoformat()
    try:
        if not _is_agent_runner_complete(conn, run_date):
            logger.info("Agent runner not yet complete for %s; skipping heuristic nightly pass.", run_date)
            return

        try:
            from learning.memory_manager import run_nightly as run_heuristic_nightly

            res = run_heuristic_nightly(conn, clock, run_date)
            logger.info("Heuristic nightly pass: %s", res)
            if res.get("errors"):
                record_pipeline_failure(conn, "heuristic_nightly", run_date, str(res["errors"]), clock)
        except Exception as exc:
            logger.exception("Heuristic nightly pass failed: %s", exc)
            record_pipeline_failure(conn, "heuristic_nightly", run_date, str(exc), clock)

        try:
            from learning.forensics import enrich_post_exit

            updated = enrich_post_exit(conn, clock, run_date)
            logger.info("Post-exit enrichment: %s position(s) updated.", updated)
        except Exception as exc:
            logger.exception("Post-exit enrichment failed: %s", exc)
            record_pipeline_failure(conn, "post_exit_enrichment", run_date, str(exc), clock)
    except Exception as exc:
        logger.exception("Heuristic nightly job failed before its steps could run: %s", exc)
        record_pipeline_failure(conn, "heuristic_nightly", run_date, str(exc), clock)
    finally:
        conn.close()


def job_weekly_reflection() -> None:
    """Sunday 10:00 IST: weekly heuristic-generation reflection for every LLM persona (the
    baseline agent has no LLM and is skipped by learning.engine.run itself). Builds its
    primary/fallback LLM client pair the same way job_agent_runner does, from the dedicated
    REFLECTION_LLM_* settings."""
    from notifications.alerts import record_pipeline_failure

    clock = SystemClock()
    conn = get_connection(settings.PORTFOLIO_DB_PATH)
    run_date = clock.today().isoformat()
    try:
        primary = build_provider(
            settings.REFLECTION_LLM_PROVIDER,
            model=require_setting(settings.REFLECTION_LLM_MODEL, "REFLECTION_LLM_MODEL"),
        )
        fallback = None
        try:
            fallback = build_provider(
                settings.REFLECTION_LLM_FALLBACK_PROVIDER,
                model=require_setting(settings.REFLECTION_LLM_FALLBACK_MODEL, "REFLECTION_LLM_FALLBACK_MODEL"),
            )
        except LLMConfigError as exc:
            logger.warning(
                "Weekly reflection fallback provider %r unavailable (%s); continuing with %r only, no fallback.",
                settings.REFLECTION_LLM_FALLBACK_PROVIDER,
                exc,
                settings.REFLECTION_LLM_PROVIDER,
            )

        from learning.engine import run as run_reflection

        res = run_reflection(conn, clock, llm_client=primary, fallback_client=fallback)
        logger.info("Weekly reflection result: %s", res)
        failed_agents = {aid: r for aid, r in res.get("agents", {}).items() if r.get("status") == "ERROR"}
        if failed_agents:
            record_pipeline_failure(conn, "weekly_reflection", run_date, str(failed_agents), clock)
    except Exception as exc:
        logger.exception("Weekly reflection failed: %s", exc)
        record_pipeline_failure(conn, "weekly_reflection", run_date, str(exc), clock)
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

    # 4. Ingestion, features, watchlist at 22:00 IST Mon-Fri
    scheduler.add_job(
        job_nightly_ingestion_and_features,
        "cron",
        day_of_week="mon-fri",
        hour=22,
        minute=0,
        id="nightly_ingestion",
    )

    # 4b. Pipeline retry checkpoint (single & final) at 22:30 IST Mon-Fri
    scheduler.add_job(
        job_retry_2230,
        "cron",
        day_of_week="mon-fri",
        hour=22,
        minute=30,
        id="nightly_pipeline_retry_2230",
    )

    # 5. Agent decision runner at 23:00 IST Mon-Fri
    scheduler.add_job(
        job_agent_runner,
        "cron",
        day_of_week="mon-fri",
        hour=23,
        minute=0,
        id="agent_runner",
    )

    # 6. Nightly heuristic trigger evaluation at 23:30 IST Mon-Fri, after the agent runner
    scheduler.add_job(
        job_heuristic_nightly,
        "cron",
        day_of_week="mon-fri",
        hour=23,
        minute=30,
        id="heuristic_nightly",
    )

    # 7. Backup at 23:45 IST daily (captures all daily settlement, decisions, and heuristics)
    scheduler.add_job(
        job_nightly_backup,
        "cron",
        hour=23,
        minute=45,
        id="nightly_backup",
    )

    # 8. Weekly reflection (heuristic generation) at 10:00 IST on Sunday
    scheduler.add_job(
        job_weekly_reflection,
        "cron",
        day_of_week="sun",
        hour=10,
        minute=0,
        id="weekly_reflection",
    )

    return scheduler


def main() -> None:
    logger.info("Initializing StockMinds APScheduler process (Asia/Kolkata)...")
    clock = SystemClock()

    # Bootstrap schema migrations and seed agents if database is empty/uninitialized
    conn = get_connection(settings.PORTFOLIO_DB_PATH)
    try:
        ensure_database_bootstrapped(clock, conn)
        check_and_run_startup_catchup(clock, conn)
    except Exception as exc:
        logger.error("Failed to initialize, bootstrap, or catch up portfolio database: %s", exc)
    finally:
        conn.close()

    scheduler = build_scheduler()
    register_signal_handlers(scheduler)
    for job in scheduler.get_jobs():
        logger.info("Registered job %s: trigger=%s", job.id, job.trigger)

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")


if __name__ == "__main__":
    main()
