"""
Four-stage watchlist funnel (liquidity, persona hurdles, intensity sort, sector cap + TTL) with
per-stage funnel-count logging. Run as
`python -m precompute.watchlist_refresh --date YYYY-MM-DD --agent simons`.
See Plan_v3 §6.
"""

import argparse
import json
import sqlite3
from bisect import bisect_right
from collections import Counter, defaultdict
from datetime import date, timedelta

import pandas as pd

from agents.personas import get_persona
from agents.personas.base import PersonaConfig
from core.clock import Clock, SystemClock
from core.config import settings
from core.database import get_connection
from features.contracts import evaluate_predicate
from watchlist.rankers import SORT_KEYS, get_strategy_ranker

JOB_NAME = "watchlist"

# Plan_v3 §6: the extra SMA5(vol) > SMA20(vol) momentum rule applies only to these personas.
# This is a fixed rule from the plan, not a per-persona tunable, so it lives here rather than
# as a PersonaConfig field; adding a new persona that doesn't need it requires no code change.
MOMENTUM_VOLUME_RULE_PERSONAS = {"simons", "jhunjhunwala"}


# Note: SORT_KEYS and single-stock heuristic scorers are imported from watchlist.rankers
# and re-exported here for backwards compatibility.


# --- Stage 0: liquidity + circuit/stale + persona-specific momentum rule -----------------------


def _bulk_stage0_metrics(ohlcv_conn: sqlite3.Connection, tickers: list[str], as_of_date: str) -> dict[str, dict]:
    """One bulk query (never per-ticker) returning {ticker: {"turnover": x, "sma5_gt_sma20": bool}}
    for every ticker with at least 20 sessions up to as_of_date."""
    if not tickers:
        return {}
    min_date = (date.fromisoformat(as_of_date) - timedelta(days=60)).isoformat()
    placeholders = ",".join("?" * len(tickers))
    rows = ohlcv_conn.execute(
        f"SELECT ticker, trade_date, close, volume FROM ohlcv "
        f"WHERE ticker IN ({placeholders}) AND trade_date >= ? AND trade_date <= ? ORDER BY ticker, trade_date",
        (*tickers, min_date, as_of_date),
    ).fetchall()
    if not rows:
        return {}
    df = pd.DataFrame(rows, columns=["ticker", "trade_date", "close", "volume"])

    result = {}
    for ticker, group in df.groupby("ticker"):
        if len(group) < 20:
            continue
        adv20 = float(group["volume"].tail(20).mean())
        latest_close = float(group["close"].iloc[-1])
        sma5 = float(group["volume"].tail(5).mean())
        result[ticker] = {"turnover": adv20 * latest_close, "sma5_gt_sma20": sma5 > adv20}
    return result


def stage0_filter(
    portfolio_conn: sqlite3.Connection, ohlcv_conn: sqlite3.Connection, persona: PersonaConfig, as_of_date: str
) -> list[str]:
    """Liquidity gate (turnover + not STALE/LOCKED), plus the momentum volume rule for Simons/RJ."""
    active_tickers = [
        r["ticker"]
        for r in portfolio_conn.execute("SELECT ticker FROM symbols WHERE is_active = 1 ORDER BY ticker").fetchall()
    ]
    status_by_ticker = {
        r["ticker"]: r["status"] for r in ohlcv_conn.execute("SELECT ticker, status FROM ticker_status").fetchall()
    }
    ok_tickers = [t for t in active_tickers if status_by_ticker.get(t) == "OK"]

    metrics = _bulk_stage0_metrics(ohlcv_conn, ok_tickers, as_of_date)
    needs_momentum_rule = persona.id in MOMENTUM_VOLUME_RULE_PERSONAS

    survivors = []
    for t in ok_tickers:
        m = metrics.get(t)
        if m is None or m["turnover"] < settings.MIN_TURNOVER_RUPEES:
            continue
        if needs_momentum_rule and not m["sma5_gt_sma20"]:
            continue
        survivors.append(t)
    return survivors


# --- Stage 1: persona hurdles on the FeatureSnapshot --------------------------------------------


def _load_features(portfolio_conn: sqlite3.Connection, tickers: list[str], as_of_date: str) -> dict[str, dict]:
    if not tickers:
        return {}
    placeholders = ",".join("?" * len(tickers))
    rows = portfolio_conn.execute(
        f"SELECT ticker, features_json FROM feature_snapshots WHERE as_of_date = ? AND ticker IN ({placeholders})",
        (as_of_date, *tickers),
    ).fetchall()
    return {r["ticker"]: json.loads(r["features_json"]) for r in rows}


