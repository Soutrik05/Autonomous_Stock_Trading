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

The shared library (`core/`) contains no LLM calls and no network I/O during agent execution. Market data is loaded into local SQLite files by scheduled jobs.

```
data/                  # Rebuildable market caches (git-ignored)
├── ohlcv.db           # Daily OHLCV for Nifty 500
├── fundamental.db     # Statements & ratios (5-year history; 14-day re-fetch cadence)
├── news.db            # FinBERT headline scores
└── macro.db           # Daily regime rows + optional biweekly narrative

state/                 # Irreplaceable application state (git-ignored, backed up)
└── portfolio.db       # Accounts, orders, fills, positions, decisions, memory, NAV
```

## 1. Upstox Ingestion Engine

### 1.1 Endpoints
All market data comes from authenticated Upstox endpoints using a long-lived analytics token in `.env`:
- **Candles and quotes:** `GET /v2/historical-candle/{instrument_key}/day/{to_date}/{from_date}` and the batched market-quote endpoint (one call can quote many instruments).
- **Fundamentals** (looked up by ISIN): income statement, balance sheet, cash flow, key ratios, shareholding, corporate actions.
- **Market information:** market-level FII/DII flows.
- **VIX and indices:** India VIX and sector index quotes.
- **Holidays:** the exchange holiday list.

> **Day-1 spike (deliverable: `docs/upstox_findings.md`).** The paths above come from earlier plans and are unverified. On day 1, call each endpoint for 3 stocks and record: (a) that the analytics token works for live quotes, (b) the exact paths and parameters, (c) which fields exist: PEG, interest coverage, promoter pledging, how many years of quarters, (d) the real delivery brokerage on Upstox's pricing page. Any field that is missing is either computed from statements or dropped from the persona that needs it, and the persona definition is updated.

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
| after ingestion | Feature snapshots | `python -m core.build_features` | ingestion = SUCCESS |
| after features | Watchlist refresh | `python -m precompute.watchlist_refresh` | features = SUCCESS |
| 21:45 | Backup of `portfolio.db` | `python -m scripts.backup` | — |
| 22:00 | Agent runner (6 agents) | `python -m agents.runner` | watchlist = SUCCESS |
| 09:20–15:20, every 10 min | Monitor (one poll per run) | `python -m broker.monitor` | trading day |
| 15:30 | Order expiry | `python -m broker.expiry` | — |
| 15:35 | Settlement and daily NAV | `python -m broker.settlement` | — |
| 15:45 | Forward-return backfill | `python -m evaluation.forward_returns` | settlement |
| Sunday 10:00 | Reflection | `python -m reflection.engine` | — |
| 1st & 15th, 09:30 | Macro narrative (optional, context only) | `python -m agents.macro_context` | — |

The 09:20 start avoids the opening-auction price. The 10-minute grid ends exactly at 15:20. The data janitor is **deferred** (not needed in an 8-week run).

### 1.5 Ingestion Guards (`ingestion/cli.py`)
1. **Calendar guard.** `market_calendar` is seeded from the holiday API and refreshed nightly. On a holiday, price, fundamentals and macro syncs are skipped, news ingestion still runs, and the day is marked closed. "Next trading day" always comes from this table. Truncated sessions (Muhurat) are marked in `session_type`, and breakout signals are suppressed that day.
2. **Corporate-action detection.** A single-day drop rule is not enough, because splits have no volume signature and real crashes do. Instead, each night re-fetch the last ~10 adjusted candles for every held ticker and every watchlist ticker, and compare them to the cache. If adjusted history differs by more than `CORP_ACTION_DIFF_PCT`, purge and reload that ticker's cache. If the ticker is **held**, set `positions.frozen_reason = 'CORP_ACTION'`, skip stop checks for it, log an alert, and keep it frozen until the position's stop and target are adjusted by the split ratio (manual or scripted).
3. **Partial-failure resilience.** Retry each failed ticker 3 times with exponential backoff, then tag it `STALE_DATA`. Agents skip stale tickers. Held stale tickers are flagged in the prompt.
4. **Circuit-lock detection.** Zero volume or a frozen quote tags the ticker `LOCKED_CIRCUIT`. Fills and stop checks skip it, and the event is logged.
5. **WAL and timeouts.** All SQLite connections use `PRAGMA journal_mode=WAL` and a 5,000 ms busy timeout.
6. **Backup.** One method only: the SQLite backup API (`Connection.backup`) copies `portfolio.db` to `state/backups/portfolio_YYYY-MM-DD.db` nightly. The last 14 copies are kept.
7. **Winsorization.** Extreme ratios are clamped: P/E in [0, 150], PEG in [0, 5], D/E in [0, 10].

