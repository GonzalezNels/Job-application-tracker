-- ============================================================
-- learning_queries.sql
--
-- A set of SQL queries against job_applications.db, ordered from
-- basic to advanced. Run them with the sqlite3 command-line tool:
--
--     sqlite3 job_applications.db
--     .headers on
--     .mode column
--     -- then paste any single query below and press Enter
--
-- Or run a whole section at once:
--     sqlite3 job_applications.db ".read queries/learning_queries.sql"
--
-- Tables available: applications, status_log (see schema.sql).
-- ============================================================


-- ------------------------------------------------------------
-- LEVEL 1: SELECT, WHERE, ORDER BY
-- ------------------------------------------------------------

-- All columns, every application.
SELECT * FROM applications;

-- Just a few columns, most recent first.
SELECT company, position, status, date_applied
FROM applications
ORDER BY date_applied DESC;

-- Filter to one status.
SELECT company, position, date_applied
FROM applications
WHERE status = 'Interview';

-- Filter with multiple conditions (AND / OR), and pattern matching.
SELECT company, position, location
FROM applications
WHERE status != 'Rejected'
  AND location LIKE '%Remote%';


-- ------------------------------------------------------------
-- LEVEL 2: Aggregation - COUNT, GROUP BY, HAVING
-- ------------------------------------------------------------

-- How many applications are in each status? This is the query
-- db.py's get_stats() runs under the hood.
SELECT status, COUNT(*) AS n
FROM applications
GROUP BY status
ORDER BY n DESC;

-- Which sources (LinkedIn, Referral, ...) are you using, and how many
-- applications came from each?
SELECT source, COUNT(*) AS n
FROM applications
GROUP BY source
ORDER BY n DESC;

-- GROUP BY + HAVING: statuses with more than 1 application.
SELECT status, COUNT(*) AS n
FROM applications
GROUP BY status
HAVING COUNT(*) > 1;


-- ------------------------------------------------------------
-- LEVEL 3: Date functions, CASE expressions
-- ------------------------------------------------------------

-- How many days ago was each application submitted?
-- julianday() converts a date to a number so subtraction works.
SELECT
    company,
    position,
    date_applied,
    CAST(julianday('now') - julianday(date_applied) AS INTEGER) AS days_ago
FROM applications
ORDER BY days_ago DESC;

-- Bucket applications into "stale" vs "fresh" using CASE - SQL's
-- equivalent of an if/elif/else expression.
SELECT
    company,
    position,
    status,
    CASE
        WHEN status IN ('Offer', 'Rejected', 'Withdrawn') THEN 'Closed'
        WHEN julianday('now') - julianday(date_applied) > 21 THEN 'Stale (3+ weeks, no resolution)'
        ELSE 'Active'
    END AS bucket
FROM applications;

-- Applications with a follow-up date that has already passed -
-- these are the ones you probably owe a nudge email.
SELECT company, position, follow_up_date
FROM applications
WHERE follow_up_date IS NOT NULL
  AND follow_up_date < date('now')
ORDER BY follow_up_date;


-- ------------------------------------------------------------
-- LEVEL 4: JOINs across applications + status_log
-- ------------------------------------------------------------

-- For every status change, show which company/position it belongs to.
-- This is an INNER JOIN: only rows that match on both sides show up.
SELECT
    a.company,
    a.position,
    s.old_status,
    s.new_status,
    s.changed_at
FROM status_log AS s
JOIN applications AS a ON a.id = s.application_id
ORDER BY a.company, s.changed_at;

-- How many status changes has each application been through?
-- LEFT JOIN here means applications with ZERO log rows would still
-- show up (with n = 0) - useful if you ever insert an application
-- without going through db.add_application().
SELECT
    a.id,
    a.company,
    a.position,
    COUNT(s.id) AS status_changes
FROM applications AS a
LEFT JOIN status_log AS s ON s.application_id = a.id
GROUP BY a.id
ORDER BY status_changes DESC;

-- Full timeline for ONE application (swap the id for one that exists
-- in your data - run "SELECT id, company FROM applications;" first).
SELECT old_status, new_status, changed_at
FROM status_log
WHERE application_id = 5
ORDER BY changed_at;


-- ------------------------------------------------------------
-- LEVEL 5: Subqueries, CTEs, window functions
-- ------------------------------------------------------------

-- Subquery in WHERE: applications that have NEVER had a "Rejected"
-- entry in their history (still alive, in other words).
SELECT company, position, status
FROM applications
WHERE id NOT IN (
    SELECT application_id FROM status_log WHERE new_status = 'Rejected'
);

-- CTE (WITH ... AS): same idea, written as a named, reusable subquery.
-- CTEs make multi-step logic much easier to read than nesting
-- subqueries inside subqueries.
WITH rejected_ids AS (
    SELECT DISTINCT application_id FROM status_log WHERE new_status = 'Rejected'
)
SELECT company, position, status
FROM applications
WHERE id NOT IN (SELECT application_id FROM rejected_ids);

-- Window function: how many days did each application spend in its
-- PREVIOUS status before moving to the next one? LAG() looks at the
-- previous row within the same application_id, ordered by time.
SELECT
    application_id,
    old_status,
    new_status,
    changed_at,
    CAST(
        julianday(changed_at) - julianday(
            LAG(changed_at) OVER (PARTITION BY application_id ORDER BY changed_at)
        ) AS INTEGER
    ) AS days_since_previous_change
FROM status_log
ORDER BY application_id, changed_at;

-- Running total of applications submitted over time (a simple way to
-- see your application "pace" week over week).
SELECT
    date_applied,
    COUNT(*) AS applications_that_day,
    SUM(COUNT(*)) OVER (ORDER BY date_applied) AS running_total
FROM applications
GROUP BY date_applied
ORDER BY date_applied;


-- ------------------------------------------------------------
-- TRY IT YOURSELF (no answers given - this is where you practice)
-- ------------------------------------------------------------
-- 1. Write a query that shows the average number of days between
--    "Applied" and "Phone Screen" across all applications that
--    reached that stage. (Hint: self-join status_log to itself, or
--    use two LAG()/filtered subqueries.)
--
-- 2. Write a query that finds your single oldest still-"Applied"
--    application that you haven't heard back on.
--
-- 3. Add a few real applications via cli.py, then write a query
--    that computes your overall response rate (Phone Screen or
--    further, divided by total) WITHOUT using Python - pure SQL,
--    using CAST(... AS REAL) so the division isn't integer division.
-- ------------------------------------------------------------