def compute_sector_percentiles(
    scores_by_ticker: dict[str, float],
    sector_by_ticker: dict[str, str],
    min_cohort: int = settings.MIN_SECTOR_COHORT,
) -> dict[str, float]:
    """
    Computes percentile rank (0.0 to 100.0) for each ticker within its sector peer group.
    Per Plan_v3 §2.3:
    - If a sector cohort has >= min_cohort (8) stocks, percentile is computed within that sector.
    - If a sector cohort has < min_cohort stocks, falls back to the whole-universe percentile.
    """
    if not scores_by_ticker:
        return {}

    by_sector: dict[str, list[float]] = defaultdict(list)
    for ticker, score in scores_by_ticker.items():
        if score > float("-inf"):
            sector = sector_by_ticker.get(ticker, "UNKNOWN")
            by_sector[sector].append(score)

    universe_scores = sorted([s for s in scores_by_ticker.values() if s > float("-inf")])
    universe_size = len(universe_scores)

    percentiles: dict[str, float] = {}
    for ticker, score in scores_by_ticker.items():
        if score == float("-inf"):
            percentiles[ticker] = 0.0
            continue

        sector = sector_by_ticker.get(ticker, "UNKNOWN")
        cohort = by_sector.get(sector, [])

        if len(cohort) >= min_cohort:
            cohort_sorted = sorted(cohort)
            idx = bisect_right(cohort_sorted, score)
            percentiles[ticker] = (idx / len(cohort_sorted)) * 100.0
        else:
            idx = bisect_right(universe_scores, score) if universe_size > 0 else 1
            percentiles[ticker] = (idx / universe_size * 100.0) if universe_size > 0 else 50.0

    return percentiles


def stage1_filter(
    stage0_tickers: list[str],
    features_by_ticker: dict[str, dict],
    persona: PersonaConfig,
    sector_percentiles: dict[str, float] | None = None,
) -> list[str]:
    """A stock must pass both the technical and the fundamental hurdle predicates. Sector
    percentile is a Stage-2 ranking input only, never a Stage-1 filter (Plan_v3 §6), unless
    SECTOR_PERCENTILE_MIN > 0 is configured."""
    survivors = []
    for t in stage0_tickers:
        features = features_by_ticker.get(t)
        if features is None:
            continue
        if not (
            evaluate_predicate(features, persona.technical_hurdles)
            and evaluate_predicate(features, persona.fundamental_hurdles)
        ):
            continue
        if settings.SECTOR_PERCENTILE_MIN > 0 and sector_percentiles is not None:
            pct = sector_percentiles.get(t, 100.0)
            if pct < settings.SECTOR_PERCENTILE_MIN:
                continue
        survivors.append(t)
    return survivors


# --- Stage 2: intensity sort ---------------------------------------------------------------------


def stage2_sort(
    stage1_tickers: list[str],
    features_by_ticker: dict[str, dict],
    sector_by_ticker: dict[str, str],
    persona: PersonaConfig,
    sector_percentiles: dict[str, float] | None = None,
) -> list[dict]:
    """Returns [{"ticker", "sector", "intensity_score", "raw_score", "sector_percentile"}, ...]
    sorted by descending intensity via the strategy's dedicated ranker."""
    if not stage1_tickers:
        return []
    ranker = get_strategy_ranker(persona.sort_key)
    return ranker(
        stage1_tickers=stage1_tickers,
        features_by_ticker=features_by_ticker,
        sector_by_ticker=sector_by_ticker,
        sector_percentiles=sector_percentiles,
    )


# --- Stage 3: sector cap, target size, TTL lock --------------------------------------------------