---

## 2. Feature Contract & Analyzers

### 2.1 FeatureSnapshot (`core/features.py`)
One **FeatureSnapshot** is built per (ticker, as-of date) by `core/build_features.py` and saved in `feature_snapshots` with a `schema_version`. It is the **only** place metrics are defined. Prompts, `cited_metrics`, screeners, forensics, heuristic triggers and the baseline all read these fields. Nothing else computes a metric on its own.

Every feature has a name, a unit and a **match rule** for the faithfulness check. Rule types: `REL(x)` = relative error within x; `ABS(x)` = absolute difference within x; `EXACT` = identical value.

| Group | Feature (allowed `cited_metrics` name) | Unit | Match rule |
|---|---|---|---|
| Price | `close` | ₹ | REL(0.5%) |
| Trend | `ema_20`, `ema_50`, `ema_200` | ₹ | REL(0.5%) |
| Trend | `ema_20_above_50` | flag | EXACT |
| Momentum | `rsi_14` | 0–100 | ABS(2.0) |
| Momentum | `macd_hist` | ₹ | ABS(0.1% of close) |
| Momentum | `adx_14` | 0–100 | ABS(2.0) |
| Volatility | `atr_14` | ₹ | REL(5%) |
| Volume | `volume_surge` | × | REL(5%) |
| Volume | `obv_slope_sign` | −1/0/+1 | EXACT |
| Structure | `dist_52w_high_pct`, `dist_52w_low_pct` | % | ABS(1.0) |
| Quality | `roce_pct`, `roe_pct` | % | ABS(1.0) |
| Valuation | `pe`, `pb`, `peg` | × | REL(5%) |
| Solvency | `debt_to_equity` | × | ABS(0.05) |
| Solvency | `interest_coverage` | × | REL(5%) |
| Cash flow | `cfo_to_pat` | × | ABS(0.05) |
| Growth | `pat_growth_yoy_pct`, `revenue_growth_yoy_pct` | % | ABS(1.0) |
| Ownership | `promoter_holding_pct`, `promoter_pledge_pct` | % | ABS(0.5) |
| Ownership | `fii_dii_qoq_delta_pct` | % | ABS(0.5) |
| News | `news_sentiment` | −1…+1 | ABS(0.05) |
| News | `news_article_count` | count | EXACT |
| Macro | `india_vix`, `regime` | value / label | ABS(0.5) / EXACT |

The list can grow, but a name is added here **first**. Any name an LLM cites that is not on the list counts as a mismatch.

### 2.2 Technical Module (`technical/`)
Vectorized NumPy/Pandas indicators with no network access: 20/50/200 EMA, RSI(14), MACD(12,26,9), ADX(14), ATR(14), volume surge, OBV, 52-week distances, Bollinger Bands, Donchian channels. A flat-price guard adds an epsilon to divisors and neutralises volatility signals when ATR is below 0.1% of price. OHLCV for all needed tickers is bulk-loaded once at startup, never per ticker. The internal layout of `technical/` is left to the builder. It exposes its public functions through `__init__.py`.

