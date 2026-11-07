# StockMinds REST API — Phase 1 + 2

Read-only FastAPI backend for the React dashboard. Every DB connection it opens is read-only
(`sqlite3.connect(f"file:{path}?mode=ro", ...)`); it never writes anything, anywhere.

## Running it

```bash
cd Autonomous_Stock_Trading
PYTHONPATH=src python -m uvicorn api.main:app --reload --port 8000
```

The guide's suggested command (`uvicorn src.api.main:app --reload --port 8000`) does **not**
work in this repo — every module under `src/` imports its siblings as top-level packages
(`from core.config import settings`, `from api.deps import ...`), the same way `pytest.ini`'s
`pythonpath = src .` already does it for the test suite. Point `PYTHONPATH` at `src` and import
`api.main:app`, not `src.api.main:app`.

Once running: `http://127.0.0.1:8000/docs` has the interactive Swagger UI.

## Endpoints (Phase 1)

### `GET /api/health`
Latest `pipeline_runs` row per job, plus a `database_reachable` flag. The job list always comes
from the table (never hardcoded); `cadence` is a static lookup of `scheduler.py`'s actual cron
registration and is `null` for a job name the lookup doesn't recognize.

```json
{
  "database_reachable": true,
  "jobs": [
    {
      "job_name": "ingestion",
      "cadence": "Daily 20:00 IST (Mon-Fri)",
      "status": "SUCCESS",
      "last_run_at": "2026-10-29T20:00:00+05:30",
      "duration_sec": 0,
      "records_processed": null,
      "error_message": null
    }
  ]
}
```

### `GET /api/activity?limit=&offset=&agent_id=&event_type=&severity=&q=`
`activity_log` rows, newest first. `severity` is derived (there is no such column): a
`PIPELINE_FAILED` row's own `metadata_json.severity` (CRITICAL/WARNING, set by
`notifications/alerts.py`) wins when present (CRITICAL is remapped to ERROR); otherwise a static
`event_type -> severity` map in `api/deps.py` is used, defaulting to INFO.

```json
{
  "total": 76,
  "limit": 50,
  "offset": 0,
  "events": [
    {
      "id": "evt-83",
      "timestamp": "2026-10-31T02:45:12.849348+05:30",
      "event_type": "FUNNEL_COUNTS",
      "agent_id": "jhunjhunwala",
      "symbol": null,
      "message": "Watchlist funnel for jhunjhunwala on 2026-10-29: stage0=237 stage1=6 final=8",
      "severity": "INFO",
      "details": {"stage0": 237, "stage1": 6, "final": 8}
    }
  ]
}
```

### `GET /api/leaderboard`
One entry per row in `agents`, built from `evaluation.performance.evaluate_all_agents`.

```json
[
  {
    "id": "baseline-lynch-rules",
    "name": "Baseline Lynch Rules",
    "badge": "RULES",
    "strategy_family": "Rules-only Peter Lynch GARP baseline",
    "nav_paise": 52275096,
    "starting_capital_paise": 50000000,
    "return_pct": 4.55,
    "alpha_vs_benchmark_pct": 4.19,
    "sharpe_ratio": 0.12,
    "max_drawdown_pct": -14.65,
    "win_rate_pct": 28.9,
    "faithfulness_rate_pct": 100.0,
    "total_trades": 43,
    "closed_trades": 38,
    "active_positions_count": 5,
    "is_provisional": false,
    "sample_notice": "VALIDATED (>=30 closed trades)",
    "foundation_model": null,
    "evidence_label": "LIVE_PILOT"
  }
]
```

### `GET /api/agents/nav`
Daily NAV series for every agent plus a `nifty500` series rebased to the first available day's
total NAV. **Values are integer paise**, not rupees (see Deviations below).

```json
[
  {"date": "2026-10-26", "values": {"simons": 9986622, "lynch": 10000000, "nifty500": 10000000}}
]
```