def stage3_update_watchlist(
    portfolio_conn: sqlite3.Connection,
    persona: PersonaConfig,
    as_of_date: str,
    stage0_tickers: list[str],
    ranked_candidates: list[dict],
    features_by_ticker: dict[str, dict],
    clock: Clock,
) -> dict:
    agent_id = persona.id
    stage0_set = set(stage0_tickers)

    existing_rows = portfolio_conn.execute(
        "SELECT ticker, sector, added_on, ttl_days, expires_on, intensity_score FROM agent_watchlist WHERE agent_id = ?",
        (agent_id,),
    ).fetchall()

    kept_rows, removed_tickers = [], []
    for row in existing_rows:
        ticker = row["ticker"]
        not_expired = row["expires_on"] >= as_of_date
        passes_stage0 = ticker in stage0_set
        trend_valid = True
        if getattr(persona, "require_above_ema200", True):
            features = features_by_ticker.get(ticker)
            trend_valid = bool(
                features
                and features.get("ema_200") is not None
                and features.get("close") is not None
                and features["close"] > features["ema_200"]
            )
        if not_expired and passes_stage0 and trend_valid:
            kept_rows.append(row)
        else:
            removed_tickers.append(ticker)

    for ticker in removed_tickers:
        portfolio_conn.execute("DELETE FROM agent_watchlist WHERE agent_id = ? AND ticker = ?", (agent_id, ticker))

    locked_tickers = {r["ticker"] for r in kept_rows}
    sector_counts = Counter(r["sector"] for r in kept_rows)

    target_size_max = getattr(persona, "max_candidates", settings.WATCHLIST_TARGET_SIZE_MAX)
    sector_cap = getattr(persona, "sector_cap", settings.SECTOR_CAP_PER_AGENT)

    new_rows = []
    for candidate in ranked_candidates:
        if len(kept_rows) + len(new_rows) >= target_size_max:
            break
        ticker = candidate["ticker"]
        if ticker in locked_tickers:
            continue
        sector = candidate["sector"]
        if sector_counts[sector] >= sector_cap:
            continue
        sector_counts[sector] += 1
        new_rows.append(candidate)

    expires_on = (date.fromisoformat(as_of_date) + timedelta(days=persona.ttl_days)).isoformat()
    for candidate in new_rows:
        portfolio_conn.execute(
            """
            INSERT INTO agent_watchlist (agent_id, ticker, sector, added_on, ttl_days, expires_on, intensity_score)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(agent_id, ticker) DO UPDATE SET
                sector = excluded.sector, added_on = excluded.added_on, ttl_days = excluded.ttl_days,
                expires_on = excluded.expires_on, intensity_score = excluded.intensity_score
            """,
            (
                agent_id,
                candidate["ticker"],
                candidate["sector"],
                as_of_date,
                persona.ttl_days,
                expires_on,
                candidate["intensity_score"],
            ),
        )

    final_rows = portfolio_conn.execute(
        "SELECT ticker, sector, intensity_score FROM agent_watchlist WHERE agent_id = ? ORDER BY intensity_score DESC",
        (agent_id,),
    ).fetchall()
    return {
        "kept": len(kept_rows),
        "new": len(new_rows),
        "removed": len(removed_tickers),
        "final": [dict(r) for r in final_rows],
    }


# --- Review pool (used by the agent runner, not just this refresh job) --------------------------


def get_review_pool(portfolio_conn: sqlite3.Connection, agent_id: str, run_date: str) -> list[dict]:
    """Returns the agent's OPEN positions plus its watchlist, capped at max_candidates.
    Open positions are always included; the lowest-intensity watchlist names are dropped first.
    Each entry is {"ticker": str, "is_held": bool}. `run_date` is accepted for interface
    stability (a future per-date snapshot) but agent_watchlist/positions are live-state tables,
    so it is not otherwise used here."""
    try:
        persona = get_persona(agent_id)
        max_candidates = getattr(persona, "max_candidates", settings.MAX_CANDIDATES_PER_RUN)
    except KeyError:
        max_candidates = settings.MAX_CANDIDATES_PER_RUN

    held_rows = portfolio_conn.execute(
        "SELECT ticker FROM positions WHERE agent_id = ? AND status = 'OPEN'", (agent_id,)
    ).fetchall()
    held_tickers = [r["ticker"] for r in held_rows]
    held_set = set(held_tickers)

    watchlist_rows = portfolio_conn.execute(
        "SELECT ticker FROM agent_watchlist WHERE agent_id = ? ORDER BY intensity_score DESC",
        (agent_id,),
    ).fetchall()
    watchlist_not_held = [r["ticker"] for r in watchlist_rows if r["ticker"] not in held_set]

    pool = [{"ticker": t, "is_held": True} for t in held_tickers]
    remaining_slots = max(max_candidates - len(pool), 0)
    pool.extend({"ticker": t, "is_held": False} for t in watchlist_not_held[:remaining_slots])
    return pool