### 2.3 Fundamental Module (`fundamental/`)
Computes the fundamental features above from statements and ratios, with winsorization. Per-persona history depth: Simons none, Core 8 quarters, Marks 3 years, RJ 12 quarters, Lynch 20 quarters. A stock without enough history is excluded for that persona. Banking/NBFC stocks use their own profile (ROA, ROE, NPA trend, P/B vs sector) instead of D/E and operating margin. Sector peer percentiles are computed only where the peer group has at least `MIN_SECTOR_COHORT` (8) stocks. Smaller groups fall back to the whole-universe percentile.

### 2.4 News Module (`news_sentiment/`)
```python
class CompanyEntityMatcher:
    def extract_companies(self, text: str) -> list[str]:
        """Returns matched Nifty 500 trading symbols."""
        raise NotImplementedError
```
Implementation is the builder's choice (FlashText or compiled regex with word boundaries). Short or common-word tickers (`IT`, `ON`, `CAN`, `OIL`, `AT`) must never match on the bare word. They need co-occurring financial context ("shares", "Q3 profit", "Ltd") or the full legal name. Sentiment uses a local FinBERT model on matched headlines only, giving a score in [−1, 1]. Only the top 3 headlines per ticker, cut to 120 characters, reach a prompt.

### 2.5 Daily Regime (`macro.db`)
A **rule-based daily regime** is written by ingestion from India VIX bands (`VIX_BANDS` in settings). The default is `<14` LOW_VOL, `14–18` NORMAL, `18–24` ELEVATED, `>24` PANIC. The row also holds the Nifty 50 and Nifty 500 trend labels, FII/DII net flow and breadth. Forensics and heuristics use this daily regime. An optional LLM narrative (200 words, twice a month, owned only by `agents/macro_context.py`) is extra prompt context and nothing depends on it.

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

### 3.1 Personas as Configuration
A persona is a `PersonaConfig` object (`agents/personas/base.py`). One runner serves all five. Adding or tuning a persona never changes runner code.

```python
@dataclass(frozen=True)
class PersonaConfig:
    id: str
    name: str
    system_prompt: str            # philosophy, sizing guidance, risk caps, output rules
    technical_hurdles: dict       # Stage-1 boolean hurdles (reads FeatureSnapshot names)
    fundamental_hurdles: dict     # empty for Simons
    sort_key: str                 # Stage-2 intensity formula name
    ttl_days: int                 # Stage-3 watchlist lock
    lookback_days: int            # reflection window
    eval_horizon_days: int        # horizon used to score heuristics
    fundamentals_depth: str       # none | 8q | 3y | 12q | 20q
    uses_rag: bool
```

| Persona | Style | Holding horizon | Lookback | TTL | Eval horizon |
|---|---|---|---|---|---|
| **Jim Simons** | Trend, EMA alignment, volume expansion (≥1.2× SMA20), MACD acceleration, RSI 55–70 | 3–14 d | 14 d | 3 d | 5 d |
| **Peter Lynch** | GARP: PEG < 1, ROCE > 15%, D/E < 0.8, CFO/PAT > 0.8, accelerating earnings | 30–90 d | 90 d | 14 d | 20 d |
| **Howard Marks** | Quality oversold on bad news: RSI < 35, near 52-week low, low debt, stable promoters | 14–45 d | 21 d | 7 d | 10 d |
| **Rakesh Jhunjhunwala** | Growth compounders: rising promoter/FII stake, sector tailwind, breakout volume | 15–60 d | 45 d | 7 d | 10 d |
| **StockMinds Core** | Balanced technical + fundamental, grounded in Zerodha Varsity via hybrid RAG | 7–30 d | 30 d | 5 d | 10 d |

**Hybrid RAG (`rag/`, Core only).** Dense BGE embeddings plus BM25, merged by Reciprocal Rank Fusion, optionally followed by a cross-encoder re-ranker. It returns the top 2 Varsity rule snippets, limited to 250 tokens. The evaluation set is 30 hand-labelled queries. Target: hit rate @3 ≥ 90%. The re-ranker is added only if time allows. The internal layout is the builder's choice.

