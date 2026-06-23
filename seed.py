"""
seed.py
-------
Populates job_applications.db with ~12 realistic-looking fake
applications, each with a believable status history, so there's
something to query immediately - before you've applied anywhere
for real.

Run it directly:
    python seed.py

It's safe to re-run: it wipes existing rows first (DELETE), then
reinserts the sample set.

This file inserts rows with plain conn.execute() calls (instead of
going through db.py's helper functions) on purpose - it's a second,
slightly more "raw SQL" example to read alongside db.py's higher-level
functions.
"""

from datetime import date, timedelta

import db

# Each entry: (company, position, date_applied, job_url, location,
#              salary_range, source, history)
# history = list of (days_after_applied, status) tuples, in order.
# The application's final status = history[-1][1].
SAMPLE_DATA = [
    ("Acme Corp", "Software Engineer", date(2026, 5, 1),
     "https://acme.example.com/careers/123", "Remote", "$100k-$130k", "LinkedIn",
     [(0, "Applied"), (4, "Phone Screen"), (10, "Rejected")]),

    ("Globex Corporation", "Data Analyst", date(2026, 5, 3),
     "https://globex.example.com/jobs/45", "Chicago, IL", "$75k-$90k", "Referral",
     [(0, "Applied"), (5, "Phone Screen")]),

    ("Initech", "Backend Developer", date(2026, 5, 5),
     "https://initech.example.com/jobs/9", "Austin, TX", "$110k-$140k", "Company Website",
     [(0, "Applied"), (3, "Phone Screen"), (9, "Interview")]),

    ("Umbrella Corp", "Python Developer", date(2026, 5, 10),
     "https://umbrella.example.com/careers/77", "Remote", "$95k-$120k", "Indeed",
     [(0, "Applied")]),

    ("Stark Industries", "ML Engineer", date(2026, 5, 12),
     "https://stark.example.com/jobs/1", "New York, NY", "$140k-$170k", "Referral",
     [(0, "Applied"), (3, "Phone Screen"), (10, "Interview"), (20, "Offer")]),

    ("Wayne Enterprises", "Data Engineer", date(2026, 5, 15),
     "https://wayne.example.com/careers/8", "Remote", "$120k-$145k", "LinkedIn",
     [(0, "Applied"), (7, "Rejected")]),

    ("Hooli", "Junior Developer", date(2026, 5, 18),
     "https://hooli.example.com/jobs/200", "Palo Alto, CA", "$90k-$105k", "Company Website",
     [(0, "Applied"), (2, "Withdrawn")]),

    ("Pied Piper", "Full Stack Engineer", date(2026, 5, 20),
     "https://piedpiper.example.com/careers/3", "Remote", "$105k-$130k", "Referral",
     [(0, "Applied"), (4, "Phone Screen"), (11, "Interview")]),

    ("Soylent Corp", "SQL Developer", date(2026, 5, 22),
     "https://soylent.example.com/jobs/14", "Detroit, MI", "$80k-$100k", "LinkedIn",
     [(0, "Applied")]),

    ("Massive Dynamic", "Data Scientist", date(2026, 5, 25),
     "https://massivedynamic.example.com/jobs/61", "Remote", "$125k-$155k", "Indeed",
     [(0, "Applied"), (6, "Phone Screen")]),

    ("Aperture Science", "Research Engineer", date(2026, 6, 1),
     "https://aperture.example.com/careers/42", "Remote", "$115k-$140k", "Company Website",
     [(0, "Applied"), (5, "Rejected")]),

    ("Cyberdyne Systems", "Software Engineer Intern", date(2026, 6, 5),
     "https://cyberdyne.example.com/jobs/5", "Remote", "$35/hr", "LinkedIn",
     [(0, "Applied")]),
]

ACTIVE_STATUSES = {"Applied", "Phone Screen", "Interview"}


def seed(conn) -> None:
    # Wipe existing data so this script can be re-run safely.
    # ON DELETE CASCADE (set up in schema.sql) removes matching
    # status_log rows automatically.
    conn.execute("DELETE FROM applications")
    conn.execute("DELETE FROM sqlite_sequence WHERE name IN ('applications', 'status_log')")
    conn.commit()

    for (company, position, date_applied, job_url, location,
         salary_range, source, history) in SAMPLE_DATA:

        final_status = history[-1][1]
        follow_up_date = None
        if final_status in ACTIVE_STATUSES:
            follow_up_date = (date_applied + timedelta(days=14)).isoformat()

        cur = conn.execute(
            """
            INSERT INTO applications (
                company, position, date_applied, status,
                job_url, location, salary_range, source, follow_up_date
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (company, position, date_applied.isoformat(), final_status,
             job_url, location, salary_range, source, follow_up_date),
        )
        application_id = cur.lastrowid

        old_status = None
        for days_after, status in history:
            changed_at = (date_applied + timedelta(days=days_after)).isoformat()
            conn.execute(
                """
                INSERT INTO status_log (application_id, old_status, new_status, changed_at)
                VALUES (?, ?, ?, ?)
                """,
                (application_id, old_status, status, changed_at),
            )
            old_status = status

    conn.commit()


if __name__ == "__main__":
    connection = db.get_connection()
    db.init_db(connection)
    seed(connection)
    count = connection.execute("SELECT COUNT(*) FROM applications").fetchone()[0]
    print(f"Seeded {count} sample applications into {db.DB_PATH.name}")
    connection.close()
