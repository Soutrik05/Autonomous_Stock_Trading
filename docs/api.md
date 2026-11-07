# StockMinds REST API — Phase 1

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

### `GET /api/backtest/...` (bug fixes only this phase; routes unchanged otherwise)
`windows`, `runs`, `runs/{window_id}/leaderboard`, `runs/{window_id}/nav`,
`runs/{window_id}/positions`, `runs/{window_id}/comparison` — all pre-existing, all still tagged
`"evidence_label": "BACKTEST_DERIVED"`.

### Not built yet (Phase 2)
`GET /api/agents/{id}/memory` and `GET /api/baseline/comparison` — their route files
(`src/api/routes/memory.py`, `src/api/routes/baseline.py`) are still docstring-only stubs with no
`router` object, so they are not imported in `src/api/main.py` yet.

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

## Test suite

- **Before this phase:** 488 passed.
- **After this phase:** 519 passed (31 new tests, 0 regressions).
- Run with: `python -m pytest tests -q`
- New test files: `tests/unit/test_api_health.py`, `test_api_activity.py`,
  `test_api_leaderboard.py`, `test_api_portfolio.py`, `test_api_isolation.py`,
  `test_api_bugfixes.py`, plus a shared (non-test) helper module
  `tests/unit/_api_test_helpers.py` that builds a real on-disk temp SQLite file per test (the
  API's `mode=ro` URI connection can't attach to an in-memory `:memory:` database from a second
  connection, which is what `tests/conftest.py`'s usual fixture uses).

## Real smoke run

Ran the live app (`uvicorn api.main:app`) against a **copy** of
`storage/backtest/rolling_w2_heuristics_on.db` (the richest database on disk — 478 positions, 10
agents) — never the original file, and never `storage/ledger/portfolio.db`. All three required
endpoints returned real, correctly-shaped data on the first try:

- `GET /api/health` → `{"database_reachable": true, "jobs": [...6 jobs...]}`
- `GET /api/leaderboard` → 10 entries, real Sharpe/drawdown/win-rate/faithfulness numbers
- `GET /api/agents/simons/positions` → 58 real positions, correct paise math, correct forensic
  tags where present

The temp copy was deleted after the smoke run; nothing under `storage/` was modified.