### 3.2 Candidate Selection, Batching & Token Budget
- **Review pool** = the agent's open positions **plus** its watchlist. Open positions are always included, even if they have left the watchlist. The pool is capped at `MAX_CANDIDATES_PER_RUN` (default 10) by dropping the lowest-intensity watchlist names first. `MAX_OPEN_POSITIONS_PER_AGENT` defaults to 5.
- **One LLM call per agent per night.** `AGENT_RUN_DELAY_SEC` (60) separates agents.
- **Compact numeric rows.** Each candidate is one dense line of about 100 tokens, built from the `FeatureSnapshot`:
  `TATAMOTORS|ENG|c=948.2|ema20/50/200=931/918/871|rsi=62.4|macdh=+1.8|vs=1.82|adx=24|atr=21.4|d52h=-4.1|roce=18.5|de=0.65|pe=14|news=+0.21(3)|pos=none`
- **Budget (estimate, to be measured on Day 2–3):**

| Block | Tokens |
|---|---|
| System prompt, persona rules, output contract | ~500 |
| Regime and macro line | ~150 |
| Active heuristics (≤5) | ~250 |
| Episodic memory (last 10 closed trades, compact) | ~300 |
| Portfolio state (cash, holdings, sector exposure) | ~250 |
| Candidates (8–10 rows × ~100) | ~800–1,000 |
| Varsity RAG (Core only) | ~250 |
| **Total prompt target** | **~2,800** (`PROMPT_TOKEN_TARGET`) |

`PROMPT_TOKEN_CEILING` (default 3,800) is enforced in Python. If the prompt is too long, trim in this order: RAG, episodic memory, lowest-intensity watchlist candidates. **Open positions are never trimmed.** Final numbers are set from measured prompts, not estimates.
- **Failure handling.** If the JSON fails validation, one repair retry is allowed. After that, every candidate defaults to `HOLD` and the failure is logged.
- **Safe to re-run.** If `decisions` already exist for (agent, run date), the runner skips that agent unless `--force` is given. With `--force`, it first cancels that agent's pending orders from the same run date and releases their reserved cash.

