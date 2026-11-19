-- Migration 0011: Performance indexes for query acceleration across backtest, live runs, and reporting.
-- 1. Accelerates date-first feature lookups (avoids full table scan on 100k+ rows)
CREATE INDEX IF NOT EXISTS idx_feature_snapshots_date_ticker
    ON feature_snapshots(as_of_date, ticker);

-- 2. Accelerates activity log queries for events (e.g. TARGET_REACHED, CAP_BREACH, daily audits)
CREATE INDEX IF NOT EXISTS idx_activity_log_event_agent_date
    ON activity_log(event_type, agent_id, created_at);

-- 3. Accelerates episodic memory and reflection trade lookups (CLOSED positions by exit date)
CREATE INDEX IF NOT EXISTS idx_positions_agent_status_exit
    ON positions(agent_id, status, exit_date);

-- 4. Accelerates decision lookups by run_date
CREATE INDEX IF NOT EXISTS idx_decisions_run_date_agent
    ON decisions(run_date, agent_id);

-- 5. Accelerates active/testing heuristic retrieval
CREATE INDEX IF NOT EXISTS idx_agent_memory_agent_status
    ON agent_memory(agent_id, status);

-- 6. Accelerates nightly resolution of pending heuristic applications
CREATE INDEX IF NOT EXISTS idx_heuristic_applications_pending
    ON heuristic_applications(outcome) WHERE outcome = 'PENDING';

