-- Migration 0005: a heuristic may fire on a given decision at most once. Without this,
-- re-running learning/memory_manager.py's nightly trigger evaluation for the same date (or two
-- processes racing) could insert the same (heuristic_id, decision_id) pair twice. Purely
-- additive -- db/schema.sql is the frozen migration-0001 baseline and is never edited after the
-- fact (confirmed: it has been byte-identical to 0001_baseline.sql since Day 1).
CREATE UNIQUE INDEX IF NOT EXISTS idx_heuristic_applications_unique
    ON heuristic_applications(heuristic_id, decision_id);
