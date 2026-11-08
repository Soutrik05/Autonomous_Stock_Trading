"""
Walk-forward simulation engine for StockMinds backtesting.
Executes multi-month simulations day-by-day with a SimulatedClock, isolated database,
daily candle matching, order expiry, settlement, forward return backfill,
and weekly Sunday reflection loops.
See Plan_v3 §5.6.
"""

import json
import logging
import sqlite3
import time
from collections.abc import Callable
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from agents.personas import all_personas
from agents.runner import run as run_agents
from backtest.broker_sim import resolve_day
from backtest.cache import CachedLLMClient, LLMResponseCache
from backtest.config import (
    CADENCE_TABLE,
    BacktestWindowConfig,
    get_all_trading_dates,
)
from backtest.data_provider import HistoricalDataProvider
from baselines.lynch_rules import run_baseline_lynch
from baselines.marks_rules import run_baseline_marks
from baselines.rj_rules import run_baseline_rj
from baselines.simons_rules import run_baseline_simons
from baselines.varsity_rules import run_baseline_varsity
from core.clock import Clock
from core.config import settings
from core.database import get_connection
from evaluation.comparison import (
    compare_lynch_vs_baseline,
    compare_marks_vs_baseline,
    compare_rj_vs_baseline,
    compare_simons_vs_baseline,
    compare_varsity_vs_baseline,
)
from evaluation.forward_returns import compute_forward_returns
from evaluation.performance import evaluate_all_agents
from features.builder import run as run_build_features
from learning.engine import run as run_reflection
from learning.forensics import enrich_post_exit
from learning.memory_manager import (
    evaluate_triggers_for_date,
    resolve_pending_applications,
    update_lifecycle,
)
from scripts.init_db import init_db
from watchlist.watchlist_refresh import run as run_watchlist_refresh

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")


class SimulatedClock(Clock):
    """Controllable clock for walk-forward historical simulations."""

    def __init__(self, current_dt: datetime):
        self._dt = current_dt

    def set_time(self, new_dt: datetime) -> None:
        self._dt = new_dt

    def now(self) -> datetime:
        return self._dt

    def today(self) -> date:
        return self._dt.date()

    def now_iso(self) -> str:
        return self._dt.isoformat()


def setup_isolated_backtest_db(
    sim_db_path: Path,
    source_port_db_path: Path,
    clock: Clock,
    resume: bool = False,
) -> sqlite3.Connection:
    """Creates a clean isolated SQLite database, or connects to an existing one in resume mode."""
    sim_db_path.parent.mkdir(parents=True, exist_ok=True)
    if sim_db_path.exists():
        if resume:
            # Reusing existing database state for checkpoint-resume
            conn = get_connection(sim_db_path)
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
            conn.execute("PRAGMA cache_size = -64000")
            conn.execute("PRAGMA temp_store = MEMORY")
            init_db(conn, clock)
            # Ensure symbols and calendar exist even in resume mode
            has_symbols = conn.execute("SELECT 1 FROM symbols LIMIT 1").fetchone()
            if not has_symbols and source_port_db_path.exists():
                src_conn = get_connection(source_port_db_path)
                try:
                    for table_name in ("symbols", "market_calendar"):
                        cols = [col[1] for col in src_conn.execute(f"PRAGMA table_info({table_name})").fetchall()]
                        if not cols:
                            continue
                        placeholders = ",".join("?" * len(cols))
                        col_list = ",".join(cols)
                        rows = src_conn.execute(f"SELECT {col_list} FROM {table_name}").fetchall()
                        for r in rows:
                            conn.execute(
                                f"INSERT OR REPLACE INTO {table_name} ({col_list}) VALUES ({placeholders})",
                                [r[c] for c in cols],
                            )
                    conn.commit()
                finally:
                    src_conn.close()
            return conn
        try:
            sim_db_path.unlink()
        except Exception:
            pass

    conn = get_connection(sim_db_path)
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA cache_size = -64000")
    conn.execute("PRAGMA temp_store = MEMORY")
    init_db(conn, clock)

    # Copy symbols and market calendar from source database
    if source_port_db_path.exists():
        src_conn = get_connection(source_port_db_path)
        try:
            for table_name in ("symbols", "market_calendar"):
                cols = [col[1] for col in src_conn.execute(f"PRAGMA table_info({table_name})").fetchall()]
                if not cols:
                    continue
                placeholders = ",".join("?" * len(cols))
                col_list = ",".join(cols)
                rows = src_conn.execute(f"SELECT {col_list} FROM {table_name}").fetchall()
                for r in rows:
                    conn.execute(
                        f"INSERT OR REPLACE INTO {table_name} ({col_list}) VALUES ({placeholders})",
                        [r[c] for c in cols],
                    )
            conn.commit()
        finally:
            src_conn.close()

    # Reset all agents to initial capital (settings.INITIAL_CASH_PER_AGENT_PAISE = Rs 5,00,000)
    conn.execute(
        "UPDATE agents SET starting_cash_paise = ?, cash_paise = ?",
        (settings.INITIAL_CASH_PER_AGENT_PAISE, settings.INITIAL_CASH_PER_AGENT_PAISE),
    )
    conn.commit()
    return conn


