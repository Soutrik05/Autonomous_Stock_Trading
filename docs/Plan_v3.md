# StockMinds — Autonomous Multi-Agent Trading Arena
## Engineering Architecture & Implementation Plan — **v3**

> **Version:** v3 · **Date:** 12 Oct 2026 · **Supersedes:** Plan v2 (`StockMinds_Engineering_Plan.md`) and the old Plan.md / DECISIONS.md.
> **Status:** Ready for build start.
> Items marked **[Default — confirm]** are values proposed in v3 that the team should confirm in one meeting. They are listed together in the Appendix.

---

## Changes since v2

**Data contracts (the main theme of v3)**
- All money is stored as **integer paise**. `reserved_cash` is no longer a stored counter. It is the **sum of pending BUY orders** (`reserved_amount_paise` per order).
- One versioned **`FeatureSnapshot`** per (ticker, date) is the single definition of every metric. Cited metrics, prompts, screeners, forensics, heuristics and the baseline all read from it. Each feature has its own tolerance.
- Heuristic triggers are now **JSON rules evaluated by Python**, with a `kind` (`SEEK` / `AVOID`) and a `heuristic_applications` table so every rule can be scored.
- New evaluation tables: `daily_nav`, `agent_watchlist`, `decisions`, `forward_returns`, `feature_snapshots`, `market_calendar`, `pipeline_runs`, `reflection_runs`, `heuristic_applications`, `symbols`.
- `llm_calls` is per call. Cited metrics and faithfulness are stored **per decision**.

**Order and position rules**
- SELL, ADJUST, averaging and overwrite are now fully defined (§4.3).
- One OPEN position per agent and ticker is enforced by the database.
- Orders link to decisions, fills and positions. Positions store entry reasoning, exit reason and hold days.
- Fill rule: small overshoot allowed, crash-cancel added, slippage included, monitor polls every **10 minutes**, and expiry is its own job at 15:30.

**Time, sequencing and testing**
- All business dates and timestamps are **IST**, supplied by an injected `Clock`. Nothing uses database default timestamps.
- `market_calendar` decides the next trading day.
- `pipeline_runs` stops the 22:00 runner from starting on partial data. Fills are atomic and safe to re-run.
- Three interfaces (`Clock`, `QuoteProvider`, `LLMClient`) allow live and replay runs to use the same code.
- Numbered SQL **migrations** with a `schema_version` table from the first commit.

**Design changes**
- The token budget uses **compact numeric candidate rows** and realistic limits.
- Personas are **config objects** run by one runner.
- The rules-only baseline is a **sixth agent** trading through the same broker. It runs on the same candidates as LLM Simons, and it logs from the first live night.
- Forensics runs **at trade close**. Reflection has a **watermark**, so trades are not re-read. The daily regime is rule-based (VIX bands).
- Corporate actions on **held positions** are handled (freeze and alert).
- Backup is one method: the SQLite backup API, nightly.
- Deployment and the scheduler move to **the end of week 1**, so the data clock starts early.

---

