-- Migration 0014: Track dividend cash credits disbursed to agents for holding positions across ex-dates
CREATE TABLE IF NOT EXISTS dividend_payouts (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id          TEXT NOT NULL,
    ticker            TEXT NOT NULL,
    position_id       INTEGER NOT NULL,
    ex_date           TEXT NOT NULL,
    amount_per_share  REAL NOT NULL,
    shares            INTEGER NOT NULL,
    payout_paise      INTEGER NOT NULL,
    credited_at       TEXT NOT NULL,
    FOREIGN KEY (agent_id) REFERENCES agents(id),
    FOREIGN KEY (position_id) REFERENCES positions(id),
    UNIQUE (agent_id, ticker, ex_date)
);

CREATE INDEX IF NOT EXISTS idx_dividend_payouts_agent_date
    ON dividend_payouts(agent_id, ex_date);