def is_persona_due_today(
    persona_id: str,
    session_idx: int,
    last_run_session: dict[str, int],
    current_regime: str,
    last_regime: str | None,
    remaining_sessions: int,
    has_target_reached_event: bool = False,
) -> bool:
    """
    Evaluates persona cadence rules:
    - Checks event-driven trigger (TARGET_REACHED on an open position wakes agent tonight).
    - Checks tail entry cutoff (remaining_sessions >= min_hold_days).
    - Checks cooldown sessions debounce guard.
    - Checks base interval or secondary triggers (e.g. regime transition).
    """
    if has_target_reached_event:
        return True

    rule = CADENCE_TABLE.get(persona_id)
    if not rule:
        return True

    # Tail entry cutoff guard: positions opened too close to window end cannot resolve minimum holding thesis
    cutoff = getattr(rule, "min_hold_days", rule.max_hold_days)
    if remaining_sessions < cutoff:
        return False

    last_run = last_run_session.get(persona_id, -999)
    sessions_since = session_idx - last_run

    # Cooldown debounce
    if sessions_since < rule.cooldown_sessions:
        return False

    # Secondary trigger (e.g. Marks VIX band transition)
    if rule.secondary_trigger == "REGIME_CHANGE" and last_regime and current_regime != last_regime:
        return True

    return sessions_since >= rule.base_interval_sessions


