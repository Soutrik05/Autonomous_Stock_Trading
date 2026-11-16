-- Migration 0007: the reflection watermark must be keyed by (exit_date, position_id), not
-- position_id alone. learning/engine.py now walks closed positions in EXIT order so that one
-- long-held OPEN position (entry order can put a low id well ahead of its eventual exit) never
-- blocks reflection on every later-closing trade. last_position_id_reviewed is kept and still
-- populated (set equal to last_position_id_in_that_exit_order on every write) so anything that
-- already reads it keeps working unchanged.
ALTER TABLE reflection_runs ADD COLUMN last_exit_date_reviewed TEXT;
ALTER TABLE reflection_runs ADD COLUMN last_position_id_in_that_exit_order INTEGER;