## Navigational Index
- [System Overview & Foundation](#system-overview--foundation)
- [Part I — Data Engine & Shared Substrate](#part-i--data-engine--shared-substrate)
- [Part II — Personas, Broker & Learning](#part-ii--personas-broker--learning)
- [Part III — Database, Configuration & Repository Tree](#part-iii--database-configuration--repository-tree)
- [Part IV — REST API & Frontend](#part-iv--rest-api--frontend)
- [Part V — Roadmap & Definition of Done](#part-v--roadmap--definition-of-done)
- [Part VI — Risks & Mitigations](#part-vi--risks--mitigations)
- [Appendix — Defaults to Confirm](#appendix--defaults-to-confirm)

---

# System Overview & Foundation

### Problem Statement
Retail investors can see that different investing styles give different returns, but they cannot see why an automated strategy made a specific trade, why a position failed, or what the system learned from that loss. StockMinds builds a paper-trading arena where five LLM personas follow distinct investing schools on the Nifty 500 universe. Every trade decision, loss diagnosis and learned heuristic is logged and checked against computed market data. The project tests whether an LLM decision layer adds measurable value over a rules-only baseline and over the Nifty 500 index.

### Research Question
*Can LLM agents following different investing philosophies trade Nifty 500 stocks with discipline and explainability, and does an LLM decision layer add demonstrable value over a rules-only baseline and the benchmark index?*

### Core Architectural Principles
1. **Five independent LLM personas plus one rules baseline.** Jim Simons (Quant Momentum), Peter Lynch (GARP), Howard Marks (Contrarian), Rakesh Jhunjhunwala (Growth & Promoter Quality) and StockMinds Core (Zerodha Varsity Balanced) each hold a separate ₹1,00,000 paper account. A sixth agent, `baseline-simons-rules`, trades the same way through the same broker without an LLM. Agents never talk to each other.
2. **Autonomous execution.** Agents decide nightly on end-of-day data and write pending orders. Market-hours matching and stop-loss enforcement are pure Python with zero LLM calls. There is no human approval step.
3. **Decoupled, ordered pipeline.** Ingestion, feature building, watchlist refresh, LLM inference and broker execution are separate jobs. Each job records its status in `pipeline_runs`, and the next job refuses to start if the previous one did not succeed.
4. **One configuration file.** All thresholds, times, charge rates and model settings live in `settings.py`. Secrets live only in `.env`.
5. **Three injected interfaces.** `Clock` (IST time), `QuoteProvider` (live or replay) and `LLMClient` (any provider, or a fake for tests). The same code runs live, in replay, and in tests.
6. **IST everywhere.** Business dates and timestamps are IST (Asia/Kolkata), and are stored as ISO text produced by the `Clock`. No table uses `CURRENT_TIMESTAMP`.
7. **Integer money.** All rupee amounts are stored as integer paise (₹940.50 = 94050).
8. **Personas are configuration.** One runner serves all five personas. A persona is a config object (prompt, hurdles, sort key, TTL, windows), not a separate code path.

### Goals & Success Criteria
1. **Explainability & faithfulness.** Every decision carries a rationale and a `cited_metrics` dictionary. A deterministic checker compares each cited value to the saved `FeatureSnapshot` using the per-feature tolerance in §2.1, and stores a `faithfulness_score` per decision. A decision must cite at least 3 allowed metrics.
2. **Paired baseline.**
   - Each night, `baseline-simons-rules` evaluates the **same candidate list** that LLM Simons saw, and both decisions are stored in `decisions`.
   - Primary comparison: LLM Simons vs rules Simons (same candidates, same broker, same charges).
   - The other four personas are compared to the Nifty 500 and to each other.
   - Because closed trades will be few, a second comparison uses the **forward returns of every decision** (including HOLD), which gives many more data points.
3. **Causal forensics and heuristic memory.** Every closed trade gets a Python post-mortem at close. The LLM turns these into heuristics whose triggers are machine-checkable and are scored in later nights.
4. **Execution discipline.** The broker blocks invalid orders (price logic, cash, short selling). Prompt-level risk caps (2% risk per trade, 5% drawdown, 25% sector) are **not** blocking. Breaches are logged as `CAP_BREACH`, so we can measure how well each persona follows its own rules.
5. **Complete data capture.** Every night's feature snapshots, decisions, orders and NAV are stored. A missed night cannot be recreated, so capture is part of the first live run.

### System Limitations
- **Daily-candle decisions.** Agents decide on closed daily candles at night.
- **Polling resolution.** The monitor polls every 10 minutes (`MONITOR_INTERVAL_MIN`). Fills and stops happen at the prevailing poll price, so gaps between polls are not captured.
- **Modelled costs.** Statutory charges are exact. Slippage is a fixed estimate (`SLIPPAGE_BPS`), not market impact.
- **Small samples.** Long-horizon personas (Lynch 30–90 days) will have few closed trades. Sharpe ratio and win rate are labelled "provisional" until at least 30 trades exist.
- **One market regime.** An 8-week test sees one slice of the market. Results describe behaviour in this period, not "the best strategy".
- **LLM randomness.** Every prompt and response is stored in `llm_calls`, so any decision can be inspected.
- **Upstox verification.** Endpoint paths and response fields are checked in the Day-1 spike. Findings are written to `docs/upstox_findings.md`.
- **Educational use only.** This is a paper-trading research system. No real funds are managed. Every UI page carries a disclaimer.

---

# Part I — Data Engine & Shared Substrate

The shared kernel (`src/core/`) contains no LLM calls and no network I/O during agent execution. Market data is loaded into local SQLite files by scheduled ingestion jobs in `src/ingestion/`.

```text
storage/               # Local SQLite database volumes
├── market/            # Rebuildable market caches (git-ignored)
│   ├── ohlcv.db       # Daily OHLCV for Nifty 500
│   ├── fundamental.db # Statements & ratios (5-year history; 14-day re-fetch cadence)
│   ├── news.db        # FinBERT headline scores
│   ├── macro.db       # Daily regime rows + optional biweekly narrative
│   └── nifty500_constituents.csv
└── ledger/            # Irreplaceable application state (git-ignored, backed up)
    ├── portfolio.db   # Accounts, orders, fills, positions, decisions, memory, NAV
    └── simulation.db  # Isolated replay/historical simulation state

backups/               # Local point-in-time SQLite backups (sibling to storage/ on same disk)
    └── portfolio_YYYY-MM-DD.db
```

### 3-Tier Enterprise Backup Strategy
1. **Tier 1 (Local Fast Rollback):** Nightly `scripts/backup.py` snapshots `storage/ledger/portfolio.db` to `backups/` via SQLite Online Backup API. Located as a direct sibling to `storage/` on the persistent volume (never nested inside `storage/` to isolate failure domains from accidental directory removal or corruption).
2. **Tier 2 (Off-Host Disaster Recovery — S3):** Nightly backup push of `storage/ledger/portfolio.db` to Amazon S3 via the EC2 instance's attached IAM role (no static credentials in `.env`). The role is strictly scoped to `s3:PutObject` only (no `s3:DeleteObject`). S3 Object Lock in Compliance Mode prevents modification or deletion, and S3 Lifecycle rules automate 30-day rotation.
3. **Tier 3 (Block-Level Volume Recovery — EBS Snapshots):** Daily automated EBS snapshots configured via AWS Backup or Amazon Data Lifecycle Manager (DLM). Persistent data volumes have `DeleteOnTermination=false` enabled, with EC2 termination protection turned on.

## 1. Upstox Ingestion Engine

### 1.1 Endpoints
All market data comes from authenticated Upstox endpoints using a long-lived analytics token in `.env`:
- **Candles (V3 Active):** Upstox V3 Historical (`GET /v3/historical-candle/{instrument_key}/days/1/{to_date}/{from_date}`) combined with V3 Intraday (`GET /v3/historical-candle/intraday/{instrument_key}/days/1`) to capture the finalized current-day EOD candle during evening pipeline execution (20:00 IST) prior to overnight analytical cold-storage clearing (~23:30–02:00 IST). (V2 `/day/` endpoints are **Deprecated**).
- **Market Quotes (V3 Active):** Upstox V3 Batched Market Quotes (`GET /v3/market-quote/quotes?instrument_key=...`, up to 500 keys per call), providing live closing prices, 52-week high/low (`year_high`, `year_low`), official exchange circuit filters (`lower_circuit_limit`, `upper_circuit_limit`), top 5 order depth, and Closing Auction Session (CAS) equilibrium metrics.
- **Fundamentals (V2 Active, looked up by ISIN):** `/v2/fundamentals/{isin}/...` (key-ratios, income-statement [annual/quarterly], balance-sheet [annual], cash-flow [annual], share-holdings [quarterly category breakdown]).
- **Corporate actions ground truth (V2 Active):** `GET /v2/fundamentals/{isin}/corporate-actions` (dividends, splits, bonuses, rights with announcement dates, ex-dates, record dates, and ratios) stored in `storage/market/fundamental.db` (`corporate_actions` table).
- **Market information & institutional flows (V2 Active):** `GET /v2/market/fii` and `GET /v2/market/dii` (`data_type=NSE_EQ|CASH&interval=1D`) providing daily institutional cash flow gross buy/sell values in ₹ Crores (available from 1 Apr 2026).
- **News feed (V2 Active):** `GET /v2/news?category=instrument_keys&instrument_keys=...` returning curated 7-day headlines, summaries, and links mapped directly to NSE instrument keys (up to 30 keys per call).
- **VIX and indices (V3 Active):** India VIX (`NSE_INDEX|India VIX`) and sector index quotes via V3 Market Quotes.
- **Holidays, Status & Timings (V2 Active):** `GET /v2/market/holidays` for calendar seeding, `GET /v2/market/status/:exchange` for live session states (`NORMAL_OPEN`, `PRE_OPEN`, `POST_CLOSE`, `CLOSED`), and `GET /v2/market/timings/:date` for session schedules.
- **WebSockets (V3 & V2 Active):** Binary Protobuf Market Data Feed (`WSS /v3/feed/market-data-feed` via `/v3/feed/market-data-feed/authorize`) for low-latency market depth, and Portfolio Stream (`WSS /v2/feed/portfolio-stream-feed`) for order/execution push events.

> **API Findings Reference (deliverable: `docs/upstox_findings.md`).** Detailed endpoint parameters, response schemas, field mappings, deprecation status, and verified availability are maintained in `docs/upstox_findings.md`.

### 1.2 Symbol Master (`scripts/build_symbol_master.py`)
The `symbols` table maps each Nifty 500 ticker to: instrument key, ISIN, company name and sector. Sector comes from the NSE Nifty 500 constituents file (Industry column), plus a sector-index mapping used for relative strength. This is the **only** ticker → sector map in the project. Stage-3 sector caps, `CAP_BREACH`, percentile groups and forensics all read from it.

### 1.3 Multi-Tier Rate Limiter (`core/rate_limiter.py`)
A thread-safe sliding-window limiter keeps calls below the exchange limits, using values from `settings.py`:
- per second: `RATE_LIMIT_PER_SEC` (45; hard cap 50)
- per minute: `RATE_LIMIT_PER_MIN` (450; hard cap 500)
- per 30 minutes: `RATE_LIMIT_PER_30MIN` (1,800; hard cap 2,000)

```python
# core/rate_limiter.py
import time, threading
from collections import deque
from settings import settings

class UpstoxRateLimiter:
    def __init__(self):
        self._lock = threading.Lock()
        self._windows = [
            (deque(), 1.0,    settings.RATE_LIMIT_PER_SEC),
            (deque(), 60.0,   settings.RATE_LIMIT_PER_MIN),
            (deque(), 1800.0, settings.RATE_LIMIT_PER_30MIN),
        ]

    def acquire(self):
        with self._lock:
            while True:
                now = time.time()
                wait = 0.0
                for q, span, cap in self._windows:
                    while q and q[0] <= now - span:
                        q.popleft()
                    if len(q) >= cap:
                        wait = max(wait, span - (now - q[0]))
                if wait <= 0:
                    for q, _, _ in self._windows:
                        q.append(now)
                    return
                time.sleep(max(0.01, wait))
```

### 1.4 Job Schedule and Pipeline Ordering
One always-on service with a persistent disk runs all jobs through `scheduler.py` (APScheduler). Every job is a **one-shot command** that can also be run by hand. Each job writes a row to `pipeline_runs(job, run_date, status)`, and a downstream job checks the upstream row before it starts.

| Time (IST) | Job | Entry point | Needs |
|---|---|---|---|
| 20:00 Mon–Fri | Ingestion (OHLCV, fundamentals, news, macro) | `python -m ingestion.cli` | trading day |
| after ingestion | Feature snapshots | `python -m features.builder` | ingestion = SUCCESS |
| after features | Watchlist refresh | `python -m watchlist.watchlist_refresh` | features = SUCCESS |
| 21:45 | Backup of `portfolio.db` | `python scripts/backup.py` | — |
| 22:00 | Agent runner (6 agents) | `python -m agents.runner` | watchlist = SUCCESS |
| 09:20–15:20, every 10 min | Monitor (one poll per run) | `python -m broker.monitor` | trading day |
| 15:30 | Order expiry | `python -m broker.expiry` | — |
| 15:35 | Settlement and daily NAV | `python -m broker.settlement` | — |
| 15:45 | Forward-return backfill | `python -m evaluation.forward_returns` | settlement |
| Sunday 10:00 | Reflection & learning | `python -m learning.engine` | — |
| 1st & 15th, 09:30 | Macro narrative (optional, context only) | `python -m agents.macro_context` | — |

The 09:20 start avoids the opening-auction price. The 10-minute grid ends exactly at 15:20. The data janitor is **deferred** (not needed in an 8-week run).

### 1.5 Ingestion Guards (`src/ingestion/cli.py`)
1. **Calendar guard.** `market_calendar` is seeded from the holiday API (`/v2/market/holidays`) and refreshed nightly. On a holiday, price, fundamentals and macro syncs are skipped, news ingestion still runs, and the day is marked closed. "Next trading day" always comes from this table. Truncated sessions (Muhurat) are marked in `session_type`, and breakout signals are suppressed that day.
2. **Corporate-action detection.** A single-day drop rule is not enough, because splits have no volume signature and real crashes do. Each night re-fetch the last ~10 adjusted candles for every held ticker and every watchlist ticker, and compare them to the cache. If adjusted history differs by more than `CORP_ACTION_DIFF_PCT`, purge and reload that ticker's cache. In addition, ground-truth corporate events from Upstox's `GET /v2/fundamentals/{isin}/corporate-actions` stored in `storage/market/fundamental.db` (`corporate_actions` table) confirm whether the move is a verified split/bonus. If the ticker is **held**, set `positions.frozen_reason = 'CORP_ACTION'`, skip stop checks for it, log an alert with event specifics, and keep it frozen until the position's stop and target are adjusted by the split ratio (manual or scripted).
3. **Partial-failure resilience.** Retry each failed ticker 3 times with exponential backoff, then tag it `STALE_DATA`. Scheduled catch-up retries run at 20:30 and 21:00 IST. Agents skip stale tickers. Held stale tickers are flagged in the prompt.
4. **Circuit-lock detection.** Zero volume, a frozen quote, or price hitting `lower_circuit_limit` / `upper_circuit_limit` (from V3 quotes) tags the ticker `LOCKED_CIRCUIT`. Fills and stop checks skip it, and the event is logged.
5. **WAL and timeouts.** All SQLite connections use `PRAGMA journal_mode=WAL` and a 5,000 ms busy timeout.
6. **Backup.** One method only: the SQLite backup API (`Connection.backup`) copies `portfolio.db` to `backups/portfolio_YYYY-MM-DD.db` nightly. The last 14 copies are kept.
7. **Winsorization.** Extreme ratios are clamped: P/E in [0, 150], PEG in [0, 5], D/E in [0, 10].

---

## 2. Feature Engine & Data Contracts (`src/features/`)

### 2.1 FeatureSnapshot & Registry (`src/features/contracts.py`)
One **`FeatureSnapshot`** is built per (ticker, as-of date) by `src/features/builder.py` and saved in `feature_snapshots` with a `schema_version`. It is the **single source of truth** for all metrics. Prompts, `cited_metrics`, screeners, forensics, heuristic triggers and the baseline all read from this snapshot. Nothing else computes a metric on its own.

Every feature has a name, a unit, and a **deterministic match rule** for the faithfulness check:
- `REL(x)`: relative error within $x$ fraction.
- `ABS(x)`: absolute difference within $x$.
- `EXACT`: identical value.

| Group | Feature (allowed `cited_metrics` name) | Unit | Match rule |
|---|---|---|---|
| Price | `close` | ₹ | REL(0.5%) |
| Trend | `ema_20`, `ema_50`, `ema_200` | ₹ | REL(0.5%) |
| Trend | `ema_20_above_50` | flag | EXACT |
| Momentum | `rsi_14` | 0–100 | ABS(2.0) |
| Momentum | `macd_hist` | ₹ | ABS(0.1% of close) |
| Momentum | `adx_14` (Wilder's ADX) | 0–100 | ABS(2.0) |
| Statistical | `kaufman_er_20` (Kaufman Efficiency Ratio) | 0.0–1.0 | ABS(0.05) |
| Statistical | `zscore_close_20` (Z-Score of price vs 20d mean) | std dev | ABS(0.2) |
| Volatility | `atr_14` (Wilder's True Range) | ₹ | REL(5%) |
| Volatility | `parkinson_vol_ratio` (Parkinson vs ATR vol) | ratio | ABS(0.2) |
| Distribution | `skew_60` (60-day return asymmetry) | ratio | ABS(0.2) |
| Volume | `volume_surge` (Vol vs 20-day SMA) | × | REL(5%) |
| Volume | `obv_slope_sign` | −1/0/+1 | EXACT |
| Structure | `dist_52w_high_pct`, `dist_52w_low_pct` | % | ABS(1.0) |
| Quality | `roce_pct`, `roe_pct` | % | ABS(1.0) |
| Valuation | `pe`, `pb`, `peg` | × | REL(5%) |
| Valuation | `dcf_fair_value`, `dcf_discount_pct` | ₹ / % | REL(5%) / ABS(2.0) |
| Solvency | `debt_to_equity` | × | ABS(0.05) |
| Solvency | `interest_coverage` | × | REL(5%) |
| Cash flow | `cfo_to_pat` | × | ABS(0.05) |
| Growth | `pat_growth_yoy_pct`, `revenue_growth_yoy_pct` | % | ABS(1.0) |
| Ownership | `promoter_holding_pct`, `promoter_pledge_pct` | % | ABS(0.5) |
| Ownership | `fii_dii_qoq_delta_pct` | % | ABS(0.5) |
| News | `news_sentiment` | −1…+1 | ABS(0.05) |
| News | `news_article_count` | count | EXACT |
| Macro | `india_vix`, `regime` | value / label | ABS(0.5) / EXACT |
| Macro | `fii_net_cr`, `dii_net_cr` | ₹ Cr | REL(5%) |

> **Upstox API Field Notes:**
> - `debt_to_equity` is approximated via `(Current Liabilities + Non-Current Liabilities) / Equity Capital` because the Upstox balance sheet does not separate pure debt borrowings.
> - `interest_coverage` is not provided in Upstox income statements and defaults to `None` (omitted from screening hurdles without penalty).
> - `promoter_pledge_pct` is not provided by Upstox shareholding endpoints and defaults to `None`.
> - `fii_net_cr` and `dii_net_cr` are computed daily from `GET /v2/market/fii` and `GET /v2/market/dii` (`NSE_EQ|CASH`).

### 2.2 Vectorized Indicators (`src/features/indicators.py`)
Vectorized NumPy/Pandas indicators with zero network access:
- 20/50/200 Exponential Moving Averages (EMA).
- Wilder's RSI(14) using exponential smoothing.
- MACD(12, 26, 9) line, signal, and histogram.
- Wilder's ADX(14) with directional indicators (+DI, -DI).
- Wilder's ATR(14) true range.
- Kaufman Efficiency Ratio (`kaufman_er_20`): $\frac{|\text{Net Change}_{20}|}{\sum |\text{Candle Changes}_{20}|}$.
- Parkinson Extreme Volatility Ratio (`parkinson_vol_ratio`): High-Low volatility vs Close-Close volatility.
- Return Skewness (`skew_60`): 60-day rolling return distribution asymmetry.
- Z-score of close (`zscore_close_20`).
- Volume surge ($V / \text{SMA}_{20}(V)$) and On-Balance Volume (OBV) slope.
- Distance to 52-week high and low.

### 2.3 Fundamentals & Valuation (`src/features/builder.py`)
Computes fundamentals from statements and ratios stored in `storage/market/fundamental.db`:
- Winsorization and fallback defaults.
- Banking & Financial Services handling (ROA, ROE, P/B vs sector; debt-to-equity hurdle bypassed where inappropriate).
- **Zerodha Varsity DCF Valuation Model (`compute_dcf_valuation`):**
  - Base Cash Flow ($\text{FCFF}_0$): Bounded capex deduction as a fraction of CFO:
    $$\text{FCFF}_0 = \text{CFO} \times \left(1 - \text{clamp}\left(\frac{|\text{CFI}|}{\text{CFO}},\ 0.10,\ 0.50\right)\right)$$
  - Growth Rate ($g$): 4-period trailing PAT CAGR clamped to $[5\%, 15\%]$.
  - Dynamic Discount Rate ($r$): Derived via rolling market beta $r = R_f + \beta \times \text{ERP}$, clamped to $[10\%, 16\%]$.
  - Shares Outstanding: Derived primarily via $\frac{\text{Market Cap}}{\text{Current Price}}$, falling back to $\frac{\text{PAT} \times 10^7}{\text{EPS}}$ if market cap is unavailable.

### 2.4 News & Sentiment (`src/features/sentiment.py`)
- Official Upstox news feed (`GET /v2/news?category=instrument_keys&instrument_keys=...`) mapped directly to NSE instrument keys.
- Hugging Face FinBERT model (`yiyanghkust/finbert-pretrain` / `ProsusAI/finbert`) scores mapped headlines in $[-1.0, +1.0]$.
- Caches headline scores in `storage/market/news.db`.
- Top 3 headlines per ticker (max 120 chars each) injected into prompt context.

### 2.5 Daily Macro Regime (`storage/market/macro.db`)
- Rule-based daily regime from India VIX: `LOW_VOL` (<14), `NORMAL` (14–18), `ELEVATED` (18–24), `PANIC` (>24).
- Nifty 50 and Nifty 500 trend labels, FII/DII daily net cash flows.
- Optional biweekly LLM macro narrative (200 words, owned by `src/agents/macro_context.py`).

---

# Part II — Personas, Broker & Learning

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│            NIFTY 500 DATA  →  FEATURE SNAPSHOTS  →  WATCHLIST FUNNEL (Stage 0–3)     │
└───────────────────────────────────────┬──────────────────────────────────────────────┘
                                        │ candidates (holdings + watchlist, max 10)
               ┌────────────────────────┴────────────────────────┐
               ▼                                                 ▼
┌───────────────────────────────────┐              ┌──────────────────────────────────┐
│   FIVE LLM PERSONAS (one runner)  │              │  baseline-simons-rules (sixth    │
│   1 call per agent per night      │              │  agent, same candidates as       │
│   pre-mortem chain of thought     │              │  LLM Simons, no LLM)             │
└───────────────────┬───────────────┘              └────────────────┬─────────────────┘
                    │ decisions (BUY / SELL / HOLD / ADJUST)        │
                    ▼                                               ▼
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                       PAPER BROKER (broker/engine.py)                                │
│  Hard rules: price logic · cash incl. reservations · no short selling                │
│  Soft rules: 2% risk / 5% drawdown / 25% sector → CAP_BREACH log only                │
│  Orders → pending_orders (reserved_amount per order) → fills → positions             │
│  Monitor every 10 min · Expiry 15:30 · Settlement + NAV 15:35                        │
└───────────────────────────────────────┬──────────────────────────────────────────────┘
                                        │ position closed
                                        ▼
┌──────────────────────────────────────────────────────────────────────────────────────┐
│  FORENSICS (at close) → FORWARD RETURNS (nightly) → REFLECTION (weekly, watermark)   │
│  Heuristics as JSON rules → heuristic_applications → lifecycle                       │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

## 3. Personas & the Nightly Cognitive Loop

### 3.1 Personas as Configuration (`src/agents/personas/`)
A persona is a `PersonaConfig` dataclass [`src/agents/personas/base.py`]. A single runner [`src/agents/runner.py`] dispatches all five personas and the rules baseline. Prompts are co-located directly inside each persona configuration module, while shared output contracts live in [`src/agents/prompt_base.py`].

```python
@dataclass(frozen=True)
class PersonaConfig:
    id: str
    name: str
    system_prompt_builder: Callable[..., str]
    technical_hurdles: Dict[str, Any]      # Stage-1 boolean hurdles over FeatureSnapshot
    fundamental_hurdles: Dict[str, Any]    # Empty for Simons
    sort_key: str                          # Stage-2 intensity formula name (src/watchlist/rankers.py)
    ttl_days: int                          # Stage-3 watchlist lock
    lookback_days: int                     # Reflection window
    eval_horizon_days: int                 # Horizon used to score heuristics (T+5, T+10, T+20)
    fundamentals_depth: str                # none | 8q | 3y | 4y | 12q | 20q
```

### Detailed Persona Specifications

| Persona | Archetype | Stage-1 Hurdles | Stage-2 Intensity Sort Key | Sizing & Execution Discipline | Holding Horizon | TTL | Lookback | Eval Horizon |
|---|---|---|---|---|---|---|---|---|
| **Jim Simons** (`simons`) | Quant Momentum & Statistical Edge | `ema_20_above_50 = True`<br>`adx_14 >= 22.0`<br>`kaufman_er_20 >= 0.30`<br>`rsi_14` in [52, 72]<br>`volume_surge >= 1.2` | `volume_surge_x_macd_slope`<br>($\text{volume\_surge} \times \text{macd\_slope}$) | **Volatility Parity:** Stop $\ge 1.5\times \text{ATR}$, Target Band $2.5\text{--}3.5\times \text{ATR}$ (1:1.7–2.3 RRR). Risk budget $0.50\%\text{--}1.25\%$, max $10\%$ position cap, sector cap 3. **Decay Exits:** SELL if held $\ge 8$ days without $1.0\times\text{ATR}$ gain, or $\text{KER}<0.20$, or $\text{ADX}<20$. Baseline counterpart has score $\ge 0.55$ conviction floor and 5% uncommitted cash reserve. | 1–14 d | 3 d | 14 d | 5 d |
| **Peter Lynch** (`lynch`) | GARP (Growth At a Reasonable Price) | `debt_to_equity <= 0.8`<br>`cfo_to_pat >= 0.8`<br>`peg <= 1.2`<br>`roce_pct >= 15.0` | `roce_peg_ratio`<br>($\frac{\text{roce\_pct}}{\max(\text{peg}, 0.1)}$) | **Earnings Compounders:** Low debt, high operating cash flow conversion. 1.5% risk rule per trade, 20% cap. Ingests 4 trailing annual audited periods from Upstox (`fundamentals_depth = "4y"`). Multi-quarter evaluation horizon. | 30–90 d | 14 d | 120 d | 60 d |
| **Howard Marks** (`marks`) | Contrarian Value & Margin of Safety | `debt_to_equity <= 1.0`<br>`roce_pct >= 12.0`<br>`dist_52w_high_pct <= -15.0`<br>`rsi_14 <= 45.0` | `marks_contrarian_composite`<br>(Percentile rank composite: oversold depth + valuation discount + ROCE) | **2nd-Level Thinking:** Buys quality businesses beaten down by bad news or market overreaction. Demands structural margin of safety (low leverage, stable promoters). Cuts only on thesis breach. | 21–120 d | 10 d | 90 d | 60 d |
| **Rakesh Jhunjhunwala** (`jhunjhunwala`) | High-Conviction Growth & India Compounders | `ema_20_above_50 = True`<br>`roce_pct >= 18.0`<br>`pat_growth_yoy_pct >= 15.0`<br>`promoter_holding_pct >= 45.0` | `jhunjhunwala_composite`<br>($\text{volume\_surge} \times \text{pat\_growth}$) | **High-Conviction Sizing & Pyramiding:** Pyramiding / averaging up permitted into winners (pos=held) up to $20\%$ cap. Forensics detects institutional outflow via `INSTITUTIONAL_SPONSORSHIP_BREACH`. Multi-month compounding horizon. | 90–180 d | 14 d | 150 d | 90 d |
| **StockMinds Core** (`varsity`) | Zerodha Varsity Balanced & DCF Intrinsic Value | `ema_20_above_50 = True`<br>`rsi_14` in [50, 70]<br>`debt_to_equity <= 1.5`<br>`roce_pct >= 12.0` | `varsity_composite`<br>(Percentile rank composite: 50% Technical [Vol+RSI] + 50% Fundamental [ROCE, 1/DE, DCF Discount]) | **Textbook Mechanical Sizing & Diversification:** Zerodha Varsity Module 1 & 9 principles. 1:1.5 RRR floor primary-sourced from Varsity Module 1 & 9. 10 diversified positions book with 10% position cap and 0.5%–1.5% trade risk (target 1.0%). Closed-form DCF intrinsic value. | 20–75 d | 14 d | 90 d | 20 d |

### 3.2 Candidate Selection, Batching & Token Budget
- **Review Pool:** The agent's open positions **plus** its watchlist. Open positions are always included, even if they have fallen out of the top watchlist. Capped at `MAX_CANDIDATES_PER_RUN` (10 candidates) by dropping lowest-intensity watchlist names first. `MAX_OPEN_POSITIONS_PER_AGENT` is 5.
- **Single Nightly Batch Call:** One structured output completion per agent per night, separated by `AGENT_RUN_DELAY_SEC` (60s) to adhere to provider RPM limits.
- **Compact Numeric Candidate Rows:** Each candidate is rendered as a dense pipe-delimited line (~100 tokens), generated deterministically from `FeatureSnapshot`:
  ```text
  APLAPOLLO|CAP|close=2195.00|ema_20=2138.14|ema_50=2116.18|ema_200=1989.04|rsi_14=55.4|macd_hist=+6.62|volume_surge=1.78|adx_14=22.0|atr_14=66.89|dist_52w_high_pct=-3.8|dist_52w_low_pct=29.2|ema_20_above_50=true|debt_to_equity=0.67|roce_pct=28.28|roe_pct=22.71|pos=none
  ```

#### Token Budget & Trimming Cascade (`src/agents/context_assembler.py`)
Target prompt size: **~2,800 tokens** (`PROMPT_TOKEN_TARGET`), with a hard ceiling of **3,800 tokens** (`PROMPT_TOKEN_CEILING`). If a prompt exceeds the ceiling, `ContextAssembler` deterministically sheds tokens in this strict priority:
1. **Trim Episodic Memory:** Drop the oldest closed trade history entries (down to 0 if necessary).
2. **Trim News Headlines:** Drop financial news headline blocks for all candidate tickers.
3. **Trim Watchlist Candidates:** Drop the lowest-intensity candidate rows one by one. **Open positions are protected and NEVER dropped.**

#### LLM Provider Architecture (`src/llm/client.py`)
- **Daily Decisions:**
  - **Primary:** Google Gemini 3.5 Flash Lite (`gemini-3.5-flash-lite`) via `google-genai` SDK using `response_json_schema` (raw JSON Schema structured outputs). Dynamic thinking budget disabled (`thinking_budget = 0`) for predictable latencies.
  - **Fallback:** Llama 3.3 70B Versatile (`llama-3.3-70b-versatile`) on Groq with automatic HTTP 429/5xx exponential backoff and JSON schema repair retry.
- **Weekly Reflection & Forensics:**
  - **Primary:** Google Gemini 3.8 Flash (`gemini-3.8-flash`).
  - **Fallback:** OpenAI GPT-OSS 120B on Groq (`openai/gpt-oss-120b`) with step-down reasoning effort (`high` → `medium` → `low`).

### 3.3 Decision Schema & Faithfulness
Each agent returns a structured batch matching `DecisionBatch` in [`src/core/schemas.py`]:
```json
{
  "decisions": [
    {
      "ticker": "TATAMOTORS",
      "action": "BUY",
      "shares": 25,
      "entry_low": 940.0,
      "entry_high": 955.0,
      "stop_loss_price": 910.0,
      "target_price": 1020.0,
      "pre_mortem_risk": "Commercial-vehicle margin squeeze if domestic steel prices rise >4%.",
      "reasoning": "Breakout above 940 with 1.8x volume surge and 20/50 EMA crossover.",
      "cited_metrics": { "rsi_14": 62.4, "volume_surge": 1.82, "roce_pct": 18.5, "debt_to_equity": 0.65 }
    }
  ]
}
```
- **Faithfulness Verification (`src/evaluation/faithfulness.py`):**
  - Evaluated deterministically for every decision.
  - Requires citing $\ge 3$ metrics strictly from the allowed feature contract list.
  - Each cited metric is verified against the recorded `FeatureSnapshot` for that ticker and date using the feature's match tolerance.
  - $\text{Faithfulness Score} = \frac{\text{Matched Citations}}{\text{Total Citations}}$. Stored in `decisions.faithfulness_score`.
  - `faithfulness_score = matched / cited`, stored in `decisions`.

## 4. Paper Broker & Execution Engine

### 4.1 Money, Charges & Slippage
All amounts are integer paise. Charges are exact for Indian delivery equity (rates in `settings.py`):

| Charge | Rate | Applies to |
|---|---|---|
| Brokerage | ₹0 (**verify on Day 1**) | — |
| STT | 0.1% of trade value | BUY and SELL |
| Exchange turnover (NSE) | 0.00297% | BUY and SELL |
| SEBI turnover fee | 0.0001% | BUY and SELL |
| Stamp duty | 0.015% | BUY only |
| GST | 18% of (brokerage + exchange + SEBI fee) | BUY and SELL |
| DP charges | ₹15.34 flat | SELL only |

**Slippage** **[Default — confirm]:** `SLIPPAGE_BPS = 10` (0.10%). BUY fills at `price × (1 + 10 bps)` and SELL fills at `price × (1 − 10 bps)`. Decide this **before the first live night** and do not change it later, so results stay comparable.

```python
# broker/transaction_charges.py
def compute_transaction_charges_paise(price_paise: int, shares: int, side: str) -> int:
    tv = price_paise * shares                      # trade value in paise
    if tv <= 0:
        return 0
    stt      = 0.001 * tv
    exch     = 0.0000297 * tv
    sebi     = 0.000001 * tv
    brokerage = 0.0                                # verify on Day 1
    gst      = 0.18 * (brokerage + exch + sebi)
    stamp    = 0.00015 * tv if side == "BUY" else 0.0
    dp       = 1534 if side == "SELL" else 0       # ₹15.34 in paise
    return int(round(stt + exch + sebi + gst + stamp + dp))
```
Each charge is computed once per fill and rounded to whole paise. Nothing accumulates by repeated float addition.

### 4.2 Validation Rules
**Hard rules (blocking).** A failing order is rejected with `rejection_reason`, and nothing is silently corrected:
1. **Price logic** (BUY): `0 < stop_loss < entry_low ≤ entry_high < target`. `shares` is an integer ≥ 1.
2. **Cash:** `cash − SUM(reserved_amount of pending BUYs) ≥ reserve_amount` for the new order (see §4.3).
3. **No short selling:** a SELL with no OPEN position is rejected as `NO_OPEN_POSITION`.
4. **ADJUST validity:** the position must be OPEN, and `stop < last close < target`.

**Soft rules (non-blocking).** The persona prompt contains 2% risk per trade, 5% max drawdown and 25% sector concentration. If an order breaks them, the broker still accepts it and logs a `CAP_BREACH` event with the measured values. This is a deliberate research choice: it lets us measure which LLM personas follow their own instructions. The report states this clearly.

### 4.3 Order Lifecycle
1. **Placement (22:00).** Each BUY or SELL decision creates a `pending_orders` row with `status='pending'` and `valid_for_date = next trading day` (from `market_calendar`). There is at most one pending order per agent and ticker (partial unique index).
2. **Cash reservation.** A pending BUY stores `reserved_amount_paise` computed at the **worst-case fill**: `shares × entry_high × (1 + BUY_OVERSHOOT_PCT) × (1 + slippage)` plus BUY charges. `reserved_cash` is **derived** as the SUM of these amounts for the agent's pending BUYs. There is no stored counter, and nothing to drift. A SELL reserves no cash.
3. **BUY fill rule** **[Default — confirm]**: at each poll, a pending BUY fills if `entry_low ≤ price ≤ entry_high × (1 + BUY_OVERSHOOT_PCT)`. `BUY_OVERSHOOT_PCT` defaults to 0.5%. If `price ≤ stop_loss`, the order is cancelled as `CRASH_CANCELLED`. If the price is below `entry_low` but above the stop, the order waits for the next poll.
4. **SELL fill rule** **[Default — confirm]:** a pending SELL fills at the **first poll** of the valid day at the prevailing price. If the stop-loss triggers before that, the stop executes and the SELL is cancelled.
5. **Stop-loss.** Any poll where `price ≤ stop_loss` closes the whole position at the prevailing price (a gap-down realises the actual lower price, and the gap is recorded in the activity log). Frozen positions (`frozen_reason` set) and locked-circuit tickers are skipped.
6. **Target.** Reaching the target is a **soft signal**. The monitor logs `TARGET_REACHED` once per position per day. The position stays open and the agent decides at 22:00.
7. **ADJUST.** Changes the stop and/or target of an open position immediately (the market is closed at 22:00). **[Default — confirm]:** a stop may be **raised but never lowered**. Both new values must pass rule 4 of §4.2. No order is created.
8. **Averaging.** A BUY on an already-held ticker is allowed. When it fills, shares are added, the average entry price is recalculated, stop and target take the new order's values, and the **single OPEN position row** is updated. `entry_date` stays at the first entry. The database enforces one OPEN position per (agent, ticker).
9. **Overwrite.** A new decision for a ticker with a pending order only happens if the nightly run is repeated. The older pending order is cancelled and its reservation disappears with it.
10. **Expiry (15:30).** A separate job marks all unfilled pending orders `expired`. Their reservations vanish, since they are no longer pending.
11. **Idempotent fills.** Every fill uses an atomic `UPDATE pending_orders SET status='filled' WHERE id=? AND status='pending'`. If no row is updated, the fill is skipped. A monitor restart cannot double-fill.
12. **Linkage.** Each order points to its decision. Each fill points to its order and position. A position stores its entry decision's reasoning, its exit reason (`STOP_HIT`, `AGENT_SELL`, `CORP_ACTION_CLOSE`), and hold days.

### 4.4 Monitor, Expiry & Settlement
- **Monitor (`broker/monitor.py`).** Stateless. Each run is one poll: fetch batched quotes through `QuoteProvider` for every pending-order and open-position ticker, apply §4.3 rules, log events. The scheduler runs it every `MONITOR_INTERVAL_MIN` (10) minutes between 09:20 and 15:20. It skips non-trading days using `market_calendar`.
- **Expiry (`broker/expiry.py`)** at 15:30, as described above.
- **Settlement (`broker/settlement.py`)** at 15:35: update `positions.last_price`, compute each agent's cash, invested value and total value, and write one `daily_nav` row per agent with the Nifty 500 close. The row stores the Nifty 500 close for that date, so alpha is a simple lookup.

## 5. Memory, Forensics & Learning (`src/learning/`)

### 5.1 Episodic Memory
The prompt includes the last `EPISODIC_MEMORY_LIMIT` (10) closed positions: ticker, entry reasoning excerpt, exit reason, hold days and PnL %.

### 5.2 Forensics (`src/learning/forensics.py`)
Runs **synchronously at the moment a position closes** inside [`src/broker/engine.py`], so the diagnosis exists before any reflection. It is deterministic, rule-based Python. A trade can fit more than one class, so the first match in this priority order wins:

- **Loss classes:**
  1. `CORP_ACTION_ARTIFACT` — Position closed due to corporate action adjustments.
  2. `BROAD_MARKET_DRAG` — VIX was elevated/panic for $\ge 50\%$ of holding days, or benchmark fell $>2\%$.
  3. `REGIME_MISMATCH` — India VIX $>20$ at exit AND VIX rose from entry to exit.
  4. `EARNINGS_SHOCK` — Single-day absolute move $\ge 7\%$ in ticker candles during holding window with company news.
  5. `FALSE_BREAKOUT` — Price back below entry within first 3 sessions without volume confirmation ($<1.2\times$ 20d avg).
  6. `UNCLASSIFIED` — Default loss fallback.
- **Win classes** (realized PnL $\ge 4\%$ and held $\ge 3$ days):
  1. `EARNINGS_MOMENTUM` — Single-day move $\ge 5\%$ during window.
  2. `MEAN_REVERSION` — Entry RSI $<40$ from snapshot.
  3. `TREND_CONTINUATION` — Default win class.
  4. `UNCLASSIFIED_WIN` — Win that matched no specific pattern.

The result is saved in `positions.forensics_type`, `positions.regime_at_exit`, and `positions.diagnosis_json`.

### 5.3 Forward Returns (`src/evaluation/forward_returns.py`)
Each night after settlement, for every row in `decisions` (LLM and baseline, including HOLD and skipped candidates), compute the stock's return and the universe/benchmark return over `FORWARD_HORIZONS` (default: 1, 5, 10, 20, 60, 120 trading days) once enough market days have passed. Results populate `forward_returns`. This gives hundreds of data points for the paired LLM-vs-baseline comparison and the only objective way to score `AVOID` heuristics.

### 5.4 Weekly Reflection (`src/learning/engine.py`)
Runs on Sunday at 10:00 IST:
1. **Eligible trades:** Positions closed **after** the agent's last reflection watermark (`reflection_runs.last_position_id_reviewed`) and within its lookback window. Trades are never reviewed twice.
2. **Sample gate:** At least `MIN_CLOSED_TRADES_FOR_REFLECTION` (3) eligible trades. If fewer, skip and **do not advance the watermark**.
3. **Heuristic generation:** The LLM reads the forensics reports and generates structured heuristics:
   `{kind: SEEK|AVOID, trigger: <JSON predicate>, prescribed_action, rationale}`.
   The trigger uses only allowed `FeatureSnapshot` metric names, for example:
   `{"all":[{"feature":"india_vix","op":">","value":22.0},{"feature":"volume_surge","op":">=","value":1.5}]}`.
   A heuristic with an unverifiable or invalid trigger is discarded.
4. **Watermark:** On success, record the run in `reflection_runs`.

### 5.5 Heuristic Lifecycle & Trigger Evaluation (`src/learning/memory_manager.py`)
- **Nightly evaluation:** Python evaluates each `active` and `testing` heuristic's trigger against every candidate's `FeatureSnapshot`. If it fires, a row goes to `heuristic_applications` (linked to the decision) as `PENDING`.
- **Resolution:** When the persona's `eval_horizon_days` has passed, the application is resolved against the candidate's forward return:
  - `SEEK` succeeds if forward return $>0$.
  - `AVOID` succeeds if forward return $\le 0$.
- **Lifecycle state transitions:**
  - `testing` → `active`: $\ge 3$ resolved applications and success rate $\ge 60\%$.
  - `active` → `reinforced`: $\ge 10$ resolved applications and success rate $\ge 60\%$.
  - `active`/`testing` → `deprecated`: $\ge 3$ resolved applications and success rate $<40\%$, or has not fired in 30 days.
- Up to 5 active and reinforced heuristics are injected into nightly prompt context.

## 6. Watchlist Curation Funnel (`src/watchlist/`)

```text
NIFTY 500 → Stage 0 liquidity gate → Stage 1 persona hurdles → Stage 2 intensity sort → Stage 3 sector cap + TTL
```
- **Stage 0 (all personas):** `ADV20 × price ≥ ₹5 crore`, circuit-lock blacklist, stock not `STALE_DATA`. The extra volume momentum rule (`SMA5(vol) > SMA20(vol)`) applies **only to Simons and RJ**.
- **Stage 1 (persona hurdles):** Boolean technical and fundamental hurdles from each `PersonaConfig`. A stock must pass both sets (Simons has no fundamental hurdles). Sector percentile ranks rather than filters.
- **Stage 2 (intensity sort — `src/watchlist/rankers.py`):** Persona-specific sort key.
  - Simons: $\text{volume\_surge} \times \text{macd\_slope}$.
  - Lynch: $\frac{\text{roce\_pct}}{\max(\text{peg}, 0.1)}$.
  - Marks: Percentile rank composite (oversold depth + valuation discount + ROCE).
  - RJ: $\text{volume\_surge} \times \text{pat\_growth}$.
  - Core: Percentile rank composite (50% Technical [Vol+RSI] + 50% Fundamental [ROCE, 1/DE, DCF Discount]).
- **Stage 3 (sector cap & TTL lock):** At most 2 stocks per sector, target size of 8–10, and a fixed TTL lock to stop daily churn. A stock leaves early only if it is structurally invalid (e.g. closes below the 200 EMA). Persisted in `agent_watchlist`.
- **Audit:** Each night the funnel logs how many stocks pass each stage per persona to `activity_log`.

### 6.1 The Independent Rules Baseline (`src/baselines/simons_rules.py`)
- A sixth agent, `baseline-simons-rules` (`agents.kind = 'BASELINE'`), with the same ₹1,00,000 starting cash, trading through the exact same broker engine, charges, slippage, and fill rules.
- **Independence:** Lives in `src/baselines/` as a sibling package with zero coupling to `src/agents/` or LLM machinery.
- **Input:** Evaluates the exact candidate list seen by LLM Simons each night.
- **Entry (BUY):** If all hold: `ema_20_above_50`, `rsi_14` in [55, 70], `volume_surge >= 1.2`, `macd_hist > 0`. Entry range: $\text{close} \pm 0.25 \times \text{ATR}$. Stop: $\text{close} - 2 \times \text{ATR}$. Target: $\text{close} + 3 \times \text{ATR}$.
- **Exit (SELL):** At next-night run if $\text{close} < \text{ema\_20}$, or target was reached. The stop is automatic via the broker.
- **Sizing:** 10% of account capital per position, up to 5 positions.
- Decisions recorded with `source='BASELINE'` from the first live night.

---

# Part III — Database, Configuration & Repository Tree

## 7. Database Schema (`db/schema.sql`, migration 0001)

**Rules for every table.**
- Money columns end in `_paise` and are integers.
- Dates are IST `YYYY-MM-DD` text. Timestamps are IST ISO-8601 text supplied by the `Clock`. No `CURRENT_TIMESTAMP` defaults.
- `reserved_cash` is **not** stored. It is `SUM(reserved_amount_paise)` over an agent's pending BUY orders.
- Changes to a live database go through numbered files in `db/migrations/` (`0001_baseline.sql`, `0002_...sql`) and the `schema_version` table. Nobody edits the live database by hand.

```sql
-- schema_version
CREATE TABLE IF NOT EXISTS schema_version (
    version      INTEGER PRIMARY KEY,
    applied_at   TEXT NOT NULL
);

-- Symbol master: the ONLY ticker -> sector map
CREATE TABLE IF NOT EXISTS symbols (
    ticker          TEXT PRIMARY KEY,
    instrument_key  TEXT NOT NULL,
    isin            TEXT NOT NULL,
    company_name    TEXT NOT NULL,
    sector          TEXT NOT NULL,
    sector_index    TEXT,
    is_active       INTEGER NOT NULL DEFAULT 1
);

-- Exchange calendar: source of "next trading day"
CREATE TABLE IF NOT EXISTS market_calendar (
    trade_date      TEXT PRIMARY KEY,
    is_trading_day  INTEGER NOT NULL,
    session_type    TEXT NOT NULL DEFAULT 'NORMAL',   -- NORMAL | MUHURAT | CLOSED
    note            TEXT
);

-- Job ordering and status
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    job           TEXT NOT NULL,                       -- ingestion | features | watchlist | agents | ...
    run_date      TEXT NOT NULL,
    status        TEXT NOT NULL,                       -- RUNNING | SUCCESS | FAILED | SKIPPED_HOLIDAY
    started_at    TEXT NOT NULL,
    finished_at   TEXT,
    detail        TEXT,
    UNIQUE (job, run_date)
);

-- Agents (5 LLM personas + 1 baseline)
CREATE TABLE IF NOT EXISTS agents (
    id                    TEXT PRIMARY KEY,
    name                  TEXT NOT NULL,
    philosophy            TEXT NOT NULL,
    kind                  TEXT NOT NULL DEFAULT 'LLM',  -- LLM | BASELINE
    starting_cash_paise   INTEGER NOT NULL DEFAULT 10000000,
    cash_paise            INTEGER NOT NULL DEFAULT 10000000,
    started_on            TEXT,
    is_active             INTEGER NOT NULL DEFAULT 1,
    created_at            TEXT NOT NULL,
    updated_at            TEXT NOT NULL
);

-- One versioned feature snapshot per ticker per date
CREATE TABLE IF NOT EXISTS feature_snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker          TEXT NOT NULL,
    as_of_date      TEXT NOT NULL,
    schema_version  INTEGER NOT NULL,
    features_json   TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    UNIQUE (ticker, as_of_date, schema_version)
);

-- Persisted watchlists (TTL lock needs memory)
CREATE TABLE IF NOT EXISTS agent_watchlist (
    agent_id         TEXT NOT NULL,
    ticker           TEXT NOT NULL,
    sector           TEXT NOT NULL,
    added_on         TEXT NOT NULL,
    ttl_days         INTEGER NOT NULL,
    expires_on       TEXT NOT NULL,
    intensity_score  REAL NOT NULL,
    PRIMARY KEY (agent_id, ticker),
    FOREIGN KEY (agent_id) REFERENCES agents(id)
);

-- One row per LLM call (one call covers many tickers)
CREATE TABLE IF NOT EXISTS llm_calls (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id      TEXT NOT NULL,
    run_date      TEXT NOT NULL,
    model         TEXT NOT NULL,
    prompt        TEXT NOT NULL,
    response      TEXT NOT NULL,
    tokens_in     INTEGER NOT NULL,
    tokens_out    INTEGER NOT NULL,
    latency_ms    INTEGER NOT NULL,
    parse_status  TEXT NOT NULL,                       -- SUCCESS | RETRY_SUCCESS | FAILED
    created_at    TEXT NOT NULL
);

-- Every decision for every candidate, from LLMs AND the baseline
CREATE TABLE IF NOT EXISTS decisions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    run_date            TEXT NOT NULL,
    agent_id            TEXT NOT NULL,
    ticker              TEXT NOT NULL,
    source              TEXT NOT NULL,                 -- LLM | BASELINE
    action              TEXT NOT NULL,                 -- BUY | SELL | HOLD | ADJUST
    shares              INTEGER,
    entry_low_paise     INTEGER,
    entry_high_paise    INTEGER,
    stop_paise          INTEGER,
    target_paise        INTEGER,
    reasoning           TEXT,
    pre_mortem_risk     TEXT,
    cited_metrics_json  TEXT,
    faithfulness_score  REAL,
    snapshot_id         INTEGER,
    llm_call_id         INTEGER,
    created_at          TEXT NOT NULL,
    UNIQUE (agent_id, ticker, run_date),
    FOREIGN KEY (agent_id) REFERENCES agents(id),
    FOREIGN KEY (snapshot_id) REFERENCES feature_snapshots(id),
    FOREIGN KEY (llm_call_id) REFERENCES llm_calls(id)
);

-- Forward returns for every decision (also scores AVOID heuristics)
CREATE TABLE IF NOT EXISTS forward_returns (
    decision_id    INTEGER NOT NULL,
    horizon_days   INTEGER NOT NULL,
    ret_pct        REAL NOT NULL,
    nifty_ret_pct  REAL NOT NULL,
    computed_on    TEXT NOT NULL,
    PRIMARY KEY (decision_id, horizon_days),
    FOREIGN KEY (decision_id) REFERENCES decisions(id)
);

-- Pending orders (market-hours matching queue)
CREATE TABLE IF NOT EXISTS pending_orders (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id                TEXT NOT NULL,
    ticker                  TEXT NOT NULL,
    side                    TEXT NOT NULL,             -- BUY | SELL
    shares                  INTEGER NOT NULL,
    entry_low_paise         INTEGER,                   -- NULL for SELL
    entry_high_paise        INTEGER,
    stop_paise              INTEGER,
    target_paise            INTEGER,
    reserved_amount_paise   INTEGER NOT NULL DEFAULT 0, -- worst-case outlay; 0 for SELL
    decision_id             INTEGER,
    status                  TEXT NOT NULL DEFAULT 'pending',
        -- pending | filled | expired | cancelled | crash_cancelled | rejected
    rejection_reason        TEXT,                      -- e.g. NO_OPEN_POSITION, INSUFFICIENT_CASH
    valid_for_date          TEXT NOT NULL,
    created_at              TEXT NOT NULL,
    updated_at              TEXT NOT NULL,
    FOREIGN KEY (agent_id) REFERENCES agents(id),
    FOREIGN KEY (decision_id) REFERENCES decisions(id)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_pending_one_per_ticker
    ON pending_orders(agent_id, ticker) WHERE status = 'pending';

-- Positions (one row per open/closed round trip)
CREATE TABLE IF NOT EXISTS positions (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id               TEXT NOT NULL,
    ticker                 TEXT NOT NULL,
    sector                 TEXT NOT NULL,
    shares                 INTEGER NOT NULL,
    avg_entry_price_paise  INTEGER NOT NULL,
    stop_paise             INTEGER NOT NULL,
    target_paise           INTEGER NOT NULL,
    last_price_paise       INTEGER NOT NULL,
    status                 TEXT NOT NULL DEFAULT 'OPEN',  -- OPEN | CLOSED
    frozen_reason          TEXT,                          -- e.g. CORP_ACTION; NULL = active
    entry_date             TEXT NOT NULL,
    entry_decision_id      INTEGER,
    entry_reasoning        TEXT,
    exit_date              TEXT,
    exit_price_paise       INTEGER,
    exit_reason            TEXT,                          -- STOP_HIT | AGENT_SELL | CORP_ACTION_CLOSE
    hold_days              INTEGER,
    realized_pnl_paise     INTEGER,
    realized_pnl_pct       REAL,
    forensics_type         TEXT,
    regime_at_exit         TEXT,
    diagnosis_json         TEXT,
    FOREIGN KEY (agent_id) REFERENCES agents(id),
    FOREIGN KEY (entry_decision_id) REFERENCES decisions(id)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_one_open_position
    ON positions(agent_id, ticker) WHERE status = 'OPEN';

-- Fills ledger (append-only)
CREATE TABLE IF NOT EXISTS fills (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id           INTEGER,                         -- NULL for stop-loss exits
    position_id        INTEGER NOT NULL,
    agent_id           TEXT NOT NULL,
    ticker             TEXT NOT NULL,
    side               TEXT NOT NULL,
    shares             INTEGER NOT NULL,
    price_paise        INTEGER NOT NULL,                -- includes slippage
    charges_paise      INTEGER NOT NULL,
    executed_at        TEXT NOT NULL,
    FOREIGN KEY (agent_id) REFERENCES agents(id),
    FOREIGN KEY (order_id) REFERENCES pending_orders(id),
    FOREIGN KEY (position_id) REFERENCES positions(id)
);

-- Daily NAV per agent (equity curves, Sharpe, drawdown, alpha)
CREATE TABLE IF NOT EXISTS daily_nav (
    agent_id         TEXT NOT NULL,
    nav_date         TEXT NOT NULL,
    cash_paise       INTEGER NOT NULL,
    invested_paise   INTEGER NOT NULL,
    total_paise      INTEGER NOT NULL,
    nifty500_close   REAL NOT NULL,
    PRIMARY KEY (agent_id, nav_date),
    FOREIGN KEY (agent_id) REFERENCES agents(id)
);

-- Heuristics: machine-checkable triggers
CREATE TABLE IF NOT EXISTS agent_memory (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id            TEXT NOT NULL,
    kind                TEXT NOT NULL,                  -- SEEK | AVOID
    heuristic_text      TEXT NOT NULL,
    trigger_json        TEXT NOT NULL,                  -- predicate over FeatureSnapshot names
    prescribed_action   TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'testing',-- testing | active | reinforced | deprecated
    confidence          REAL NOT NULL DEFAULT 0.5,
    times_triggered     INTEGER NOT NULL DEFAULT 0,
    times_successful    INTEGER NOT NULL DEFAULT 0,
    last_fired_on       TEXT,
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL,
    FOREIGN KEY (agent_id) REFERENCES agents(id)
);

-- Each time a heuristic fires, and how it turned out
CREATE TABLE IF NOT EXISTS heuristic_applications (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    heuristic_id    INTEGER NOT NULL,
    decision_id     INTEGER NOT NULL,
    fired_on        TEXT NOT NULL,
    horizon_days    INTEGER NOT NULL,
    outcome         TEXT NOT NULL DEFAULT 'PENDING',    -- PENDING | SUCCESS | FAILURE
    resolved_on     TEXT,
    FOREIGN KEY (heuristic_id) REFERENCES agent_memory(id),
    FOREIGN KEY (decision_id) REFERENCES decisions(id)
);

-- Reflection watermark: never re-read the same trades
CREATE TABLE IF NOT EXISTS reflection_runs (
    id                        INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id                  TEXT NOT NULL,
    run_date                  TEXT NOT NULL,
    last_position_id_reviewed INTEGER NOT NULL,
    trades_reviewed           INTEGER NOT NULL,
    status                    TEXT NOT NULL,            -- DONE | SKIPPED_TOO_FEW_TRADES
    FOREIGN KEY (agent_id) REFERENCES agents(id)
);

-- Transparency feed
CREATE TABLE IF NOT EXISTS activity_log (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id       TEXT,
    event_type     TEXT NOT NULL,
        -- ORDER_SUBMITTED | BUY_FILLED | SELL_FILLED | STOP_HIT | TARGET_REACHED | CRASH_CANCELLED
        -- | ORDER_EXPIRED | VALIDATION_FAILED | CAP_BREACH | ADJUSTED | LOCKED_CIRCUIT
        -- | CORP_ACTION_FROZEN | WATCHLIST_REFRESH | FUNNEL_COUNTS | PIPELINE_FAILED
    ticker         TEXT,
    description    TEXT NOT NULL,
    metadata_json  TEXT,
    created_at     TEXT NOT NULL
);
```

### Market Cache Schemas (`storage/market/`)
- **`storage/market/ohlcv.db`**:
  `daily_candles(ticker TEXT, date TEXT, open REAL, high REAL, low REAL, close REAL, volume INTEGER, oi INTEGER, PRIMARY KEY (ticker, date))`
- **`storage/market/macro.db`**:
  `macro_daily(trade_date TEXT PRIMARY KEY, regime TEXT, india_vix REAL, fii_net_cr REAL, dii_net_cr REAL, nifty50_trend TEXT, nifty500_trend TEXT, advance_decline REAL, market_closed INTEGER)` and optional `macro_narrative(narrative_date TEXT PRIMARY KEY, content TEXT, created_at TEXT)`.
- **`storage/market/fundamental.db`**:
  - `key_ratios(isin TEXT, as_of_date TEXT, pe REAL, pb REAL, ev_to_ebitda REAL, roa_pct REAL, roe_pct REAL, roce_pct REAL, market_cap REAL, PRIMARY KEY (isin, as_of_date))`
  - `income_statements(isin TEXT, period_type TEXT, fiscal_date TEXT, revenue REAL, operating_profit REAL, net_profit REAL, change_pct REAL, pat REAL, eps REAL, PRIMARY KEY (isin, period_type, fiscal_date))`
  - `balance_sheets(isin TEXT, fiscal_date TEXT, total_assets REAL, current_liab REAL, non_current_liab REAL, equity_capital REAL, PRIMARY KEY (isin, fiscal_date))`
  - `cash_flows(isin TEXT, fiscal_date TEXT, operating_cf REAL, investing_cf REAL, financing_cf REAL, PRIMARY KEY (isin, fiscal_date))`
  - `shareholding(isin TEXT, quarter_date TEXT, category TEXT, percentage REAL, PRIMARY KEY (isin, quarter_date, category))`
  - `corporate_actions(isin TEXT, name TEXT, expiry_date TEXT, amount REAL, ratio TEXT, event_details_json TEXT, updated_at TEXT, PRIMARY KEY (isin, name, expiry_date))`
- **`storage/market/news.db`**:
  `news_articles(instrument_key TEXT, heading TEXT, summary TEXT, article_link TEXT, thumbnail TEXT, published_time TEXT, PRIMARY KEY (instrument_key, published_time))`

## Settings Specification (`settings.py`)
Single source of truth for all system constants. Highlights:
- **Capital and costs:** `INITIAL_CASH_PER_AGENT_PAISE = 10_000_000`, `SLIPPAGE_BPS = 10`, statutory rates (`STT_RATE`, `EXCHANGE_TURNOVER_RATE`, `SEBI_FEE_RATE`, `STAMP_DUTY_RATE`, `GST_RATE`, `DP_CHARGES_PAISE = 1534`, `BROKERAGE_PAISE = 0`).
- **Rate limits:** `RATE_LIMIT_PER_SEC = 45`, `RATE_LIMIT_PER_MIN = 450`, `RATE_LIMIT_PER_30MIN = 1800`.
- **Schedule (IST):** Ingestion 20:00, backup 21:45, agents 22:00, `MONITOR_START = 09:20`, `MONITOR_END = 15:20`, `MONITOR_INTERVAL_MIN = 10`, expiry 15:30, settlement 15:35, reflection Sunday 10:00.
- **Orders:** `BUY_OVERSHOOT_PCT = 0.5`, `STOP_MAY_ONLY_RISE = True`, `MAX_OPEN_POSITIONS_PER_AGENT = 5`.
- **Prompts & Models:** `MAX_CANDIDATES_PER_RUN = 10`, `AGENT_RUN_DELAY_SEC = 60`, `PROMPT_TOKEN_TARGET = 2800`, `PROMPT_TOKEN_CEILING = 3800`, `EPISODIC_MEMORY_LIMIT = 10`, `MIN_CITED_METRICS = 3`.
  - Daily decision primary: `gemini-3.5-flash-lite`, fallback: `llama-3.3-70b-versatile` (Groq).
  - Reflection primary: `gemini-3.8-flash`, fallback: `openai/gpt-oss-120b` (Groq).
- **Funnel & Watchlist:** `MIN_SECTOR_COHORT = 8`, `SECTOR_PERCENTILE_MIN = 0` (off), `SECTOR_CAP_PER_AGENT = 2`, `WATCHLIST_TARGET_SIZE_MIN = 8`, `WATCHLIST_TARGET_SIZE_MAX = 10`.
- **Learning:** `MIN_CLOSED_TRADES_FOR_REFLECTION = 3`, `FORWARD_HORIZONS = [1, 5, 10, 20, 60, 120]`, lifecycle thresholds.
- **Storage & Paths:** `PORTFOLIO_DB_PATH = "storage/ledger/portfolio.db"`, `MARKET_DB_DIR = "storage/market"`, `BACKUP_DIR = "backups"`.

## Repository Tree

```text
Autonomous_Stock_Trading/
├── pyproject.toml                 # Setuptools build system configuration (where = ["src"])
├── pytest.ini                     # Pytest runner configuration (pythonpath = ["src", "."])
├── settings.py                    # Single source of truth for all constants (auto-injects src/ to sys.path)
├── scheduler.py                   # APScheduler: orchestrates the nightly pipeline & intraday monitor
├── Dockerfile                     # Deployment image for always-on persistent server (TZ=Asia/Kolkata, PYTHONPATH)
├── docker-compose.yml
├── requirements.txt
├── README.md
├── .gitignore
│
├── src/                           # Pure Python application source code (src/ layout)
│   ├── core/                      # Kernel primitives (zero LLM, zero network I/O at runtime)
│   │   ├── __init__.py
│   │   ├── calendar.py            # NSE market session calendar & next trading day
│   │   ├── clock.py               # Time injection protocol (SystemClock, FakeClock)
│   │   ├── database.py            # SQLite WAL connection factory with 5000ms busy timeout
│   │   ├── interfaces.py          # Core abstractions (Clock, QuoteProvider, LLMClient)
│   │   ├── money.py               # Exact integer paise arithmetic & formatting
│   │   ├── rate_limiter.py        # Multi-tier sliding-window rate limiter (45/s, 450/m, 1800/30m)
│   │   └── schemas.py             # System-wide Pydantic data contracts (Decision, Order, etc.)
│   │
│   ├── ingestion/                 # Upstox market data synchronization
│   │   ├── __init__.py
│   │   ├── cli.py                 # Ingestion CLI coordinator
│   │   ├── upstox_client.py       # Authenticated Upstox API client
│   │   ├── sync_ohlcv.py          # Daily candle synchronization with V3 EOD intraday merge
│   │   ├── sync_fundamentals.py   # Financial statements, ratios, shareholding, corporate actions
│   │   ├── sync_news.py           # Upstox curated news & FinBERT headline scoring
│   │   └── sync_macro.py          # Daily regime, India VIX, and institutional FII/DII net flows
│   │
│   ├── features/                  # Feature engineering & signal generation
│   │   ├── __init__.py
│   │   ├── contracts.py           # Canonical FeatureDef registry, metric schemas, match tolerances
│   │   ├── indicators.py          # Vectorized technical indicators (Wilder's RSI/ADX/ATR, Kaufman ER, etc.)
│   │   ├── sentiment.py           # FinBERT model inference pipeline
│   │   └── builder.py             # Nightly FeatureSnapshot generator job with data freshness checks
│   │
│   ├── watchlist/                 # Candidate selection funnel & intensity rankers
│   │   ├── __init__.py
│   │   ├── rankers.py             # Cross-sectional percentile rankers and Stage-2 sort keys
│   │   └── watchlist_refresh.py   # 4-stage funnel (liquidity -> hurdles -> sort -> sector cap & TTL)
│   │
│   ├── llm/                       # LLM provider abstractions & retry logic
│   │   ├── __init__.py
│   │   └── client.py              # Gemini & Groq clients, exponential backoff, reasoning step-down
│   │
│   ├── agents/                    # Decision layer and cognitive prompt assembly
│   │   ├── __init__.py
│   │   ├── runner.py              # Unified per-candidate execution loop for all 5 LLM agents + baseline
│   │   ├── parsers.py             # JSON repair, output validation, HOLD-all fallbacks
│   │   ├── context_assembler.py   # Compact candidate rows, token budgeting & trimming cascade
│   │   ├── prompt_base.py         # Shared prompt contracts and formatting helpers
│   │   ├── macro_context.py       # Biweekly macro narrative generator
│   │   └── personas/              # 5 self-contained persona configs (prompts, hurdles, sort keys)
│   │       ├── base.py            # PersonaConfig dataclass
│   │       ├── simons.py          # Jim Simons (Quant Momentum)
│   │       ├── lynch.py           # Peter Lynch (GARP)
│   │       ├── marks.py           # Howard Marks (Contrarian Value)
│   │       ├── jhunjhunwala.py    # Rakesh Jhunjhunwala (Growth & Promoter Quality)
│   │       └── varsity.py         # StockMinds Core (Zerodha Varsity Balanced & DCF Intrinsic Value)
│   │
│   ├── baselines/                 # Independent rules control benchmark
│   │   ├── __init__.py
│   │   └── simons_rules.py        # Rules-only 6th agent (trades through same broker, zero LLM calls)
│   │
│   ├── broker/                    # Execution engine & position management
│   │   ├── __init__.py
│   │   ├── engine.py              # Order validation, reservation, fills, averaging, ADJUST
│   │   ├── quotes.py              # LiveQuoteProvider (Upstox) and ReplayQuoteProvider (historical)
│   │   ├── monitor.py             # 10-minute intraday polling engine (matching & stop-loss enforcement)
│   │   ├── expiry.py              # 15:30 IST order cancellation job
│   │   ├── settlement.py          # 15:35 IST daily NAV calculation & audit logging
│   │   └── transaction_charges.py # Exact statutory Indian delivery charges (STT, DP, GST, Stamp, Exchange)
│   │
│   ├── learning/                  # Closed-loop learning & memory adaptation
│   │   ├── __init__.py
│   │   ├── forensics.py           # Rule-based post-mortem trade diagnosis at position close
│   │   ├── engine.py              # Weekly reflection job (Sunday 10:00 IST) with watermark tracking
│   │   └── memory_manager.py      # Nightly heuristic trigger evaluation & lifecycle state management
│   │
│   ├── evaluation/                # Performance measurement & benchmarking
│   │   ├── __init__.py
│   │   ├── faithfulness.py        # Deterministic cited-metric verification against FeatureSnapshot
│   │   ├── forward_returns.py     # Multi-horizon return backfill (T+1, T+5, T+10, T+20, T+60, T+120)
│   │   ├── performance.py         # Sharpe ratio, maximum drawdown, alpha vs Nifty 500, win rate
│   │   └── comparison.py          # Paired comparison engine (LLM Simons vs Rules Simons vs Benchmark)
│   │
│   ├── notifications/             # System alerts & failure notices
│   │   ├── __init__.py
│   │   └── alerts.py              # Telegram / Webhook alert dispatchers
│   │
│   └── api/                       # REST API (FastAPI)
│       ├── __init__.py
│       ├── main.py                # FastAPI bootstrap and CORS configuration
│       └── routes/                # Endpoint routers (leaderboard, portfolio, activity, memory, health)
│
├── storage/                       # Persistent runtime database storage (git-ignored)
│   ├── market/                    # Rebuildable market caches (ohlcv.db, fundamental.db, news.db, macro.db)
│   └── ledger/                    # Irreplaceable application state (portfolio.db, simulation.db)
│
├── backups/                       # Local point-in-time SQLite backups (sibling to storage/ on same volume)
│   └── portfolio_YYYY-MM-DD.db
│
├── db/                            # DDL schemas & database migrations
│   ├── schema.sql                 # Baseline schema (migration 0001)
│   └── migrations/                # Numbered migrations (0001_baseline.sql, 0002_..., 0003_..., 0004_...)
│
├── scripts/                       # Operational, migration, and simulation CLI utilities
│   ├── init_db.py                 # Apply migrations, seed agents
│   ├── build_symbol_master.py     # Generate symbols table from Nifty 500 constituents
│   ├── backup.py                  # Nightly SQLite backup API runner
│   ├── backfill_history_2025.py   # Historical 400-day candle backfiller
│   ├── run_historical_simulation.py # Comprehensive end-to-end replay simulation runner
│   └── evaluate_forward_returns.py # Multi-day decision forward returns evaluator
│
├── tests/                         # Automated test suites (sibling to src/)
│   ├── conftest.py                # Shared test fixtures (FakeClock, FakeLLM, in-memory DBs)
│   ├── unit/                      # 286 isolated unit tests
│   └── integration/               # 21 comprehensive integration pipeline tests
│
├── docs/                          # Architecture documentation & API audit findings
│   ├── Plan_v3.md                 # Single source of truth engineering specification
│   ├── upstox_findings.md         # Upstox API audit results and verified schemas
│   ├── personas.md                # Quantitative persona prompt & hurdle specifications
│   ├── FEATURE_DOCUMENTATION.md   # Mathematical definitions of all 28 snapshot metrics
│   └── backtest_results.md        # Historical backtest and simulation performance logs
│
└── dashboard/                     # React web application (Vite + Tailwind CSS)
    ├── package.json
    ├── src/
    │   ├── App.jsx
    │   ├── pages/                 # Leaderboard, AgentDetail, BaselineCompare, ActivityFeed
    │   └── components/            # EquityCurve, PositionTable, MetricBadge
```

The old recommendation engine and LangGraph orchestrator are removed from the `v2-ATA` branch before building starts. Git history keeps them.

---

# Part IV — REST API & Frontend

Read-only endpoints power the dashboard:
- `GET /api/leaderboard` — NAV, return %, alpha vs Nifty 500, Sharpe, max drawdown, win rate, faithfulness rate, total trades, and a **small-sample notice** per agent.
- `GET /api/agents/{id}/positions` — open and closed positions, forensic tags, frozen flags.
- `GET /api/agents/{id}/orders` — pending and past orders with rejection reasons.
- `GET /api/agents/{id}/decisions` — decisions with cited metrics and faithfulness scores.
- `GET /api/agents/{id}/nav` — daily NAV series for equity curves.
- `GET /api/agents/{id}/memory` — heuristics (kind, trigger, status, confidence) and post-mortems.
- `GET /api/baseline/comparison` — LLM Simons vs rules Simons vs Nifty 500, plus forward-return comparison for all decisions.
- `GET /api/activity` — transparency feed (`ORDER_SUBMITTED`, fills, `CAP_BREACH`, `FUNNEL_COUNTS`, ...).
- `GET /api/health` — latest `pipeline_runs` status for each job.

Pages: Leaderboard, Agent Detail, Baseline Compare, Activity Feed. Every page carries the educational / paper-trading disclaimer.

---

# Part V — Roadmap & Definition of Done

**Principle:** start the live paper clock at the end of week 1. Every night without capture is lost data.

### Week 1 — Foundations and the Simons Vertical Slice (STATUS: COMPLETED)
- **Day 1 (spike and contracts):** Upstox API spike → `docs/upstox_findings.md`. Symbol master. `settings.py`, `db/schema.sql` + numbered migrations, `Clock`, `QuoteProvider`, `LLMClient` interfaces, `core/money.py`.
- **Days 2–3:** Multi-tier rate limiter, OHLCV ingestion, market calendar. Vectorized indicators (`src/features/indicators.py`), `FeatureSnapshot` contracts, Stage 0–3 candidate funnel for Simons. LLM provider integration (Gemini & Groq) with compact pipe-delimited prompt formats and token budgeting.
- **Days 3–4:** Broker engine (validation, cash reservation, statutory charges, slippage, idempotent fills, averaging, ADJUST), intraday monitor, order expiry, settlement, rule-based post-mortem forensics, independent rules baseline agent. Comprehensive unit test suites for charges, money, reservation, and order lifecycle.
- **Day 5:** APScheduler orchestration, deployment Dockerfile with persistent disk volumes, end-to-end historical simulation replay with `FakeLLM`.
- **End of week 1:** LLM Simons and rules Simons live slice ready. Snapshots, decisions, NAV and pipeline runs verified.

### Week 2 — Remaining Personas, Multi-Agent Funnel & Clean Architecture (STATUS: COMPLETED)
- Fundamentals ingestion (4-period statements, ratios, quarterly category shareholding, corporate actions ground truth).
- FinBERT news sentiment inference pipeline and macro regime tracking.
- All 5 quantitative persona configs implemented with calibrated hurdles and intensity sort keys:
  - Simons (Quant momentum, Kaufman ER, ADX, Skew, Volatility Parity sizing).
  - Lynch (GARP, PEG, CFO/PAT conversion, ROCE/PEG sort).
  - Marks (Contrarian Value, 2nd-level thinking, Margin of Safety, Percentile rank composite sort).
  - Jhunjhunwala (Structural growth, promoter quality, high conviction, pyramiding).
  - StockMinds Core (Zerodha Varsity Dual Confluence, DCF Intrinsic Valuation with clamp-bounded FCFF, Module 9 Kelly-criterion sizing).
- **Funnel audit:** 4-stage multi-agent watchlist curation funnel (`src/watchlist/`) audited and verified.
- **Clean Architecture & Packaging Refactor:**
  - Migrated codebase to standard `src/` layout (`pyproject.toml`, `pytest.ini`).
  - Decoupled storage into `storage/market/` and `storage/ledger/`, with local point-in-time `backups/` as an independent sibling.
  - Promoted `baselines/` to an independent sibling package (`src/baselines/`).
  - Co-located prompts within persona modules, removing dead re-export stubs.
  - Automated CI test workflow (`.github/workflows/ci.yml`). 307 of 307 tests passing.

### Week 3 — Learning Loop, Heuristics & Performance Evaluation
- Forward-return multi-horizon backfill (`src/evaluation/forward_returns.py`).
- Weekly reflection engine with watermark tracking (`src/learning/engine.py`).
- Machine-checkable heuristic trigger evaluator, forward-return scoring, and testing/active/reinforced/deprecated lifecycle management (`src/learning/memory_manager.py`).
- Performance evaluation module: Sharpe ratio, maximum drawdown, alpha vs Nifty 500, win rate (`src/evaluation/performance.py`).
- Paired comparison engine: LLM Simons vs Rules Simons vs Nifty 500, and forward-return deltas (`src/evaluation/comparison.py`).
- Review first 2 weeks of live/replay execution telemetry: parse failure rate, missed fills, faithfulness, token use.

### Week 4 — REST API & Dashboard (STATUS: UPCOMING)
- FastAPI read-only endpoints mounted in `src/api/` (`leaderboard.py`, `portfolio.py`, `activity.py`, `baseline.py`, `memory.py`, `health.py`).
- React dashboard (`dashboard/`) with Vite, Tailwind CSS, Recharts equity curves, and small-sample labels.
- Health monitor page and system telemetry.

### Weeks 5–6 — Soak, tuning and hardening
- All six agents live. Fix issues found in real runs. Settings changes are recorded with the date (so results can be split before and after).
- Test coverage for the broker, features and heuristic triggers. Corporate-action freeze tested with a fake split.

### Weeks 7–8 — Evidence, report and demo
- Final comparison tables, example post-mortems, a worked heuristic from rule to outcome.
- Report, demo rehearsal, and buffer.

### Definition of Done
1. All six agents complete each nightly run with no unhandled exceptions over at least 15 consecutive trading days.
2. At least 3 of 5 LLM personas have executed trades. At least one stop-loss exit has occurred (or been exercised in a replay test).
3. Every order has a decision, and every fill has an order and position. `reserved_cash` always equals the sum of pending BUYs. This is verified by a test and a nightly check.
4. Every decision has a stored `FeatureSnapshot`, and a faithfulness score where metrics were cited.
5. `daily_nav` is complete for every trading day since each agent started.
6. The comparison page shows LLM Simons vs rules Simons vs Nifty 500, and the forward-return comparison for all decisions.
7. At least one heuristic has a machine-checked trigger with resolved applications.
8. The report states the limitations in the Overview section.

---

# Part VI — Risks & Mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| Upstox fundamentals fields missing or different | High | Audited & verified: 4-period statements, ratios, category shareholding, and corporate actions are live. Unprovided fields (`interest_coverage`, `promoter_pledge_pct`) default to `None` gracefully. |
| Current-day daily candle missing at 20:00 IST | High | V3 Historical cold storage clears overnight (~23:30–02:00 IST). Mitigated by V3 Intraday `days/1` dual fetch protocol merging today's candle at 20:00 IST. |
| Missed nights of data | High | Deploy and go live at the end of week 1. `pipeline_runs`, health page and failure alerts. Snapshots and decisions saved every night. |
| Runner starts on partial data | High | `pipeline_runs` check before every job. Runner refuses to start unless ingestion, features and watchlist are SUCCESS. |
| Double fill after a monitor restart | High | Atomic `UPDATE ... WHERE status='pending'`. Monitor is stateless. |
| Reserved-cash drift | High | No stored counter. Reserved cash is the SUM of pending BUY reservations. Nightly consistency check. |
| Floating-point money errors | Medium | Integer paise everywhere. Charges rounded once per fill. |
| Date or timezone bugs | Medium | IST `Clock` injected everywhere. No database default timestamps. `market_calendar` for trading days. Tests with `FakeClock`. |
| Split or bonus on a held stock | Medium | Overlap re-fetch comparison cross-referenced against `GET /v2/fundamentals/{isin}/corporate-actions` ground truth. Freeze stops, alert, adjust by split ratio. |
| LLM invalid or hallucinated output | Medium | JSON validation and one repair retry. HOLD-all fallback. Hard broker rules. Faithfulness check. |
| LLM rate limits or cost | Medium | One call per agent per night, 60 s spacing, max 10 candidates, compact prompts, fallback model, every call logged. |
| Prompt exceeds token ceiling | Medium | Compact rows. Python truncation order. Measured budget in week 1. |
| Few fills (missed entries) | Medium | 0.5% overshoot, 10-minute polls, nightly funnel and fill counts. Review in week 2. |
| Too few closed trades for learning | Medium | Forward returns on all decisions. Heuristics scored on forward returns. Small-sample labels. Honest "mechanism, not proof" wording. |
| Watchlists empty or the same few stocks | Medium | Nightly funnel counts. Hurdles filter, sector percentile only ranks. Threshold review in week 2. |
| Baseline unfair or mismatched | Medium | Same candidates, same broker, same costs, same fill rule. Logged from the first live night. |
| SQLite write contention | Low | WAL, busy timeout, one process runs the scheduler. |
| Schema change damages history | Medium | Numbered migrations from the first commit. Nightly backup. No manual edits. |
| Regulatory misreading | High | Educational paper trading only. Disclaimer on every page. No real funds. |

---

# Part VII — Automated Test Suite Coverage & Known Testing Gaps

### Current Status (Week 2 Close)
- **Suite Volume:** 308 passed tests across 36 test modules (executed via `pytest tests/ -W error` in ~26 seconds).
- **Core Coverage Areas:**
  1. *Mathematical & Financial Contracts:* Wilder indicator formulas (ATR-14, RSI-14, ADX-14), Kaufman Efficiency, Parkinson Volatility, transaction charges (STT, SEBI, GST, stamp duty) validated down to integer paise.
  2. *Pipeline Funnel & Starvation:* Stage 0-3 candidate filtering across all 5 personas tested under both normal and bear market starvation conditions.
  3. *Order Lifecycle & Money Safety:* Pre-trade cash reservation, overshoot logic, intraday monitor fills, 15:30 expiry cancellations and cash refunds.
  4. *Decision Fidelity & Faithfulness:* Calibrator adjustments, counterfactual sizing capture, and metric hallucination detection against ground-truth snapshots.

### Known Gaps & Technical Debt to Address in Weeks 3–4
1. **Concurrency & SQLite WAL Writer Contention:** All tests execute single-threaded in `:memory:`. In production, the 10-minute intraday monitor (`job_intraday_monitor`) and dashboard API readers execute against `storage/ledger/portfolio.db`. Need a multi-threaded stress test verifying that `BEGIN IMMEDIATE` under concurrent load does not raise unhandled `sqlite3.OperationalError: database is locked`.
2. **Mid-Batch Network Timeout & Partial Ingestion Recovery:** Ingestion tests mock 100% clean API responses. Missing a simulated HTTP 504 / socket drop mid-batch (e.g. at ticker 250 of 500) to verify graceful rollback and restartability.
3. **Empty Stub File (`tests/unit/test_heuristic_triggers.py`):** Currently a 4-line docstring placeholder. Heuristic transition states (DISCOVERED -> ACTIVE -> REINFORCED / DEPRECATED) and trigger scoring must be implemented and tested in Week 3.
4. **Macro Market Breadth & Trend Ingestion [RESOLVED]:** `sync_macro.py` now computes advance/decline ratio across constituents in `ohlcv.db` and index trends from Upstox index candles/quotes (with breadth fallback). Tested via 9 unit tests in `tests/unit/test_sync_macro.py` and all historical rows backfilled.
5. **Multi-Day Order Rollover vs Expiry Integration:** Existing tests verify intraday expiry at 15:30. A multi-day simulation test is needed to verify agent behavior when an unfulfilled candidate expires and is re-evaluated on subsequent sessions.

---

# Appendix — Defaults to Confirm

These are values proposed in v3 so work can start. The team should confirm or change them in one meeting. **Money and cost settings should not change after the first live night.**

| # | Setting | v3 default | Why it matters |
|---|---|---|---|
| 1 | Monitor poll interval | 10 min (09:20–15:20) | Fewer missed fills. Cheap with batched quotes. |
| 2 | BUY overshoot above `entry_high` | 0.5% | Stops a small gap-up from killing the order. |
| 3 | Slippage | 10 bps each side | Makes paper results less optimistic. Decide once. |
| 4 | Pending SELL fill time | First poll of next trading day | Defines the SELL contract. |
| 5 | ADJUST rule | Stop may only be raised | Prevents widening a loss after the fact. |
| 6 | Risk caps | Non-blocking, logged as `CAP_BREACH` | Research choice: measure rule-following. |
| 7 | Heuristic evaluation horizons | Simons 5d, Marks/RJ/Core 10d, Lynch 20d | Needed to score SEEK and AVOID rules. |
| 8 | Baseline rules | EMA20>50, RSI 55–70, vol ≥1.2×, MACD hist>0, ATR stops, 10% sizing | Defines the comparison. |
| 9 | Prompt token target / ceiling | ~2,800 / 3,800 | Final numbers set after measuring real prompts. |
| 10 | RAG target | Hit rate @3 ≥ 90% | Realistic for 30 hand-made queries. |
| 11 | Sector percentile | Rank only, filter off | Avoids empty watchlists. |
| 12 | Brokerage | ₹0 delivery | Verify on Upstox pricing on Day 1. |
