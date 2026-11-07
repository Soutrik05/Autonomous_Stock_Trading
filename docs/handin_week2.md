# StockMinds — Week 2 Handin & System Status Report

> **Target Audience:** Engineering Teammate / Co-developer  
> **Date:** October 31, 2026  
> **Status:** Week 2 Complete | Baseline Test Suite Passing (308/308) | Clean Architecture (`src/`) Deployed

---

## 1. Executive Summary

Week 2 focused on completing the multi-agent persona implementations, delivering the fundamentals and news sentiment data ingestion pipelines, establishing the 4-stage watchlist curation funnel, and refactoring the codebase into a standard `src/` layout with decoupled storage.

All 5 LLM personas and the rules baseline are fully operational, calibrated, and verified against ground-truth database records. The automated test suite executes **308 tests across 36 modules in ~26 seconds** with zero warnings and zero failures under strict `-W error` mode.

---

## 2. Codebase Architecture & Storage Layout

The repository has been restructured from a flat root into standard Python packaging (`src/` layout):

```
Autonomous_Stock_Trading/
├── pyproject.toml               # Package configuration & pythonpath = ["src", "."]
├── pytest.ini                   # Pytest configuration with testpaths = ["tests"]
├── settings.py                  # Single source of runtime configuration
├── scheduler.py                 # Thin APScheduler entry point (IST timezone)
├── requirements.txt             # Locked Python dependencies
├── Dockerfile                   # Container specification
├── README.md                    # Project overview
├── .gitignore                   # Ignores databases, caches, and backups
│
├── src/                         # All production source code (no relative import hacks)
│   ├── api/                     # FastAPI route handlers (portfolio, activity, health, memory)
│   ├── core/                    # Low-level primitives: DB factory, money (paise), calendar, clock
│   ├── ingestion/               # External data connectors: OHLCV, fundamentals, macro, news
│   ├── features/                # Technical indicator math (Wilder ATR/RSI/ADX), feature snapshot builder
│   ├── watchlist/               # 4-stage multi-agent watchlist funnel & percentile rankers
│   ├── agents/                  # Decision runner, context assembler, JSON parsers, calibrator
│   │   └── personas/            # 5 persona configs: simons, varsity, marks, lynch, jhunjhunwala
│   ├── baselines/               # Pure Python rules-only momentum agent (baseline-simons-rules)
│   ├── broker/                  # Virtual exchange: cash reservation, orders, fills, expiry, settlement
│   ├── learning/                # Post-trade forensics, heuristic memory lifecycle (Week 3 focus)
│   ├── evaluation/              # Forward returns backfill, metric faithfulness scoring
│   ├── llm/                     # Provider abstractions: Gemini primary, Claude fallback, FakeLLM
│   └── notifications/           # Pipeline failure and risk cap breach alerting
│
├── storage/                     # Decoupled runtime databases (excluded from git)
│   ├── market/                  # Rebuildable market feeds (ohlcv.db, macro.db, news.db, fundamental.db)
│   └── ledger/                  # Irreplaceable accounting records (portfolio.db)
│
├── backups/                     # Sibling to storage: point-in-time SQLite online backup snapshots
├── scripts/                     # Operational entrypoints (init_db.py, backup.py, build_symbol_master.py)
├── tests/                       # Unit & integration test suites (sibling to src/)
├── docs/                        # Specifications (Plan_v3.md, personas.md, FEATURE_DOCUMENTATION.md)
└── dashboard/                   # React/Vite dashboard frontend (standalone JS package)
```

---

## 3. What Was Built & Delivered in Week 2

### A. Fundamentals, News Sentiment & Macro Ingestion
1. **Fundamentals Ingestion [`src/ingestion/sync_fundamentals.py`]:**
   - Ingests audited annual and quarterly financial statements (income statement, balance sheet, cash flows) from Upstox.
   - Computes key ratios: P/E, P/B, ROCE, ROE, PEG, Debt-to-Equity, CFO/PAT, and YoY PAT/Revenue growth.
   - Ingests quarterly category shareholding (`promoters`, `fii`, `dii`, `public`) and corporate actions ground truth.
   - Stored in `storage/market/fundamental.db` (`fundamental_ratios` table: 500 active stocks).