### `GET /api/agents/{id}/positions?status=OPEN|CLOSED`
Unknown `id` → 404.

```json
[
  {
    "id": 476, "agent_id": "simons", "symbol": "CASTROLIND",
    "company_name": "Castrol India Ltd.", "sector": "Oil Gas & Consumable Fuels",
    "quantity": 180, "entry_price_paise": 18839, "current_price_paise": 18761,
    "exit_price_paise": null, "stop_loss_paise": 17700, "target_price_paise": 21000,
    "status": "OPEN", "unrealized_pnl_paise": -14040, "unrealized_pnl_pct": -0.41,
    "realized_pnl_paise": null, "realized_pnl_pct": null,
    "opened_at": "2026-10-28", "closed_at": null, "hold_days": null,
    "forensic_tag": null, "is_frozen": false,
    "thesis_summary": "Setup B mean-reversion triggered by severe price dislocation (zscore -2.43), oversold RSI (37.1), and strong absorption volume surge (2.09)."
  }
]
```

### `GET /api/agents/{id}/orders`
`pending_orders` left-joined with `fills`.

### `GET /api/agents/{id}/decisions`
`decisions` with `cited_metrics_json` parsed into a list.

### `GET /api/backtest/...`
`windows`, `runs`, `runs/{window_id}/leaderboard`, `runs/{window_id}/nav`,
`runs/{window_id}/positions`, `runs/{window_id}/holding-duration` (new, Phase 2),
`runs/{window_id}/comparison` — all tagged `"evidence_label": "BACKTEST_DERIVED"`, money in paise,
`window_id` validated (400 if it contains a path separator or `..`) before ever touching disk.

## Endpoints (Phase 2)

### `GET /api/agents/{id}/memory?status=`
Heuristics from `agent_memory`, plus a "recent success rate" computed over the most recent
`settings.HEURISTIC_ROLLING_WINDOW` resolved `heuristic_applications` (fewer if that many don't
exist yet; `null` if none have resolved at all). `lifecycle_reason` is the most recent
`HEURISTIC_STATUS_CHANGED` reason for that heuristic from `activity_log.metadata_json` — the
reason is never stored on `agent_memory` itself (see `learning/memory_manager.py::update_lifecycle`).
Unknown agent → 404; no heuristics → `[]`.

```json
[
  {
    "id": 19, "agent_id": "simons", "kind": "AVOID",
    "rule_text": "Avoid entering when price is overextended with zscore_close_20 above 1.3 and rsi_14 above 67.",
    "context": "ENTRY", "status": "reinforced", "confidence": 0.7284,
    "applications": 79, "successes": 58, "recent_success_rate": 100.0,
    "created_at": "2026-08-02T10:00:00+05:30", "updated_at": "2026-10-29T15:45:00+05:30",
    "lifecycle_reason": "promotion_epoch"
  }
]
```

### `GET /api/baseline/comparison?persona=`
`persona` must be one of `simons`, `lynch`, `marks`, `jhunjhunwala`, `varsity` — anything else is
422 with the valid set named in the message. Reuses the now-fixed
`evaluation.comparison.compare_*_vs_baseline` and `compare_selection_alpha` (which gained an
optional `agent_id` filter this phase — see Bug fixes). A horizon with no decisions at all is
`null` throughout, never `0`.

```json
{
  "persona_id": "simons",
  "llm_agent": {"return_pct": -5.12, "sharpe_ratio": -3.61, "win_rate_pct": 28.6, "max_drawdown_pct": -5.42, "trades": 56},
  "rules_agent": {"return_pct": -5.62, "sharpe_ratio": -4.49, "win_rate_pct": 31.0, "max_drawdown_pct": -5.69, "trades": 42},
  "deltas": {"excess_return_pct": 0.5, "excess_sharpe": 0.88, "excess_alpha_pct": 0.5, "excess_win_rate_pct": -2.4},
  "is_provisional": false,
  "sample_notice": "VALIDATED (>=30 closed trades)",
  "evidence_label": "LIVE_PILOT",
  "horizon_returns": [
    {
      "horizon_days": 1, "llm_buy_avg_pct": 0.21, "llm_hold_avg_pct": -0.1,
      "rules_buy_avg_pct": 0.19, "nifty500_avg_pct": 0.1, "selection_alpha_pct": 0.31,
      "llm_buy_count": 63, "rules_buy_count": 44
    }
  ]
}
```

