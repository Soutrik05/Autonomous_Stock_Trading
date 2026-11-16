-- Migration 0008: nullable agent_memory.lifecycle_epoch_start, for the rolling-demotion fix in
-- learning/memory_manager.py::update_lifecycle. NULL means "since the beginning" -- an
-- un-demoted heuristic's "epoch" stats are identical to its lifetime stats. When a heuristic is
-- demoted (reinforced->active or active->testing), this is set to the date of the demotion, so
-- promotion afterwards is judged only on fresh evidence resolved on or after that date, never
-- on the old lifetime record that triggered the demotion in the first place.
ALTER TABLE agent_memory ADD COLUMN lifecycle_epoch_start TEXT;