### 3.3 Decision Schema & Faithfulness
Each agent returns a list of decisions. Actions are `BUY`, `SELL`, `HOLD` or `ADJUST`. `SELL` always exits the **whole** position (no partial exits in the MVP).

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
      "pre_mortem_risk": "Commercial-vehicle margin squeeze if steel prices rise 4%.",
      "reasoning": "Breakout above 940 with 1.8x volume and 20/50 EMA crossover.",
      "cited_metrics": { "rsi_14": 62.4, "volume_surge": 1.82, "roce_pct": 18.5, "debt_to_equity": 0.65 }
    }
  ]
}
```
- `HOLD` needs only ticker and a one-line reason. `SELL` needs ticker and reason. `ADJUST` needs ticker plus new `stop_loss_price` and/or `target_price`.
- **Faithfulness check** (`evaluation/faithfulness.py`), run for every decision:
  - The decision must cite **at least 3** names from the allowed list in §2.1.
  - Each cited value is compared with the saved `FeatureSnapshot` for that ticker and date, using that feature's match rule.
  - Names not on the list, and values that do not match, count as mismatches.
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

## 5. Memory, Forensics & Reflection

### 5.1 Episodic Memory
The prompt includes the last `EPISODIC_MEMORY_LIMIT` (10) closed positions: ticker, entry reasoning excerpt, exit reason, hold days and PnL %.

### 5.2 Forensics (`reflection/forensics.py`)
Runs **at the moment a position closes**, so the diagnosis exists before any reflection. It is rule-based Python. A trade can fit more than one class, so the first match in this priority order wins:

- **Loss classes:** `CORP_ACTION_ARTIFACT` → `BROAD_MARKET_DRAG` (Nifty 50 fell > 2% while the position was open) → `REGIME_MISMATCH` (daily regime worsened, or VIX rose > 20%) → `EARNINGS_SHOCK` (single-day move ≥ 7% together with a results-related headline or announcement in the window) → `FALSE_BREAKOUT` (price back below entry within 3 sessions without volume confirmation) → `UNCLASSIFIED`.
- **Win classes** (PnL ≥ 4% and held ≥ 3 days): `TREND_CONTINUATION`, `EARNINGS_MOMENTUM`, `MEAN_REVERSION`, else `UNCLASSIFIED_WIN`.

The result is saved in `positions.forensics_type`, `diagnosis_json` and `regime_at_exit`. If the API has no earnings dates, `EARNINGS_SHOCK` uses the proxy above.

### 5.3 Forward Returns (`evaluation/forward_returns.py`)
Each night after settlement, for every row in `decisions` (LLM and baseline, including HOLD and skipped candidates), compute the stock's return and the Nifty 500 return over `FORWARD_HORIZONS` (default 1, 5, 10, 20 trading days) once enough days have passed. Results go to `forward_returns`. This gives hundreds of data points for the LLM-vs-baseline comparison and the only way to score AVOID heuristics.

### 5.4 Weekly Reflection (`reflection/engine.py`)
Runs on Sunday at 10:00.
1. **Eligible trades.** Positions closed **after** the agent's last reflection watermark (`reflection_runs`) and within its lookback window. This means the same trade is never read twice.
2. **Sample gate.** At least `MIN_CLOSED_TRADES_FOR_REFLECTION` (3) eligible trades. If fewer, skip and **do not move the watermark**.
3. **Heuristic generation.** The LLM reads the forensics reports and proposes heuristics. Each is a structured object:
   `{kind: SEEK|AVOID, trigger: <JSON predicate>, prescribed_action, rationale}`.
   The trigger uses only allowed `FeatureSnapshot` names, for example
   `{"all":[{"feature":"india_vix","op":">","value":22},{"feature":"volume_surge","op":">=","value":1.5}]}`.
   A heuristic with an invalid trigger is discarded.
4. **Watermark.** On success, record the run in `reflection_runs`.

### 5.5 Heuristic Lifecycle
- Every night, Python evaluates each active and testing heuristic's trigger against every candidate's `FeatureSnapshot`. If it fires, a row goes to `heuristic_applications` (linked to the decision) as `PENDING`.
- When the persona's `eval_horizon_days` has passed, the application is resolved from the candidate's **forward return** at that horizon: SEEK succeeds if the return is positive, AVOID succeeds if it is zero or negative. This works the same whether or not the agent actually traded.
- **States:** `testing` → `active` when ≥ 3 resolved applications and success rate ≥ 60% → `reinforced` when ≥ 10 resolved and ≥ 60% → `deprecated` when ≥ 3 resolved and success < 40%, or when it has not fired in 30 days.
- **Honest label:** with so few applications this is a **mechanism**, not statistical proof. The report says so.
- Active and reinforced heuristics (up to 5) are injected into the prompt.

## 6. Watchlist Curation Funnel (`precompute/watchlist_refresh.py`)

```
NIFTY 500 → Stage 0 liquidity gate → Stage 1 persona hurdles → Stage 2 intensity sort → Stage 3 sector cap + TTL
```
- **Stage 0 (all personas):** `ADV20 × price ≥ ₹5 crore`, circuit-lock blacklist, stock not `STALE_DATA`. The extra volume rule (`SMA5(vol) > SMA20(vol)`) applies **only to Simons and RJ**, because it is a momentum filter, not a liquidity filter.
- **Stage 1 (persona hurdles):** the boolean technical and fundamental hurdles from each `PersonaConfig`. A stock must pass both sets (Simons has no fundamental hurdles). **Sector percentile is used to rank, not to filter.** An optional filter `SECTOR_PERCENTILE_MIN` exists in settings, default off. Turn it on only if the pass counts are too high. If no stock passes, the watchlist is empty or tiny, and the agent holds cash. This is intended behaviour in a bear market.
- **Stage 2 (intensity sort):** a persona-specific sort key (for example Simons: volume surge × MACD slope; Lynch: ROCE / PEG).
- **Stage 3 (cap and lock):** at most 2 stocks per sector, a target size of 8–10, and a fixed TTL lock to stop daily churn. A stock leaves early only if it is structurally invalid (for example, it closes below the 200 EMA). Persisted in `agent_watchlist`.
- **Audit.** Each night the funnel logs how many stocks pass each stage per persona (to `activity_log`). In week 2, review these counts and adjust thresholds in `settings.py`.

### 6.1 The Rules-Only Baseline (`baselines/simons_rules.py`)
- A sixth agent, `baseline-simons-rules` (`agents.kind = 'BASELINE'`), with the same ₹1,00,000, the same broker, the same charges, slippage and fill rule.
- **Input:** the exact candidate list LLM Simons saw that night.
- **Entry (BUY)** if all hold: `ema_20_above_50`, `rsi_14` in 55–70, `volume_surge ≥ 1.2`, `macd_hist > 0`. Entry range: `close ± 0.25 × ATR`. Stop: `close − 2 × ATR`. Target: `close + 3 × ATR` (soft, like the LLM's).
- **Exit (SELL)** at the next-night run if `close < ema_20`, or the target was reached. The stop is automatic, as for every agent.
- **Size:** 10% of the account's starting capital per position, up to 5 positions, ranked by the same Stage-2 sort key.
- Its decisions are stored with `source='BASELINE'` from the **first live night**.

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

`data/macro.db` holds `macro_daily(trade_date, regime, india_vix, fii_net_cr, dii_net_cr, nifty50_trend, nifty500_trend, advance_decline, market_closed)` and the optional `macro_narrative` rows.

## Settings Specification (`settings.py`)
Everything below is a named constant, with no numbers hard-coded elsewhere. Highlights:
- **Capital and costs:** `INITIAL_CASH_PER_AGENT_PAISE = 10_000_000`, `SLIPPAGE_BPS = 10`, statutory rates (`STT_RATE`, `EXCHANGE_TURNOVER_RATE`, `SEBI_FEE_RATE`, `STAMP_DUTY_RATE`, `GST_RATE`, `DP_CHARGES_PAISE = 1534`, `BROKERAGE_PAISE = 0`).
- **Rate limits:** `RATE_LIMIT_PER_SEC = 45`, `RATE_LIMIT_PER_MIN = 450`, `RATE_LIMIT_PER_30MIN = 1800`.
- **Schedule:** ingestion 20:00, backup 21:45, agents 22:00, `MONITOR_START = 09:20`, `MONITOR_END = 15:20`, `MONITOR_INTERVAL_MIN = 10`, expiry 15:30, settlement 15:35, reflection Sunday 10:00. All in IST.
- **Orders:** `BUY_OVERSHOOT_PCT = 0.5`, `STOP_MAY_ONLY_RISE = True`, `MAX_OPEN_POSITIONS_PER_AGENT = 5`.
- **Prompts:** `MAX_CANDIDATES_PER_RUN = 10`, `AGENT_RUN_DELAY_SEC = 60`, `PROMPT_TOKEN_TARGET`, `PROMPT_TOKEN_CEILING = 3800`, `EPISODIC_MEMORY_LIMIT = 10`, `MIN_CITED_METRICS = 3`.
- **Funnel:** `MIN_SECTOR_COHORT = 8`, `SECTOR_PERCENTILE_MIN = 0` (off), per-persona hurdle dictionaries.
- **Learning:** `MIN_CLOSED_TRADES_FOR_REFLECTION = 3`, `FORWARD_HORIZONS = [1, 5, 10, 20]`, lifecycle thresholds.
- **Data:** `CORP_ACTION_DIFF_PCT`, `VIX_BANDS`, retry counts.

## Repository Tree

```text
Autonomous_Stock_Trading/
├── settings.py                    # Single source of truth for all constants
├── scheduler.py                   # APScheduler: calls the one-shot job entry points
├── .env.example  .gitignore  requirements.txt  Dockerfile  README.md
│
├── docs/
│   ├── Plan_v3.md                 # This document
│   └── upstox_findings.md         # Day-1 spike results
│
├── db/
│   ├── schema.sql                 # Baseline schema (== migration 0001)
│   └── migrations/                # 0001_baseline.sql, 0002_*.sql ...
│
├── scripts/
│   ├── init_db.py                 # Apply migrations, seed 5 LLM agents + baseline agent
│   ├── build_symbol_master.py     # symbol, instrument key, ISIN, sector
│   └── backup.py                  # Nightly sqlite backup API copy
│
├── core/                          # Shared tools (zero LLM, zero network at run time)
│   ├── __init__.py
│   ├── interfaces.py              # Clock, QuoteProvider (abstract base classes)
│   ├── clock.py                   # SystemClock (IST), FakeClock (tests/replay)
│   ├── database.py                # Connection factory, WAL, busy timeout
│   ├── money.py                   # paise <-> rupee helpers
│   ├── rate_limiter.py
│   ├── schemas.py                 # Pydantic models
│   ├── features.py                # FeatureSnapshot definition + match rules (§2.1)
│   └── build_features.py          # Builds and saves snapshots nightly
│
├── ingestion/
│   ├── __init__.py
│   ├── cli.py
│   ├── upstox_client.py
│   ├── sync_ohlcv.py
│   ├── sync_fundamentals.py
│   ├── sync_news.py
│   └── sync_macro.py              # VIX, flows, daily regime
│
├── technical/    fundamental/    news_sentiment/    rag/
│                                   # internal layout is the builder's choice;
│                                   # each exposes its public functions via __init__.py
│
├── precompute/
│   ├── __init__.py
│   └── watchlist_refresh.py       # 4-stage funnel + funnel-count logging
│
├── llm/
│   ├── __init__.py
│   └── client.py                  # LLMClient: providers, retries, spacing, logs to llm_calls
│
├── agents/
│   ├── __init__.py
│   ├── runner.py                  # One runner for all personas; idempotent per run date
│   ├── prompts.py
│   ├── parsers.py                 # JSON validation + repair
│   ├── context_assembler.py       # Compact candidate rows + token budget enforcement
│   ├── macro_context.py           # Optional biweekly narrative (single owner)
│   └── personas/
│       ├── base.py                # PersonaConfig
│       ├── simons.py  lynch.py  marks.py  jhunjhunwala.py  varsity.py   # config objects only
│
├── baselines/
│   ├── __init__.py
│   └── simons_rules.py            # Sixth agent, trades through the broker
│
├── broker/
│   ├── __init__.py
│   ├── engine.py                  # Validation, orders, reservation, fills, averaging, ADJUST
│   ├── transaction_charges.py
│   ├── quotes.py                  # LiveQuoteProvider, ReplayQuoteProvider
│   ├── monitor.py                 # One poll per run (stateless)
│   ├── expiry.py                  # 15:30 expiry of unfilled orders
│   └── settlement.py              # 15:35 daily NAV
│
├── reflection/
│   ├── __init__.py
│   ├── forensics.py               # Runs at position close
│   ├── engine.py                  # Weekly reflection with watermark
│   └── memory_manager.py          # Heuristic firing, resolution, lifecycle
│
├── evaluation/
│   ├── __init__.py
│   ├── performance.py             # Sharpe, drawdown, alpha, win rate
│   ├── faithfulness.py            # Cited-metric verification
│   ├── forward_returns.py         # Nightly forward-return backfill
│   └── comparison.py              # LLM vs baseline vs Nifty 500
│
├── api/
│   ├── __init__.py
│   ├── main.py
│   └── routes/  leaderboard.py  portfolio.py  activity.py  baseline.py  memory.py  health.py
│
├── web/                           # React (Vite + Tailwind)
│   └── src/
│       ├── App.jsx
│       ├── pages/  Leaderboard.jsx  AgentDetail.jsx  BaselineCompare.jsx  ActivityFeed.jsx
│       └── components/  MetricBadge.jsx  EquityCurve.jsx  PositionTable.jsx
│
├── data/    .gitkeep              # market caches (git-ignored)
├── state/   .gitkeep              # portfolio.db + backups (git-ignored)
│
└── tests/
    ├── conftest.py                # Fake OHLCV, FakeClock, FakeLLM, ReplayQuoteProvider
    ├── test_upstox_auth.py        # Day-1 spike
    ├── unit/    test_charges.py  test_money.py  test_rate_limiter.py  test_indicators.py
    │            test_broker_rules.py  test_faithfulness.py  test_heuristic_triggers.py
    └── integration/  test_nightly_flow.py  test_order_lifecycle.py
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