### `GET /api/backtest/runs/{window_id}/holding-duration`
New this phase: Question B evidence (average and median `hold_days`, and closed-trade count,
per persona, for one backtest run).

### `GET /api/funnel?agent_id=`
Each agent's **latest** `FUNNEL_COUNTS` `activity_log` row (live DB only), newest `created_at`
per agent. Stage keys are returned exactly as stored, in their original order — never renamed or
invented. Unknown `agent_id` → 404; no rows → `[]`; a row whose `metadata_json` isn't valid JSON
is skipped (falling through to an older valid row for that agent if one exists), never a 500.

```json
[{"agent_id": "simons", "run_date": "2026-10-29", "stages": [{"key": "stage0", "count": 237}, {"key": "stage1", "count": 2}, {"key": "final", "count": 8}]}]
```

**The real funnel has 3 stages** (`stage0`, `stage1`, `final`) — it does **not** match
`docs/frontend_implementation_plan_week5.md`'s mock funnel (500 → 350 → 20 → 3-5, four stages).
The frontend should label whatever stage keys this endpoint actually returns, not assume the
mock's four-step shape or its stage names.

---

## Deviations from the Week 5 guide

The real schema (`db/schema.sql` + migrations 0002-0012) is sparser than the guide's samples in
several places. Per the decision to keep the guide's field names and fill every field from the
real schema (nulling what has no real source), here is every place the two diverge:

1. **No `portfolios` table.** The guide's leaderboard logic note mentions one; it doesn't exist.
   Leaderboard data comes from `agents` + `daily_nav` + `positions`, via the existing
   `evaluation.performance.evaluate_all_agents`.
2. **No `trade_forensics` table.** `forensics_type`/`regime_at_exit`/`diagnosis_json` live
   directly on `positions`. `forensic_tag` is `positions.forensics_type` verbatim — real values
   are things like `FALSE_BREAKOUT`, `TREND_CONTINUATION`, `BROAD_MARKET_DRAG`,
   `CORP_ACTION_ARTIFACT`, `UNCLASSIFIED` (from `src/learning/forensics.py`), **not** the guide's
   imagined `WIN_TREND_CONTINUATION`/`LOSS_STOP_HIT` vocabulary. Nothing was renamed or invented.
3. **`/api/agents/nav` and `/api/backtest/.../nav` emit integer paise, not rupees.** The guide's
   sample shows small rounded numbers (100000, 104250) that read as rupees; the explicit hard
   rule for this phase ("Money is integer paise in every response. No rupee floats anywhere")
   takes precedence. The existing `backtest.py` NAV handler previously divided by 100 into a
   rupee float — that's bug fix (d), also listed below. Divide by 100 client-side to display ₹.
4. **`positions.entry_date`/`exit_date` are dates (`YYYY-MM-DD`), not full timestamps.** The
   guide's `opened_at`/`closed_at` samples show full ISO datetimes; the schema only stores a
   date for these two columns, so that's exactly what's returned, unconverted (a date has no
   time-of-day to attach a timezone to).
5. **Orders have no single `limit_price_paise`, `order_type`, or `slippage_paise`.** The system
   only ever places entry-*band* limit orders (`entry_low_paise`/`entry_high_paise`); those two
   real columns are returned alongside a `null` `limit_price_paise` rather than picking one bound
   arbitrarily. `order_type` is always implicitly "band limit order" but that string isn't
   persisted anywhere, so it's `null`. `fills.price_paise` already includes slippage baked in;
   with no stored reference price, the slippage component can't be isolated without guessing, so
   `slippage_paise` is `null`.