# --- Pipeline wiring ------------------------------------------------------------------------------


def _pipeline_status(conn, job: str, run_date: str) -> str | None:
    row = conn.execute("SELECT status FROM pipeline_runs WHERE job = ? AND run_date = ?", (job, run_date)).fetchone()
    return row["status"] if row else None


def _upsert_terminal_run(conn, run_date: str, status: str, clock: Clock, detail: str = None) -> None:
    now = clock.now_iso()
    conn.execute(
        """
        INSERT INTO pipeline_runs (job, run_date, status, started_at, finished_at, detail)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(job, run_date) DO UPDATE SET
            status = excluded.status, started_at = excluded.started_at,
            finished_at = excluded.finished_at, detail = excluded.detail
        """,
        (JOB_NAME, run_date, status, now, now, detail),
    )


def _start_run(conn, run_date: str, clock: Clock) -> None:
    conn.execute(
        """
        INSERT INTO pipeline_runs (job, run_date, status, started_at, finished_at, detail)
        VALUES (?, ?, 'RUNNING', ?, NULL, NULL)
        ON CONFLICT(job, run_date) DO UPDATE SET
            status = 'RUNNING', started_at = excluded.started_at, finished_at = NULL, detail = NULL
        """,
        (JOB_NAME, run_date, clock.now_iso()),
    )


def _finish_run(conn, run_date: str, status: str, clock: Clock, detail: str = None) -> None:
    conn.execute(
        "UPDATE pipeline_runs SET status = ?, finished_at = ?, detail = ? WHERE job = ? AND run_date = ?",
        (status, clock.now_iso(), detail, JOB_NAME, run_date),
    )


def _write_funnel_counts(conn, agent_id: str, run_date: str, counts: dict, clock: Clock) -> None:
    conn.execute(
        """
        INSERT INTO activity_log (agent_id, event_type, ticker, description, metadata_json, created_at)
        VALUES (?, 'FUNNEL_COUNTS', NULL, ?, ?, ?)
        """,
        (
            agent_id,
            f"Watchlist funnel for {agent_id} on {run_date}: "
            f"stage0={counts['stage0']} stage1={counts['stage1']} final={counts['final']}",
            json.dumps(counts),
            clock.now_iso(),
        ),
    )


def run_all(
    as_of_date: str = None,
    clock: Clock = None,
    portfolio_conn: sqlite3.Connection = None,
    ohlcv_conn: sqlite3.Connection = None,
) -> dict:
    """Runs the Stage 0-3 funnel for all active personas."""
    clock = clock or SystemClock()
    owns_portfolio = portfolio_conn is None
    owns_ohlcv = ohlcv_conn is None
    portfolio_conn = portfolio_conn or get_connection(settings.PORTFOLIO_DB_PATH)
    ohlcv_conn = ohlcv_conn or get_connection(settings.OHLCV_DB_PATH)
    try:
        from agents.personas import all_personas

        results = {}
        for persona in all_personas():
            res = run(
                as_of_date=as_of_date,
                agent_id=persona.id,
                clock=clock,
                portfolio_conn=portfolio_conn,
                ohlcv_conn=ohlcv_conn,
            )
            results[persona.id] = res
            if res.get("status") != "SUCCESS":
                return {"status": "FAILED", "results": results, "failed_agent": persona.id}
        return {"status": "SUCCESS", "results": results}
    finally:
        if owns_portfolio:
            portfolio_conn.close()
        if owns_ohlcv:
            ohlcv_conn.close()