def inherit_prior_memory(target_conn: sqlite3.Connection, source_db_path: Path, clock: Clock) -> int:
    """Copies active and reinforced heuristics from a prior backtest DB into target_conn."""
    if not source_db_path.exists():
        return 0
    src = sqlite3.connect(source_db_path)
    src.row_factory = sqlite3.Row
    try:
        rows = src.execute(
            """
            SELECT agent_id, kind, context, heuristic_text, trigger_json, prescribed_action, status, confidence
            FROM agent_memory
            WHERE status IN ('active', 'reinforced')
            """
        ).fetchall()
        now = clock.now_iso()
        count = 0
        for r in rows:
            target_conn.execute(
                """
                INSERT INTO agent_memory (agent_id, kind, context, heuristic_text, trigger_json, prescribed_action, status, confidence, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    r["agent_id"],
                    r["kind"],
                    r["context"],
                    r["heuristic_text"],
                    r["trigger_json"],
                    r["prescribed_action"],
                    r["status"],
                    r["confidence"],
                    now,
                    now,
                ),
            )
            count += 1
        target_conn.commit()
        return count
    finally:
        src.close()


class BacktestEngine:
    def __init__(
        self,
        window: BacktestWindowConfig,
        db_path: Path | None = None,
        fake_llm: bool = False,
        use_cache: bool = True,
        resume: bool = False,
        progress_callback: Callable[[int, int, str], None] | None = None,
        agent_ids: list[str] | None = None,
        enable_heuristics: bool = True,
        inherit_memory: str | Path | None = None,
    ):
        self.window = window
        self.db_path = db_path or Path(f"storage/backtest/{window.window_id}.db")
        self.fake_llm = fake_llm
        self.use_cache = use_cache
        self.cache = LLMResponseCache() if use_cache else None
        self.resume = resume
        self.progress_callback = progress_callback
        self.agent_ids = agent_ids
        self.enable_heuristics = enable_heuristics
        self.inherit_memory = Path(inherit_memory).resolve() if inherit_memory else None

    def run(self) -> dict[str, Any]:
        """
        Executes the walk-forward simulation across all dates in self.window.
        Supports resume mode to skip already settled dates from previous runs.
        """
        start_t0 = time.time()
        start_date_obj = date.fromisoformat(self.window.start_date)
        clock = SimulatedClock(
            datetime(start_date_obj.year, start_date_obj.month, start_date_obj.day, 9, 0, tzinfo=IST)
        )

        source_port = Path(settings.PORTFOLIO_DB_PATH).resolve()
        conn = setup_isolated_backtest_db(self.db_path, source_port, clock, resume=self.resume)
        if self.inherit_memory and self.inherit_memory.exists():
            existing_count = conn.execute("SELECT COUNT(*) FROM agent_memory").fetchone()[0]
            if existing_count == 0:
                inherited_count = inherit_prior_memory(conn, self.inherit_memory, clock)
                logger.info(
                    "Inherited %d active/reinforced heuristics from prior database: %s",
                    inherited_count,
                    self.inherit_memory,
                )
        ohlcv_conn = get_connection(settings.OHLCV_DB_PATH)
        fundamental_conn = None
        news_conn = None
        try:
            fundamental_conn = get_connection(settings.FUNDAMENTAL_DB_PATH)
        except Exception:
            pass
        try:
            news_conn = get_connection(settings.NEWS_DB_PATH)
        except Exception:
            pass

        intraday_conn = None
        intraday_path = Path(settings.INTRADAY_DB_PATH)
        if intraday_path.exists():
            try:
                intraday_conn = get_connection(intraday_path)
                intraday_conn.execute("PRAGMA mmap_size = 536870912")  # 512MB memory-mapped IO
                intraday_conn.execute("PRAGMA query_only = 1")  # Read-only zero lock
            except Exception:
                intraday_conn = None

        data_provider = HistoricalDataProvider(
            ohlcv_conn=ohlcv_conn,
            fundamental_conn=fundamental_conn,
            news_conn=news_conn,
        )

        # Initialize LLM Client (Cached or Fake)
        from llm.client import FakeLLMClient, build_provider, require_setting

        if self.fake_llm:
            llm_client = FakeLLMClient()
        else:
            base_client = build_provider(
                settings.LLM_PROVIDER,
                model=require_setting(settings.LLM_MODEL, "LLM_MODEL"),
            )
            llm_client = CachedLLMClient(base_client, cache=self.cache) if self.use_cache else base_client
            fallback_client = None
            if settings.LLM_FALLBACK_PROVIDER:
                try:
                    fallback_client = build_provider(
                        settings.LLM_FALLBACK_PROVIDER,
                        model=require_setting(settings.LLM_FALLBACK_MODEL, "LLM_FALLBACK_MODEL"),
                    )
                except Exception as fb_err:
                    logger.warning("Backtest fallback client unavailable: %s", fb_err)

        try:
            # Gather trading sessions in this window
            all_trading_dates = get_all_trading_dates(ohlcv_conn)
            window_dates = [d for d in all_trading_dates if self.window.start_date <= d <= self.window.end_date]

            if not window_dates:
                return {
                    "status": "ERROR",
                    "error": f"No trading dates found in range {self.window.start_date} to {self.window.end_date}",
                }

            total_days = len(window_dates)
            logger.info(
                "Starting walk-forward backtest for [%s] (%s to %s, %d sessions)...",
                self.window.name,
                self.window.start_date,
                self.window.end_date,
                total_days,
            )

            # Map benchmark close proxy from universe avg
            bench_rows = ohlcv_conn.execute(
                """
                SELECT trade_date, AVG(close) as avg_c
                FROM ohlcv
                WHERE trade_date BETWEEN ? AND ?
                GROUP BY trade_date
                """,
                (self.window.start_date, self.window.end_date),
            ).fetchall()
            bench_map = {r["trade_date"]: float(r["avg_c"]) for r in bench_rows}

            # Detect already settled dates in resume mode
            completed_dates = set()
            if self.resume and self.db_path.exists():
                try:
                    rows = conn.execute("SELECT DISTINCT nav_date FROM daily_nav").fetchall()
                    completed_dates = {r[0] if isinstance(r, (tuple, list)) else r["nav_date"] for r in rows}
                    if completed_dates:
                        logger.info(
                            "Resume mode: %d sessions already settled in %s. Skipping them.",
                            len(completed_dates),
                            self.db_path.name,
                        )
                except Exception as exc:
                    logger.debug("Resume query note: %s", exc)

            # Cadence tracking state
            last_run_session: dict[str, int] = {}
            last_regime: str | None = None

            for idx, trade_date_str in enumerate(window_dates, start=1):
                cur_date = date.fromisoformat(trade_date_str)
                bench_close = bench_map.get(trade_date_str, 24000.0)
                remaining_sessions = total_days - idx

                # In resume mode, update cadence state and skip already settled dates
                if trade_date_str in completed_dates:
                    try:
                        dec_rows = conn.execute(
                            "SELECT DISTINCT agent_id FROM decisions WHERE run_date = ?",
                            (trade_date_str,),
                        ).fetchall()
                        for r in dec_rows:
                            aid = r[0] if isinstance(r, (tuple, list)) else r["agent_id"]
                            last_run_session[aid] = idx

                        snap = conn.execute(
                            "SELECT features_json FROM feature_snapshots WHERE as_of_date = ? LIMIT 1",
                            (trade_date_str,),
                        ).fetchone()
                        if snap:
                            f_raw = snap[0] if isinstance(snap, (tuple, list)) else snap["features_json"]
                            last_regime = json.loads(f_raw).get("regime", "NORMAL")
                    except Exception:
                        pass
                    continue

                if self.progress_callback:
                    self.progress_callback(idx, total_days, trade_date_str)

                # --- 1. MORNING (10:00 IST): Daily Candle Matching & Settlement ---
                clock.set_time(datetime(cur_date.year, cur_date.month, cur_date.day, 10, 0, tzinfo=IST))
                resolve_day(
                    conn=conn,
                    ohlcv_conn=ohlcv_conn,
                    clock=clock,
                    trade_date=trade_date_str,
                    nifty500_close=bench_close,
                    intraday_conn=intraday_conn,
                )

                # --- 2. AFTERNOON (15:45 IST): Forward Returns & Learning Resolution ---
                clock.set_time(datetime(cur_date.year, cur_date.month, cur_date.day, 15, 45, tzinfo=IST))
                try:
                    compute_forward_returns(conn, ohlcv_conn, clock=clock)
                    if self.enable_heuristics:
                        resolve_pending_applications(conn, clock=clock, ohlcv_conn=ohlcv_conn)
                        update_lifecycle(conn, clock=clock)
                        from learning.compliance import audit_compliance_and_escalate

                        audit_compliance_and_escalate(conn, clock=clock)
                        enrich_post_exit(conn, clock=clock, as_of_date=trade_date_str, ohlcv_conn=ohlcv_conn)
                except Exception as exc:
                    logger.debug("Evaluation backfill note on %s: %s", trade_date_str, exc)

                # --- 3. EVENING (20:00 IST): Features Builder with Historical Seam ---
                clock.set_time(datetime(cur_date.year, cur_date.month, cur_date.day, 20, 0, tzinfo=IST))
                conn.execute(
                    """
                    INSERT INTO pipeline_runs (job, run_date, status, started_at, finished_at, detail)
                    VALUES ('ingestion', ?, 'SUCCESS', ?, ?, 'Backtest historical pre-validated')
                    ON CONFLICT(job, run_date) DO UPDATE SET status = 'SUCCESS'
                    """,
                    (trade_date_str, clock.now_iso(), clock.now_iso()),
                )
                conn.commit()

                # Build feature snapshots using HistoricalDataProvider
                snap_exists = conn.execute(
                    "SELECT 1 FROM feature_snapshots WHERE as_of_date = ? LIMIT 1",
                    (trade_date_str,),
                ).fetchone()
                if not snap_exists:
                    run_build_features(
                        as_of_date=trade_date_str,
                        clock=clock,
                        portfolio_conn=conn,
                        ohlcv_conn=ohlcv_conn,
                        data_provider=data_provider,
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO pipeline_runs (job, run_date, status, started_at, finished_at, detail)
                        VALUES ('features', ?, 'SUCCESS', ?, ?, 'Pre-populated feature snapshots')
                        ON CONFLICT(job, run_date) DO UPDATE SET status = 'SUCCESS'
                        """,
                        (trade_date_str, clock.now_iso(), clock.now_iso()),
                    )
                    conn.commit()

                # Detect current macro regime
                cur_regime_row = conn.execute(
                    "SELECT features_json FROM feature_snapshots WHERE as_of_date = ? LIMIT 1",
                    (trade_date_str,),
                ).fetchone()

                cur_regime = "NORMAL"
                vix_val = None
                if cur_regime_row:
                    try:
                        f_dict = json.loads(cur_regime_row["features_json"])
                        cur_regime = f_dict.get("regime", "NORMAL")
                        vix_val = f_dict.get("india_vix")
                    except Exception:
                        pass

                # --- 4. EVENING (21:00 IST): Watchlist Refresh (Cadence Gated) ---
                clock.set_time(datetime(cur_date.year, cur_date.month, cur_date.day, 21, 0, tzinfo=IST))
                due_personas = []
                candidate_personas = [p for p in all_personas() if not self.agent_ids or p.id in self.agent_ids]

                # Identify any agents whose positions reached targets today (Event-driven wakeup)
                target_reached_agents = {
                    r[0] if isinstance(r, (tuple, list)) else r["agent_id"]
                    for r in conn.execute(
                        "SELECT DISTINCT agent_id FROM activity_log WHERE event_type = 'TARGET_REACHED' AND created_at LIKE ?",
                        (f"{trade_date_str}%",),
                    ).fetchall()
                }

                for p in candidate_personas:
                    has_tgt_event = p.id in target_reached_agents
                    if is_persona_due_today(
                        p.id,
                        idx,
                        last_run_session,
                        cur_regime,
                        last_regime,
                        remaining_sessions,
                        has_target_reached_event=has_tgt_event,
                    ):
                        due_personas.append(p)
                        run_watchlist_refresh(
                            as_of_date=trade_date_str, agent_id=p.id, clock=clock, portfolio_conn=conn
                        )

                # Status log for current session
                vix_str = f" | VIX: {vix_val:.1f}" if vix_val is not None else ""
                open_pos_count = conn.execute("SELECT count(*) FROM positions WHERE status = 'OPEN'").fetchone()[0]
                due_names = [p.id for p in due_personas]
                should_run_simons_baseline = not self.agent_ids or "baseline-simons-rules" in self.agent_ids
                should_run_varsity_baseline = not self.agent_ids or "baseline-varsity-rules" in self.agent_ids
                should_run_lynch_baseline = not self.agent_ids or "baseline-lynch-rules" in self.agent_ids
                should_run_marks_baseline = not self.agent_ids or "baseline-marks-rules" in self.agent_ids
                should_run_rj_baseline = not self.agent_ids or "baseline-rj-rules" in self.agent_ids

                if should_run_simons_baseline and any(p.id == "simons" for p in due_personas):
                    due_names.append("baseline-simons-rules")
                if should_run_varsity_baseline and any(p.id == "varsity" for p in due_personas):
                    due_names.append("baseline-varsity-rules")
                if should_run_lynch_baseline and any(p.id == "lynch" for p in due_personas):
                    due_names.append("baseline-lynch-rules")
                if should_run_marks_baseline and any(p.id == "marks" for p in due_personas):
                    due_names.append("baseline-marks-rules")
                if should_run_rj_baseline and any(p.id == "jhunjhunwala" for p in due_personas):
                    due_names.append("baseline-rj-rules")

                due_str = ", ".join(due_names) if due_names else "None"
                logger.info(
                    "[%3d/%3d (%5.1f%%)] %s | Regime: %-12s%s | Due: [%s] | Open Pos: %d",
                    idx,
                    total_days,
                    (idx / total_days) * 100.0,
                    trade_date_str,
                    cur_regime,
                    vix_str,
                    due_str,
                    open_pos_count,
                )

                # --- 5. NIGHT (22:00 IST): Agent Decisions & Order Placement ---
                clock.set_time(datetime(cur_date.year, cur_date.month, cur_date.day, 22, 0, tzinfo=IST))
                # Run baselines if respective personas are due
                if should_run_simons_baseline and any(p.id == "simons" for p in due_personas):
                    b_res = run_baseline_simons(trade_date_str, clock, conn)
                    logger.info(
                        "  [baseline-simons-rules] Decisions: %d | Orders: %s",
                        b_res.get("decisions", 0),
                        b_res.get("order_summary") or "None",
                    )

                if should_run_varsity_baseline and any(p.id == "varsity" for p in due_personas):
                    b_varsity_res = run_baseline_varsity(trade_date_str, clock, conn)
                    logger.info(
                        "  [baseline-varsity-rules] Decisions: %d | Orders: %s",
                        b_varsity_res.get("decisions", 0),
                        b_varsity_res.get("order_summary") or "None",
                    )

                if should_run_lynch_baseline and any(p.id == "lynch" for p in due_personas):
                    b_lynch_res = run_baseline_lynch(trade_date_str, clock, conn)
                    logger.info(
                        "  [baseline-lynch-rules] Decisions: %d | Orders: %s",
                        b_lynch_res.get("decisions", 0),
                        b_lynch_res.get("order_summary") or "None",
                    )

                if should_run_marks_baseline and any(p.id == "marks" for p in due_personas):
                    b_marks_res = run_baseline_marks(trade_date_str, clock, conn)
                    logger.info(
                        "  [baseline-marks-rules] Decisions: %d | Orders: %s",
                        b_marks_res.get("decisions", 0),
                        b_marks_res.get("order_summary") or "None",
                    )

                if should_run_rj_baseline and any(p.id == "jhunjhunwala" for p in due_personas):
                    b_rj_res = run_baseline_rj(trade_date_str, clock, conn)
                    logger.info(
                        "  [baseline-rj-rules] Decisions: %d | Orders: %s",
                        b_rj_res.get("decisions", 0),
                        b_rj_res.get("order_summary") or "None",
                    )

                for p in due_personas:
                    if hasattr(llm_client, "set_context"):
                        llm_client.set_context(p.id, trade_date_str)
                    try:
                        run_agents(
                            agent_ids=[p.id],
                            as_of_date=trade_date_str,
                            clock=clock,
                            fake_llm=self.fake_llm,
                            llm_client=llm_client,
                            fallback_client=fallback_client,
                            portfolio_conn=conn,
                        )
                        last_run_session[p.id] = idx
                    except Exception as exc:
                        logger.error(
                            "LLM execution for persona %s on %s encountered error: %s. Session skipped for this persona.",
                            p.id,
                            trade_date_str,
                            exc,
                        )

                last_regime = cur_regime

                # --- 5b. NIGHT (22:30 IST): Heuristic Nightly Trigger Evaluation ---
                if self.enable_heuristics:
                    clock.set_time(datetime(cur_date.year, cur_date.month, cur_date.day, 22, 30, tzinfo=IST))
                    try:
                        new_apps = evaluate_triggers_for_date(conn, clock=clock, as_of_date=trade_date_str)
                        if new_apps > 0:
                            logger.info(
                                "  [Heuristics] Triggered %d heuristic application(s) on %s", new_apps, trade_date_str
                            )
                    except Exception as exc:
                        logger.debug("Heuristic nightly trigger note on %s: %s", trade_date_str, exc)

                # --- 6. SUNDAY (10:00 IST): Watermark Reflection Loop ---
                if self.enable_heuristics and idx < len(window_dates):
                    next_date = date.fromisoformat(window_dates[idx])
                    delta_days = (next_date - cur_date).days
                    if delta_days > 1:
                        for d_offset in range(1, delta_days):
                            mid_date = cur_date + timedelta(days=d_offset)
                            if mid_date.weekday() == 6:  # Sunday
                                sunday_clock = SimulatedClock(
                                    datetime(mid_date.year, mid_date.month, mid_date.day, 10, 0, tzinfo=IST)
                                )
                                ref_summary = run_reflection(
                                    conn,
                                    clock=sunday_clock,
                                    llm_client=llm_client,
                                    fallback_client=fallback_client,
                                    agent_ids=self.agent_ids,
                                    ohlcv_conn=ohlcv_conn,
                                )
                                for aid, r in ref_summary.get("agents", {}).items():
                                    if r.get("status") == "DONE" and r.get("trades_reviewed", 0) > 0:
                                        logger.info(
                                            "  [Sunday Reflection] %s (%s): Reviewed %d trades -> Created %d new heuristic(s) (watermark: %s)",
                                            aid,
                                            mid_date.isoformat(),
                                            r["trades_reviewed"],
                                            r.get("heuristics_created", 0),
                                            r.get("watermark"),
                                        )

            # Final Evaluation & Statistics
            perf_summary = evaluate_all_agents(conn, is_backtest=True)
            comparison_summary = compare_simons_vs_baseline(conn, is_backtest=True)
            varsity_comparison_summary = compare_varsity_vs_baseline(conn, is_backtest=True)
            lynch_comparison_summary = compare_lynch_vs_baseline(conn, is_backtest=True)
            marks_comparison_summary = compare_marks_vs_baseline(conn, is_backtest=True)
            rj_comparison_summary = compare_rj_vs_baseline(conn, is_backtest=True)
            elapsed = time.time() - start_t0

            return {
                "status": "SUCCESS",
                "window": {
                    "window_id": self.window.window_id,
                    "name": self.window.name,
                    "start_date": self.window.start_date,
                    "end_date": self.window.end_date,
                    "regime_label": self.window.regime_label,
                    "sessions_count": len(window_dates),
                },
                "elapsed_sec": round(elapsed, 2),
                "is_backtest": True,
                "evidence_label": "BACKTEST_DERIVED",
                "disclaimer": "BACKTEST-DERIVED RESULTS (Question B Proof) — Not equivalent to live paper pilot",
                "performance": perf_summary,
                "comparison": comparison_summary,
                "varsity_comparison": varsity_comparison_summary,
                "lynch_comparison": lynch_comparison_summary,
                "marks_comparison": marks_comparison_summary,
                "rj_comparison": rj_comparison_summary,
                "database_path": str(self.db_path),
            }
        finally:
            conn.close()
            ohlcv_conn.close()
            if fundamental_conn:
                fundamental_conn.close()
            if news_conn:
                news_conn.close()
            if intraday_conn:
                intraday_conn.close()
