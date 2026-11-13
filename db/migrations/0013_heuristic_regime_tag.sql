-- Migration 0013: Add regime_tag column to agent_memory to partition learned heuristics by macro market regime.
-- Values: 'ALL', 'BULL_TREND', 'RANGE_BOUND', 'HIGH_VOLATILITY'.
-- Prevents negative transfer across conflicting macro volatility cycles.

ALTER TABLE agent_memory ADD COLUMN regime_tag TEXT NOT NULL DEFAULT 'ALL';

