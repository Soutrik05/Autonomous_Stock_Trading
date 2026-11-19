-- Migration 0010: Add context column to agent_memory to differentiate ENTRY vs EXIT rules.
-- 'ENTRY': evaluates on candidate decisions (SEEK=BUY, AVOID=filter)
-- 'EXIT': evaluates on open positions nightly (SEEK=sell signal, AVOID=hold signal)
-- 'ANY': evaluates in both contexts

ALTER TABLE agent_memory ADD COLUMN context TEXT NOT NULL DEFAULT 'ENTRY';

