-- ============================================================
-- schema.sql
-- Database schema for the Job Application Tracker.
--
-- Two tables, on purpose:
--   1. applications  - one row per job you applied to (current state)
--   2. status_log    - one row per status CHANGE for an application
--                      (history, linked back via a foreign key)
--
-- Splitting "current state" from "history" like this is a common
-- real-world pattern, and it's what lets you practice JOINs instead
-- of just single-table SELECTs. As you learn more SQL, this is one
-- of the project's "weak points" you can build on (e.g. add an
-- interviews table, a contacts table, etc.) following the same idea.
-- ============================================================

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS applications (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    company         TEXT    NOT NULL,
    position        TEXT    NOT NULL,
    date_applied    TEXT    NOT NULL,           -- ISO format: 'YYYY-MM-DD'
    status          TEXT    NOT NULL DEFAULT 'Applied'
        CHECK (status IN (
            'Applied', 'Phone Screen', 'Interview',
            'Offer', 'Rejected', 'Withdrawn'
        )),
    job_url         TEXT,
    location        TEXT,
    salary_range    TEXT,
    source          TEXT,                       -- e.g. LinkedIn, Referral, Indeed
    notes           TEXT,
    follow_up_date  TEXT,                        -- ISO date or NULL
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS status_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id  INTEGER NOT NULL,
    old_status      TEXT,
    new_status      TEXT    NOT NULL,
    changed_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (application_id) REFERENCES applications (id)
        ON DELETE CASCADE
);

-- Helpful indexes for the queries you'll run most (filtering by
-- status, sorting by date applied, looking up history per application).
CREATE INDEX IF NOT EXISTS idx_applications_status ON applications (status);
CREATE INDEX IF NOT EXISTS idx_applications_date ON applications (date_applied);
CREATE INDEX IF NOT EXISTS idx_status_log_app_id ON status_log (application_id);