### Week 1 — Foundations and the Simons vertical slice, live by the end of the week
- **Day 1 (spike and contracts):** Upstox spike → `docs/upstox_findings.md`. Symbol master. `settings.py`, `db/schema.sql` + migrations, `Clock`, `QuoteProvider`, `LLMClient` interfaces, `core/money.py`.
- **Days 2–3:** rate limiter, OHLCV ingestion, calendar. Technical module, `FeatureSnapshot`, Stage 0–3 funnel for Simons. LLM client and compact prompts, **measure real token counts**, set the budget.
- **Days 3–4:** broker engine (validation, reservation, charges, slippage, fills, averaging, ADJUST), monitor, expiry, settlement, forensics, baseline agent. Unit tests for charges, money, reservation and order lifecycle.
- **Day 5:** scheduler, deploy to one always-on server with a persistent disk, replay dry run of a full night with `FakeLLM`.
- **End of week 1:** **first live night** for LLM Simons and rules Simons. Snapshots, decisions, NAV and pipeline runs are all being captured.

### Week 2 — Remaining personas and data
- Fundamentals, news and sector percentiles. Persona configs for Marks, Core, Lynch and RJ. RAG for Core.
- Add each persona to the live run once it passes a replay dry run.
- **Funnel audit:** review the nightly pass counts, adjust thresholds, check that bear-market starvation behaves as intended.
- If the Day-1 spike found missing fields, finalise how each affected persona changes.

