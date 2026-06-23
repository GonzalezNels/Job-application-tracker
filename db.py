"""
db.py
-----
All the database access for the Job Application Tracker lives here.

This is the "Python talking to SQL" layer. Every function below does
the same three things: build a SQL string with placeholders, execute
it through sqlite3, and turn the result into something easy to use
in plain Python (dicts / lists of dicts).

Why placeholders ("?") instead of f-strings?
    cur.execute("SELECT * FROM applications WHERE company = ?", (company,))
    NOT
    cur.execute(f"SELECT * FROM applications WHERE company = '{company}'")
The second form is vulnerable to SQL injection and breaks on quotes
in the data. Always let sqlite3 substitute the values for you.

DB_PATH points at a single file on disk - that's the whole "database
server" for SQLite. No setup, no daemon, just a file.
"""

import sqlite3
from pathlib import Path
from datetime import date

DB_PATH = Path(__file__).parent / "job_applications.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"

VALID_STATUSES = (
    "Applied", "Phone Screen", "Interview", "Offer", "Rejected", "Withdrawn",
)


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """Open a connection to the SQLite database file.

    row_factory = sqlite3.Row lets us access columns by name
    (row["company"]) instead of by position (row[1]), and we can
    convert a row to a plain dict with dict(row).
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Create the tables (if they don't already exist) from schema.sql.

    executescript() lets us run a whole .sql file's worth of statements
    in one call, instead of one execute() per statement.
    """
    sql = SCHEMA_PATH.read_text()
    conn.executescript(sql)
    conn.commit()


# ---------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------

def add_application(
    conn: sqlite3.Connection,
    company: str,
    position: str,
    date_applied: str | None = None,
    status: str = "Applied",
    job_url: str | None = None,
    location: str | None = None,
    salary_range: str | None = None,
    source: str | None = None,
    notes: str | None = None,
    follow_up_date: str | None = None,
) -> int:
    """Insert a new application row. Returns the new row's id.

    date_applied defaults to today if you don't pass one - a small
    example of doing logic in Python rather than SQL when it's easier.
    """
    if date_applied is None:
        date_applied = date.today().isoformat()

    cur = conn.execute(
        """
        INSERT INTO applications (
            company, position, date_applied, status,
            job_url, location, salary_range, source, notes, follow_up_date
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (company, position, date_applied, status,
         job_url, location, salary_range, source, notes, follow_up_date),
    )

    # Log the initial status too, so status_log always has a starting point.
    conn.execute(
        """
        INSERT INTO status_log (application_id, old_status, new_status)
        VALUES (?, NULL, ?)
        """,
        (cur.lastrowid, status),
    )

    conn.commit()
    return cur.lastrowid


# ---------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------

def get_application(conn: sqlite3.Connection, application_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM applications WHERE id = ?", (application_id,)
    ).fetchone()
    return dict(row) if row else None


def list_applications(
    conn: sqlite3.Connection,
    status: str | None = None,
    order_by: str = "date_applied DESC",
) -> list[dict]:
    """List applications, optionally filtered to a single status.

    order_by is inserted directly (not as a "?" parameter) because
    SQLite doesn't allow column names/SQL keywords as bound parameters
    - only values. We guard it with a small allow-list so this never
    becomes a place to sneak in arbitrary SQL.
    """
    allowed_order = {
        "date_applied DESC", "date_applied ASC",
        "company ASC", "status ASC",
    }
    if order_by not in allowed_order:
        order_by = "date_applied DESC"

    if status:
        query = f"SELECT * FROM applications WHERE status = ? ORDER BY {order_by}"
        rows = conn.execute(query, (status,)).fetchall()
    else:
        query = f"SELECT * FROM applications ORDER BY {order_by}"
        rows = conn.execute(query).fetchall()

    return [dict(r) for r in rows]


def search_applications(conn: sqlite3.Connection, keyword: str) -> list[dict]:
    """Search company / position / notes for a keyword (case-insensitive).

    LIKE with % wildcards does substring matching. We wrap the keyword
    in %...% so it can match anywhere in the field.
    """
    pattern = f"%{keyword}%"
    rows = conn.execute(
        """
        SELECT * FROM applications
        WHERE company LIKE ? OR position LIKE ? OR notes LIKE ?
        ORDER BY date_applied DESC
        """,
        (pattern, pattern, pattern),
    ).fetchall()
    return [dict(r) for r in rows]


def get_status_history(conn: sqlite3.Connection, application_id: int) -> list[dict]:
    rows = conn.execute(
        """
        SELECT * FROM status_log
        WHERE application_id = ?
        ORDER BY changed_at ASC
        """,
        (application_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_stats(conn: sqlite3.Connection) -> dict:
    """A few summary numbers, computed in SQL rather than in Python.

    GROUP BY status + COUNT(*) is the classic "tally by category" query.
    We also compute a couple of derived stats in Python after pulling
    the raw counts back, since that's often simpler than one giant
    SQL statement.
    """
    by_status_rows = conn.execute(
        "SELECT status, COUNT(*) AS n FROM applications GROUP BY status"
    ).fetchall()
    by_status = {row["status"]: row["n"] for row in by_status_rows}

    total = sum(by_status.values())
    interviews_or_better = sum(
        by_status.get(s, 0) for s in ("Phone Screen", "Interview", "Offer")
    )
    response_rate = (interviews_or_better / total * 100) if total else 0.0

    return {
        "total": total,
        "by_status": by_status,
        "response_rate_pct": round(response_rate, 1),
    }


# ---------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------

def update_status(conn: sqlite3.Connection, application_id: int, new_status: str) -> bool:
    """Move an application to a new status and record it in status_log.

    Returns False if the application doesn't exist or the status is invalid.
    """
    if new_status not in VALID_STATUSES:
        return False

    current = get_application(conn, application_id)
    if current is None:
        return False

    old_status = current["status"]

    conn.execute(
        """
        UPDATE applications
        SET status = ?, updated_at = datetime('now')
        WHERE id = ?
        """,
        (new_status, application_id),
    )
    conn.execute(
        """
        INSERT INTO status_log (application_id, old_status, new_status)
        VALUES (?, ?, ?)
        """,
        (application_id, old_status, new_status),
    )
    conn.commit()
    return True


def update_application(conn: sqlite3.Connection, application_id: int, **fields) -> bool:
    """Update arbitrary editable fields (not status - use update_status for that).

    Demonstrates building a dynamic SQL statement from a dict of
    column -> new value, while still using "?" placeholders for the
    actual values (only the column NAMES come from a checked allow-list).
    """
    editable_columns = {
        "company", "position", "date_applied", "job_url",
        "location", "salary_range", "source", "notes", "follow_up_date",
    }
    fields = {k: v for k, v in fields.items() if k in editable_columns}
    if not fields:
        return False

    set_clause = ", ".join(f"{col} = ?" for col in fields)
    values = list(fields.values()) + [application_id]

    conn.execute(
        f"""
        UPDATE applications
        SET {set_clause}, updated_at = datetime('now')
        WHERE id = ?
        """,
        values,
    )
    conn.commit()
    return True


# ---------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------

def delete_application(conn: sqlite3.Connection, application_id: int) -> bool:
    """Delete an application. ON DELETE CASCADE (in schema.sql) takes
    care of deleting its status_log rows automatically.
    """
    cur = conn.execute("DELETE FROM applications WHERE id = ?", (application_id,))
    conn.commit()
    return cur.rowcount > 0
