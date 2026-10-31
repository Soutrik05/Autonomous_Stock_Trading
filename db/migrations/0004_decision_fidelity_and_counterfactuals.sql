-- Migration 0004: add decision fidelity and counterfactual sizing tracking to decisions table.
-- Captures raw uncalibrated LLM decisions, formula-derived counterfactuals, and sizing fidelity scores.
ALTER TABLE decisions ADD COLUMN raw_llm_json TEXT;
ALTER TABLE decisions ADD COLUMN counterfactual_shares INTEGER;
ALTER TABLE decisions ADD COLUMN counterfactual_stop_paise INTEGER;
ALTER TABLE decisions ADD COLUMN counterfactual_target_paise INTEGER;
ALTER TABLE decisions ADD COLUMN sizing_fidelity_score REAL;