### Week 3 — Learning loop and evaluation
- Forward-return backfill, reflection with watermark, heuristic triggers, lifecycle, `heuristic_applications`.
- Evaluation module: Sharpe, drawdown, alpha, faithfulness, paired comparison.
- Review the first two weeks of data: parse failure rate, missed fills, faithfulness, token use.

### Week 4 — API and dashboard
- FastAPI endpoints and the React dashboard. Health page. Small-sample labels.

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
| Upstox fundamentals fields missing or different | High | Day-1 spike. Compute from statements or drop the metric for that persona. Persona definition updated in week 1–2. |
| Missed nights of data | High | Deploy and go live at the end of week 1. `pipeline_runs`, health page and failure alerts. Snapshots and decisions saved every night. |
| Runner starts on partial data | High | `pipeline_runs` check before every job. Runner refuses to start unless ingestion, features and watchlist are SUCCESS. |
| Double fill after a monitor restart | High | Atomic `UPDATE ... WHERE status='pending'`. Monitor is stateless. |
| Reserved-cash drift | High | No stored counter. Reserved cash is the SUM of pending BUY reservations. Nightly consistency check. |
| Floating-point money errors | Medium | Integer paise everywhere. Charges rounded once per fill. |
| Date or timezone bugs | Medium | IST `Clock` injected everywhere. No database default timestamps. `market_calendar` for trading days. Tests with `FakeClock`. |
| Split or bonus on a held stock | Medium | Overlap re-fetch comparison. Freeze stops, alert, adjust by split ratio. |
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