2. **News Sentiment Pipeline [`src/ingestion/sync_news.py`]:**
   - Fetches ticker-specific news headlines.
   - Scores sentiment in $[-1.0, +1.0]$ via FinBERT inference pipeline (with graceful heuristic fallback).
   - Stored in `storage/market/news.db` (`news_articles` table: 360 articles).
3. **Macro Regime Tracking [`src/ingestion/sync_macro.py`]:**
   - Fetches India VIX and classifies daily regime: `LOW_VOL` (<14), `NORMAL` (14–18), `ELEVATED` (18–24), `PANIC` (>24).
   - Tracks FII and DII daily cash flows.
   - Stored in `storage/market/macro.db` (`macro_daily` table).

---

### B. All Five Personas & The Decoupled Horizon Architecture

The five quantitative personas and their corresponding configurations are implemented in [`src/agents/personas/`]:

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                   MASTER PERSONA SPECIFICATION MATRIX                                  │
├────────────────────┬─────────────────────┬──────────────┬──────────┬──────────┬──────────┬─────────────┤
│ Agent ID           │ Archetype           │ Holding Band │ TTL Days │ Lookback │ Eval Hor │ Min Win Hld │
├────────────────────┼─────────────────────┼──────────────┼──────────┼──────────┼──────────┼─────────────┤
│ simons             │ Quant Momentum      │ 1–14 d       │ 3 d      │ 14 d     │ 5 d      │ 1 d (≥4%)   │
│ varsity            │ Balanced Hybrid/DCF │ 20–75 d      │ 14 d     │ 90 d     │ 20 d     │ 10 d (≥5%)  │
│ marks              │ Contrarian Value    │ 21–120 d     │ 10 d     │ 90 d     │ 60 d     │ 14 d (≥6%)  │
│ lynch              │ GARP Compounder     │ 30–90 d      │ 14 d     │ 120 d    │ 60 d     │ 15 d (≥10%) │
│ jhunjhunwala       │ Growth Compounder   │ 90–180 d     │ 14 d     │ 150 d    │ 90 d     │ 45 d (≥15%) │
│ baseline-simons    │ Rules Momentum      │ 1–14 d       │ 3 d      │ 14 d     │ 5 d      │ 1 d (≥4%)   │
└────────────────────┴─────────────────────┴──────────────┴──────────┴──────────┴──────────┴─────────────┘
```

#### Key Architecture Notes:
- **Decoupling Principle:** `ttl_days` (Stage-3 watchlist lock) governs **entry signal decay** (how long an unbought candidate stays locked on the watchlist without replacement). In contrast, `eval_horizon_days` governs **thesis maturity time** (when post-trade forensics evaluates whether the trade worked). Decoupling these clocks prevents fast entry setups (e.g. Marks' oversold bounce) from clogging the watchlist for 60+ days.
- **Closed-Form DCF Model:** Implemented in [`src/features/builder.py`] for Varsity (`stockminds-core`). Computes clamp-bounded Free Cash Flow to Firm (FCFF) discounted at 11.5% WACC with 5.0% terminal growth, deriving `dcf_discount_pct`.
- **Pyramiding on Strength:** Implemented for Rakesh Jhunjhunwala (`jhunjhunwala`). Allows issuing additional BUY decisions on already-held positions up to the 20% position cap when quarterly PAT growth and volume conviction confirm the compounding thesis.

---

### C. Watchlist Funnel [`src/watchlist/watchlist_refresh.py`]
A deterministic 4-stage funnel curates candidate pools nightly:
- **Stage 0 (Turnover & Liquidity):** Nifty 500 universe $\rightarrow$ filters for turnover $\ge$ ₹5 Cr, $\ge 200$ historical sessions, and volume conviction.
- **Stage 1 (Archetype Hurdles):** Evaluates persona-specific technical and fundamental predicates.
- **Stage 2 (Percentile Ranking):** Computes normalized composite scores within sector cohorts ($\ge 5$ stocks) to avoid sector concentration bias.
- **Stage 3 (Persistence & Capacity):** Locks candidates for `ttl_days`. Ejects broken stocks early if they fail Stage 0 or drop below the 200 EMA (`require_above_ema200`). Enforces `sector_cap` and caps the candidate review pool at `max_candidates`.

---

### D. Decision Calibration, Counterfactuals & Faithfulness
- **Calibration Layer [`src/agents/parsers.py`]:** Automatically clamps stops to $\ge \text{atr\_stop\_multiplier} \times \text{ATR-14}$ and downsizes share count if proposed capital risk exceeds `target_risk_pct` or `max_position_pct`.
- **Counterfactuals & Sizing Fidelity [`db/migrations/0004_*.sql`]:** Records formula-derived sizing alongside the LLM's raw output, computing `sizing_fidelity_score` in $[0.0, 1.0]$.
- **Faithfulness Scoring [`src/evaluation/faithfulness.py`]:** Verifies that numerical values cited in `cited_metrics` match the exact values in `feature_snapshots`. Historical BUY decisions currently maintain an average faithfulness score of **1.0** (0 hallucinations).

---

### E. Broker & Accounting Ledger Verification
- **Virtual Exchange Engine [`src/broker/engine.py`]:**
  - Pre-trade cash reservation: When Simons placed order #7 for `INDHOTEL` (95 shares), ₹75,808.62 was reserved, reducing cash from ₹1,00,000 to ₹25,576.22. A subsequent BUY for `CRISIL` was rejected with `INSUFFICIENT_CASH`. The cash invariant holds.
  - Intraday fill simulation: Orders fill when price enters $[entry\_low, entry\_high]$, taking slippage (10 bps) and statutory charges into account.
  - 15:30 Expiry: Unfilled orders are marked `cancelled` with reason `EXPIRED`, and reserved cash is immediately credited back to the agent.
  - 15:35 Settlement: Marks positions to market and writes official NAV records to `daily_nav`.

---

## 4. Current State of the Live Databases

| Database | Table | Rows | Range / Key Stats | Invariant Status |
| :--- | :--- | :--- | :--- | :--- |
| `storage/market/ohlcv.db` | `ohlcv` | 221,994 | 2025-01-01 to 2026-10-29 | Valid. 499 active tickers on Oct 29 (`JSWDULUX` flagged `STALE_DATA`). |
| `storage/market/macro.db` | `macro_daily` | 5 | 2026-10-16 to 2026-10-29 | Valid. VIX: 14.06–17.63; Regime: `NORMAL`. |
| `storage/market/news.db` | `news_articles` | 360 | 2026-10-21 to 2026-10-29 | Valid. Sentiment scored via FinBERT. |
| `storage/market/fundamental.db` | `fundamental_ratios` | 500 | 2026-10-19 to 2026-10-29 | Valid. Exactly matches 500 constituent stocks (`TATAMOTORS` purged). |
| `storage/ledger/portfolio.db` | `symbols` | 500 | Active Nifty 500 constituents | Valid. Mapped across 20 NSE sectors. |
| `storage/ledger/portfolio.db` | `agents` | 6 | All 5 LLM + 1 baseline | Valid. `varsity` retained as canonical ID (`stockminds-core` purged). |
| `storage/ledger/portfolio.db` | `feature_snapshots` | 1,997 | 4 dates (Oct 16, 22, 23, 29) | Valid. Joined technicals, fundamentals, macro, and news. |
| `storage/ledger/portfolio.db` | `pending_orders` | 22 | Oct 23 to Oct 30 | Valid. Fills, cancellations, and cash reservations verified. |
| `storage/ledger/portfolio.db` | `positions` | 2 | 2 OPEN positions | Valid. Simons (95 INDHOTEL), Baseline (12 INDHOTEL). |
| `storage/ledger/portfolio.db` | `daily_nav` | 6 | Oct 26 settlement pass | Valid. Recorded across all 6 agents alongside Nifty 500 close. |

---

## 5. Audit Findings & Known Technical Debt

1. **Market Breadth & Index Trends in `macro.db` [RESOLVED]:**
   - *Status:* Implemented in [`src/ingestion/sync_macro.py`](file:///c:/Users/KIIT0001/Projects/mini-proj/New%20Build/Autonomous_Stock_Trading/src/ingestion/sync_macro.py) and verified across all historical rows.
   - *Implementation:*
     - `advance_decline` is computed dynamically from `storage/market/ohlcv.db` across the constituent daily returns for that session (advances vs declines).
     - `nifty50_trend` and `nifty500_trend` are derived hierarchically: 20-day SMA trend from index candles (`NSE_INDEX|Nifty 50`, `NSE_INDEX|Nifty 500`), single-day quote net change, or market breadth fallback.
     - Backfilled all 5 historical sessions (`2026-10-16` to `2026-10-29`) and covered by 9 unit tests in [`tests/unit/test_sync_macro.py`](file:///c:/Users/KIIT0001/Projects/mini-proj/New%20Build/Autonomous_Stock_Trading/tests/unit/test_sync_macro.py).
2. **Scheduler Daemonization Required on Deployment:**
   - [`scheduler.py`] is a blocking script. When deployed to AWS EC2, it must be managed as a **systemd service** (or Docker container with `restart: unless-stopped`) so terminal disconnects do not terminate the cron loops.
3. **Automated Consecutive Stale Ticker Alerting:**
   - In [`src/features/builder.py`], add automated alerting via `notifications/alerts.py` if an active constituent is marked `STALE_DATA` for $> 2$ consecutive trading days.
4. **Off-Volume S3 Backup Sync:**
   - [`scripts/backup.py`] currently writes point-in-time snapshots to [`backups/`]. On EC2, this lives on the same EBS volume. Add `aws s3 cp` in `backup.py` to establish off-volume Tier-2 durability.

---

## 6. Recorded Test Suite Gaps (Tracked in `Plan_v3.md` Part VII)

1. **Concurrency & SQLite WAL Writer Contention:** Tests currently run single-threaded in `:memory:`. A multi-threaded test is needed to verify that `BEGIN IMMEDIATE` transactions under concurrent load (intraday monitor vs API reads) do not raise unhandled `sqlite3.OperationalError: database is locked`.
2. **Mid-Batch Network Timeout Simulation:** Tests mock clean API responses. An integration test simulating an HTTP 504 Gateway Timeout midway through a 500-stock batch is needed to verify clean rollback and restartability.
3. **Empty Stub File (`tests/unit/test_heuristic_triggers.py`):** Currently a 4-line placeholder. Heuristic transition states (`DISCOVERED` $\rightarrow$ `ACTIVE` $\rightarrow$ `REINFORCED` / `DEPRECATED`) will be implemented and tested in Week 3.
4. **Multi-Day Order Rollover Test:** Need an automated scenario verifying agent behavior when an unfilled pending order expires at 15:30 and the agent re-evaluates the same ticker on subsequent trading days.

---

## 7. Week 3 Implementation

Per [`docs/Plan_v3.md`], Week 3 transitions the system from data ingestion and order execution into autonomous learning and user-facing observability:

1. **Reflection & Episodic Memory Engine [`src/learning/`]:**
   - Implement `src/learning/engine.py` and `memory_manager.py`.
   - Post-trade forensics [`src/learning/forensics.py`] is already written (552 lines). Wire it to run on closed trades at daily settlement.
   - Implement automated heuristic generation (`SEEK` and `AVOID` rules), transition states (`DISCOVERED` $\rightarrow$ `ACTIVE` $\rightarrow$ `REINFORCED` / `DEPRECATED`), and injection into the prompt's `<HEURISTICS>` block.
   - Complete [`tests/unit/test_heuristic_triggers.py`].
2. **FastAPI Backend Endpoints [`src/api/`]:**
   - Expose endpoints for the dashboard: `/portfolio/summary`, `/leaderboard`, `/activity`, `/baseline/compare`, and `/memory/heuristics`.
   - Read directly from `portfolio.db` using read-only connections with WAL mode.

---

## 8. Operational Command Cheat-Sheet

```powershell
# 1. Run full test suite with warnings treated as errors
pytest tests/ -W error

# 2. Run a specific test module
pytest tests/unit/test_varsity_dcf.py -W error
pytest tests/integration/test_multi_agent_funnel.py -W error

# 3. Manually trigger a nightly pipeline pass (as of specific date)
python -m scheduler --date 2026-10-29

# 4. Run agent decision runner for a specific persona
python -m agents.runner --agent simons --date 2026-10-29 --fake-llm

# 5. Run Stage 0-3 watchlist funnel for all personas
python -m watchlist.watchlist_refresh --agent all --date 2026-10-29

# 6. Execute manual SQLite database backup
python scripts/backup.py

# 7. Start the background scheduler daemon
python scheduler.py
```
