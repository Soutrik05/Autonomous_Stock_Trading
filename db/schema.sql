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