6. **Decisions have no `candidate_rank`, `stage_reached`, or `allocated_paise`.** None of the
   three is recorded anywhere in `decisions`; all three are always `null`. `sizing_fidelity_score`
   *is* a real column and is returned as-is.
7. **`cited_metrics` is a flat `{name: value}` dict in storage**, not the guide's rich
   per-metric object (`actual_snapshot_value`/`tolerance`/`is_faithful`). Each entry is returned
   as `{"name", "cited_value"}` with the other three fields present but `null` — the only real
   per-decision faithfulness number the system computes is the aggregate `faithfulness_score`
   (`evaluation/faithfulness.py::compute_faithfulness`), which has no per-metric breakdown to
   expose.
8. **`/api/health`'s shape is a wrapped object** (`{"database_reachable": ..., "jobs": [...]}`),
   not a bare array — the phase-1 instructions explicitly require a `database_reachable` flag
   alongside the per-job list, which a bare array can't carry.
9. **`records_processed` is always `null`.** `pipeline_runs.detail` is free text (not a
   structured record count) for every writer in this codebase; nothing numeric is parseable out
   of it reliably.
10. **`PENDING`/`pending_orders.status` values are uppercased** in the response (`"FILLED"`, not
    `"filled"`) to match the guide's sample casing — a pure string transform, not new data.
11. **The suggested run command doesn't work as written** — see "Running it" above.
12. **`/api/agents/{id}/decisions`'s `cited_metrics` is `null` only when the column is really
    empty** (`NULL`, `''`, or `'{}'` — a HOLD decision cites nothing) — confirmed against real
    data (`storage/ledger/portfolio.db` has 21/82 decisions with non-empty `cited_metrics_json`;
    `storage/backtest/rolling_w2_heuristics_on.db` has 679/18831). Phase 1 returned `[]` for the
    empty case; Phase 2 corrected this to `null`, per instruction.
13. **`horizon_returns`' field names are generic** (`llm_buy_avg_pct`, `rules_buy_avg_pct`, …),
    not baked with a persona name the way the guide's sample shows it for Simons specifically
    (`llm_simons_buy_avg_pct`, …) — this is one endpoint serving all 5 personas via `?persona=`,
    so persona-specific field names would force the frontend to parse 5 different shapes.
14. **`selection_alpha_pct` is the LLM persona's own candidate-selection alpha** (its BUY decisions'
    average forward return minus its HOLD-rejected candidates' average), not the LLM-vs-rules
    performance delta — that's already covered by `deltas.excess_return_pct`. This matches
    `evaluation/comparison.py::compare_selection_alpha`'s existing definition and the frontend
    plan's own description ("verifying whether BUY decisions outperform candidates rejected as
    HOLD").