def run(
    as_of_date: str = None,
    agent_id: str = "simons",
    clock: Clock = None,
    portfolio_conn: sqlite3.Connection = None,
    ohlcv_conn: sqlite3.Connection = None,
) -> dict:
    """Runs the Stage 0-3 funnel for one agent/date (or all if agent_id='all'). Returns stage counts and the final watchlist."""
    clock = clock or SystemClock()
    owns_portfolio = portfolio_conn is None
    owns_ohlcv = ohlcv_conn is None
    portfolio_conn = portfolio_conn or get_connection(settings.PORTFOLIO_DB_PATH)
    ohlcv_conn = ohlcv_conn or get_connection(settings.OHLCV_DB_PATH)
    try:
        if agent_id.lower() == "all":
            return run_all(
                as_of_date=as_of_date,
                clock=clock,
                portfolio_conn=portfolio_conn,
                ohlcv_conn=ohlcv_conn,
            )

        if agent_id.lower() in ("stockminds-core", "stockminds", "core", "varsity-dcf"):
            agent_id = "varsity"

        run_date = as_of_date or clock.today().isoformat()
        persona = get_persona(agent_id)

        features_status = _pipeline_status(portfolio_conn, "features", run_date)
        if features_status != "SUCCESS":
            detail = f"features status for {run_date} is {features_status!r}, expected SUCCESS"
            _upsert_terminal_run(portfolio_conn, run_date, "FAILED", clock, detail=detail)
            return {"status": "FAILED", "detail": detail}

        _start_run(portfolio_conn, run_date, clock)
        try:
            stage0_tickers = stage0_filter(portfolio_conn, ohlcv_conn, persona, run_date)
            features_by_ticker = _load_features(portfolio_conn, stage0_tickers, run_date)

            sector_by_ticker = {
                r["ticker"]: r["sector"]
                for r in portfolio_conn.execute("SELECT ticker, sector FROM symbols").fetchall()
            }
            sort_fn = SORT_KEYS[persona.sort_key]
            scores_by_ticker = {t: sort_fn(features_by_ticker[t]) for t in stage0_tickers if t in features_by_ticker}
            sector_percentiles = compute_sector_percentiles(
                scores_by_ticker, sector_by_ticker, min_cohort=settings.MIN_SECTOR_COHORT
            )

            stage1_tickers = stage1_filter(
                stage0_tickers, features_by_ticker, persona, sector_percentiles=sector_percentiles
            )
            ranked = stage2_sort(
                stage1_tickers, features_by_ticker, sector_by_ticker, persona, sector_percentiles=sector_percentiles
            )

            # Stage 3 needs features for any already-locked tickers too (for the ema_200 check),
            # even if they fell out of today's stage0/stage1 survivor set.
            existing_tickers = [
                r["ticker"]
                for r in portfolio_conn.execute(
                    "SELECT ticker FROM agent_watchlist WHERE agent_id = ?", (agent_id,)
                ).fetchall()
            ]
            missing = [t for t in existing_tickers if t not in features_by_ticker]
            features_by_ticker.update(_load_features(portfolio_conn, missing, run_date))

            stage3 = stage3_update_watchlist(
                portfolio_conn, persona, run_date, stage0_tickers, ranked, features_by_ticker, clock
            )

            counts = {"stage0": len(stage0_tickers), "stage1": len(stage1_tickers), "final": len(stage3["final"])}
            _write_funnel_counts(portfolio_conn, agent_id, run_date, counts, clock)
        except Exception as exc:
            _finish_run(portfolio_conn, run_date, "FAILED", clock, detail=str(exc)[:500])
            raise

        _finish_run(portfolio_conn, run_date, "SUCCESS", clock, detail=json.dumps(counts))
        return {"status": "SUCCESS", "counts": counts, "watchlist": stage3["final"]}
    finally:
        if owns_portfolio:
            portfolio_conn.close()
        if owns_ohlcv:
            ohlcv_conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage 0-3 watchlist funnel for one or all agents.")
    parser.add_argument("--date", dest="date_str", default=None, help="YYYY-MM-DD, default: today (IST)")
    parser.add_argument(
        "--agent",
        dest="agent_id",
        default="simons",
        help="Persona id (e.g. simons, lynch, marks, jhunjhunwala, stockminds-core) or 'all'",
    )
    args = parser.parse_args()
    result = run(as_of_date=args.date_str, agent_id=args.agent_id)
    if result.get("status") != "SUCCESS":
        print(f"watchlist_refresh: {result.get('status')} - {result.get('detail') or result.get('failed_agent')}")
        return
    if args.agent_id.lower() == "all":
        print("watchlist_refresh: SUCCESS for all personas")
        for persona_id, res in result.get("results", {}).items():
            print(f"[{persona_id}] Counts: {res.get('counts')}")
            for row in res.get("watchlist", []):
                print(f"  {row['ticker']:<16} {row['sector']:<30} intensity={row['intensity_score']:.4f}")
    else:
        print(f"watchlist_refresh: SUCCESS {result['counts']}")
        for row in result["watchlist"]:
            print(f"  {row['ticker']:<16} {row['sector']:<30} intensity={row['intensity_score']:.4f}")


if __name__ == "__main__":
    main()
