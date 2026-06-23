# Job Application Tracker

A starter project for tracking job applications, built around SQLite + Python
so you get real SQL and Python practice while using it this summer.

## Files

| File | Purpose |
|---|---|
| `schema.sql` | Table definitions (`applications`, `status_log`) |
| `db.py` | All database access — every SQL query the project runs lives here, commented |
| `cli.py` | Interactive menu app: add, update, list, search, stats, delete |
| `gmail_sync.py` | Scans Gmail and auto-updates application statuses from recruiting emails |
| `queries/learning_queries.sql` | Standalone SQL queries, basic → advanced, to run and tweak |
| `job_applications.db` | The actual database file (created the first time you run anything) |

## Setup

No installs needed for the core tracker — everything uses Python's built-in `sqlite3` module.
Requires Python 3.10+ (uses the `int | None` type hint style).

```
python cli.py        # launch the interactive tracker
```

For Gmail sync, install the Google API client once:

```
pip install google-api-python-client google-auth-oauthlib
```

Then place your `credentials.json` (from Google Cloud Console) in this folder and run:

```
python gmail_sync.py
```

## Using the CLI

`python cli.py` opens a numbered menu: add an application, move one through
statuses (`Applied → Phone Screen → Interview → Offer/Rejected/Withdrawn`),
list everything, filter by status, search, view one application's full
history, see stats, or delete a row.

## Practicing SQL directly

The CLI is the "app," but the point of this project is also the SQL itself.
Open the database directly and run the queries in `queries/learning_queries.sql`:

```
sqlite3 job_applications.db
.headers on
.mode column
```

Then paste in any query from that file, or run the whole file at once:

```
sqlite3 job_applications.db ".read queries/learning_queries.sql"
```

The file walks through `SELECT`/`WHERE`/`ORDER BY`, `GROUP BY` aggregation,
date arithmetic, `CASE` expressions, `JOIN`s between `applications` and
`status_log`, and finishes with subqueries, CTEs, and window functions
(`LAG()`, running totals). There are three open-ended exercises at the
bottom with no answers given — that's intentional.

## Schema

**`applications`** — one row per job, current state: company, position,
date applied, status, job URL, location, salary range, source, notes,
follow-up date.

**`status_log`** — one row per status *change*, linked to `applications`
by `application_id` (a foreign key). This is what lets you JOIN and ask
questions like "how long did each application spend in Phone Screen before
moving on" instead of only ever seeing the current snapshot.

## Python concepts in db.py / cli.py worth studying

Parameterized queries (`?` placeholders) instead of string-formatted SQL —
the only safe way to pass values into a query. `sqlite3.Row` + `dict()` for
named column access. Separating data access (`db.py`) from the user
interface (`cli.py`). A small allow-list pattern for the one place
(`ORDER BY` column, `UPDATE` column names) where untrusted input controls
SQL structure rather than a value. Type hints (`str | None`), keyword
arguments with defaults, and `**fields` for building a dynamic `UPDATE`.

## Where to take this next (your "weak points" list)

This is deliberately a starting point, not a finished tool. Ideas for
extending it as your Python/SQL improve:

- Export query results to CSV (`csv` module) or pull them into pandas for
  analysis/charts.
- Add an `interviews` table (one application can have many interview
  rounds) — more foreign-key/JOIN practice.
- Add a `contacts` table for recruiter/referral names tied to an application.
- Swap the CLI for a tiny Flask or FastAPI app with a real web form.
- Write a script that emails or notifies you about overdue follow-ups
  (there's already a query for "overdue follow-ups" in `learning_queries.sql`).
- Add full-text search, or migrate from SQLite to Postgres once you want
  to practice a "real" client-server database.
- Write `pytest` tests for the functions in `db.py`.

As you actually start applying and bump into something the tracker doesn't
handle well, that's the signal for what to build next — add it to this list.
