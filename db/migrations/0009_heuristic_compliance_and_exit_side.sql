-- Migration 0009: Add compliance tracking and exit-side position applications to heuristic_applications.
-- Recreates the table so decision_id becomes nullable (for exit-side position applications),
-- adds position_id, context ('ENTRY' | 'EXIT'), and complied (1=complied, 0=defied, NULL=not applicable).
-- Preserves existing records and enforces partial unique indexes for entry and exit fires.

CREATE TABLE IF NOT EXISTS heuristic_applications_new (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    heuristic_id    INTEGER NOT NULL,
    decision_id     INTEGER,                            -- nullable for exit-side position applications
    position_id     INTEGER,                            -- populated for exit-side position applications
    context         TEXT NOT NULL DEFAULT 'ENTRY',      -- ENTRY | EXIT
    fired_on        TEXT NOT NULL,
    horizon_days    INTEGER NOT NULL,
    outcome         TEXT NOT NULL DEFAULT 'PENDING',    -- PENDING | SUCCESS | FAILURE
    resolved_on     TEXT,
    complied        INTEGER,                            -- 1 (True) | 0 (False) | NULL
    FOREIGN KEY (heuristic_id) REFERENCES agent_memory(id),
    FOREIGN KEY (decision_id) REFERENCES decisions(id),
    FOREIGN KEY (position_id) REFERENCES positions(id)
);

INSERT INTO heuristic_applications_new (id, heuristic_id, decision_id, position_id, context, fired_on, horizon_days, outcome, resolved_on, complied)
SELECT id, heuristic_id, decision_id, NULL, 'ENTRY', fired_on, horizon_days, outcome, resolved_on, 1 FROM heuristic_applications;

DROP TABLE heuristic_applications;

ALTER TABLE heuristic_applications_new RENAME TO heuristic_applications;

CREATE UNIQUE INDEX IF NOT EXISTS idx_heuristic_applications_unique_entry
    ON heuristic_applications(heuristic_id, decision_id) WHERE decision_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_heuristic_applications_unique_exit
    ON heuristic_applications(heuristic_id, position_id, fired_on) WHERE position_id IS NOT NULL;