15. **`/api/backtest/runs`'s shape changed**: each entry is now `{pair_id, heuristics_on,
    heuristics_off}` instead of a flat list of runs, so the dashboard can show a heuristics-ON
    run next to its OFF counterpart. A run with no counterpart on disk still appears, with the
    missing side `null`. No `_heuristics_on`/`_heuristics_off`-suffixed window still appears,
    filed under `heuristics_on` by convention (never silently dropped).
16. **The real funnel has 3 stages, not the mock's 4** — see "GET /api/funnel" above.

## Bug fixes this phase

- **`evaluation/comparison.py::compare_selection_alpha`** queried `forward_returns.id`,
  `return_pct`, `benchmark_return_pct`, `excess_return_pct` — none of which exist (the real
  columns are the composite primary key `(decision_id, horizon_days)`, `ret_pct`,
  `nifty_ret_pct`). Fixed to `count(*)`, `AVG(ret_pct)`, `AVG(nifty_ret_pct)`, with
  `avg_excess_pct` now computed in Python as the difference of the two.
- **`src/api/routes/backtest.py`'s positions query** selected `opened_at`/`closed_at`, which
  don't exist on `positions`. Fixed to `entry_date`/`exit_date`.
- **`src/api/routes/backtest.py` used `settings.SIMULATION_DB_PATH`**, which doesn't exist.
  Replaced with a new `settings.BACKTEST_DB_DIR` (default `storage/backtest`); `window_id` is now
  rejected with 400 if it contains a path separator or `..`, before ever touching the filesystem.
- **`backtest.py` now opens every database read-only** (`api.deps.get_ro_conn`, same connection
  factory the live routes use) and returns integer paise from the NAV endpoint instead of a
  rounded rupee float (see Deviation 3 above). The positions endpoint's `avg_entry_price` (a
  rupee float) was also replaced with `avg_entry_price_paise` (an integer) for the same reason.

### Phase 2

- **`evaluation/comparison.py::compare_selection_alpha`** gained an optional `agent_id` filter
  (default `None`, preserving its original global behavior) so `/api/baseline/comparison` can
  compute per-persona BUY/HOLD forward returns. Also now exposes `avg_benchmark_pct` in each
  stats dict (previously computed internally but never returned), which `/api/baseline/comparison`
  uses for `nifty500_avg_pct`.
- Everything else flagged in Phase 1 for Phase 2 (`/memory`, `/baseline/comparison`) is now built
  — see "Endpoints (Phase 2)" above.

## Test suite

- **Before Phase 1:** 488 passed.
- **After Phase 1:** 519 passed (31 new, 0 regressions).
- **After Phase 2:** 541 passed (22 more new, 0 regressions).
- Run with: `python -m pytest tests -q`
- Phase 1 test files: `tests/unit/test_api_health.py`, `test_api_activity.py`,
  `test_api_leaderboard.py`, `test_api_portfolio.py`, `test_api_isolation.py`,
  `test_api_bugfixes.py`.
- Phase 2 test files: `tests/unit/test_api_memory.py`, `test_api_baseline.py`,
  `test_api_funnel.py`, `test_api_backtest_phase2.py`, plus one added test each to
  `test_api_portfolio.py` (cited_metrics null case), `test_api_activity.py` (multi-page severity
  pagination), and `test_api_isolation.py`'s static guard list (memory/baseline/funnel added).
- Shared (non-test) helper module: `tests/unit/_api_test_helpers.py` builds a real on-disk temp
  SQLite file per test — the API's `mode=ro` URI connection can't attach to an in-memory
  `:memory:` database from a second connection, which is what `tests/conftest.py`'s usual fixture
  uses.

## Real smoke run

**Phase 1** — ran the live app against a copy of `storage/backtest/rolling_w2_heuristics_on.db`
(the richest database on disk — 478 positions, 10 agents): `GET /api/health`, `GET
/api/leaderboard`, `GET /api/agents/simons/positions` all returned real, correctly-shaped data.

**Phase 2** — ran it again against a fresh copy of the same database, curling the four
newly-required endpoints:

- `GET /api/agents/simons/memory` → real heuristics (e.g. an AVOID rule, `reinforced`, 79
  applications, 58 successes, `lifecycle_reason: "promotion_epoch"`)
- `GET /api/baseline/comparison?persona=simons` → real LLM-vs-rules stats and all 5 horizons
  populated with real forward-return numbers
- `GET /api/backtest/runs` → the real on-disk windows (`rolling_w1`, `rolling_w2`,
  `supplementary_range`), each paired (`heuristics_off: null` for all three, since no `_off`
  variant exists on disk yet)
- `GET /api/funnel` → real 3-stage funnel counts for every agent

Both temp copies were deleted after their smoke runs; nothing under `storage/` was modified
either time.
