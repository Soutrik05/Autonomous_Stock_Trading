-- Migration 0006: tags each llm_calls row with what it was for. Nightly decision calls stay
-- NULL (their existing behaviour, unchanged); learning/engine.py's weekly reflection calls are
-- tagged 'reflection' so they can be queried/seen separately from decision calls.
ALTER TABLE llm_calls ADD COLUMN purpose TEXT;
