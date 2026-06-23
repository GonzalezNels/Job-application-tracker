"""
cli.py
------
A small interactive menu for the Job Application Tracker.

Run it with:
    python cli.py

This file is the "user interface" layer - it only handles input()/print()
and calls into db.py for anything that touches the database. Keeping
that separation (UI vs. data access) is a habit worth keeping as you
build bigger Python projects.
"""

import db

MENU = """
==================== Job Application Tracker ====================
1. Add a new application
2. Update an application's status
3. List all applications
4. List applications by status
5. Search applications (company / position / notes)
6. View one application + its status history
7. Show stats
8. Delete an application
9. Follow-ups due (overdue + next 7 days)
10. Edit an application
0. Quit
====================================================================
"""


def print_table(rows: list[dict], columns: list[str]) -> None:
    """Print a list of dicts as a simple fixed-width table.

    No external libraries (like 'tabulate') on purpose - this is all
    just Python string formatting, so it's worth reading even if it's
    not the prettiest table you've ever seen.
    """
    if not rows:
        print("(no results)")
        return

    widths = {
        col: max(len(col), *(len(str(row.get(col, ""))) for row in rows))
        for col in columns
    }

    header = " | ".join(col.ljust(widths[col]) for col in columns)
    print(header)
    print("-" * len(header))
    for row in rows:
        print(" | ".join(str(row.get(col, "")).ljust(widths[col]) for col in columns))


def prompt(label: str, required: bool = True) -> str:
    while True:
        value = input(f"{label}: ").strip()
        if value or not required:
            return value
        print("  (required, try again)")


def action_add(conn) -> None:
    print("\n-- Add application --")
    company = prompt("Company")
    position = prompt("Position")
    date_applied = prompt("Date applied (YYYY-MM-DD, blank = today)", required=False) or None
    job_url = prompt("Job URL", required=False) or None
    location = prompt("Location", required=False) or None
    salary_range = prompt("Salary range", required=False) or None
    source = prompt("Source (LinkedIn, Referral, etc.)", required=False) or None
    notes = prompt("Notes", required=False) or None
    follow_up_date = prompt("Follow-up date (YYYY-MM-DD)", required=False) or None

    new_id = db.add_application(
        conn, company, position, date_applied=date_applied,
        job_url=job_url, location=location, salary_range=salary_range,
        source=source, notes=notes, follow_up_date=follow_up_date,
    )
    print(f"Added application #{new_id}.")


def action_update_status(conn) -> None:
    print("\n-- Update status --")
    try:
        app_id = int(prompt("Application id"))
    except ValueError:
        print("That's not a number.")
        return

    current = db.get_application(conn, app_id)
    if not current:
        print(f"No application with id {app_id}.")
        return

    print(f"Current status: {current['status']}")
    print(f"Valid statuses: {', '.join(db.VALID_STATUSES)}")
    new_status = prompt("New status")

    if db.update_status(conn, app_id, new_status):
        print("Updated.")
    else:
        print("Could not update - check the status spelling.")


def action_list_all(conn) -> None:
    rows = db.list_applications(conn)
    print_table(rows, ["id", "company", "position", "status", "date_applied", "follow_up_date", "job_url"])


def action_list_by_status(conn) -> None:
    print(f"Valid statuses: {', '.join(db.VALID_STATUSES)}")
    status = prompt("Status")
    rows = db.list_applications(conn, status=status)
    print_table(rows, ["id", "company", "position", "status", "date_applied", "follow_up_date", "job_url"])


def action_search(conn) -> None:
    keyword = prompt("Search for")
    rows = db.search_applications(conn, keyword)
    print_table(rows, ["id", "company", "position", "status", "date_applied"])


def action_view(conn) -> None:
    try:
        app_id = int(prompt("Application id"))
    except ValueError:
        print("That's not a number.")
        return

    app = db.get_application(conn, app_id)
    if not app:
        print(f"No application with id {app_id}.")
        return

    print("\n-- Application details --")
    for key, value in app.items():
        print(f"  {key}: {value}")

    print("\n-- Status history --")
    history = db.get_status_history(conn, app_id)
    print_table(history, ["changed_at", "old_status", "new_status"])


def action_stats(conn) -> None:
    stats = db.get_stats(conn)
    print("\n-- Stats --")
    print(f"Total applications: {stats['total']}")
    print(f"Response rate (Phone Screen or further): {stats['response_rate_pct']}%")
    print("By status:")
    for status, count in stats["by_status"].items():
        print(f"  {status}: {count}")


def action_delete(conn) -> None:
    try:
        app_id = int(prompt("Application id to delete"))
    except ValueError:
        print("That's not a number.")
        return

    confirm = prompt(f"Type 'yes' to confirm deleting application #{app_id}")
    if confirm.lower() != "yes":
        print("Cancelled.")
        return

    if db.delete_application(conn, app_id):
        print("Deleted.")
    else:
        print(f"No application with id {app_id}.")


def action_followups(conn) -> None:
    rows = db.get_due_followups(conn)
    if not rows:
        print("No follow-ups due in the next 7 days.")
        return
    print_table(rows, ["id", "company", "position", "status", "follow_up_date", "job_url"])


def action_edit(conn) -> None:
    print("\n-- Edit application --")
    try:
        app_id = int(prompt("Application id"))
    except ValueError:
        print("That's not a number.")
        return

    app = db.get_application(conn, app_id)
    if not app:
        print(f"No application with id {app_id}.")
        return

    print("Leave a field blank to keep the current value.")
    fields = {}
    for col in ("company", "position", "date_applied", "job_url", "location",
                "salary_range", "source", "notes", "follow_up_date"):
        current = app.get(col) or ""
        new_val = input(f"  {col} [{current}]: ").strip()
        if new_val:
            fields[col] = new_val

    if fields:
        db.update_application(conn, app_id, **fields)
        print("Updated.")
    else:
        print("No changes made.")


ACTIONS = {
    "1": action_add,
    "2": action_update_status,
    "3": action_list_all,
    "4": action_list_by_status,
    "5": action_search,
    "6": action_view,
    "7": action_stats,
    "8": action_delete,
    "9": action_followups,
    "10": action_edit,
}


def main() -> None:
    conn = db.get_connection()
    db.init_db(conn)

    while True:
        print(MENU)
        choice = input("Choose an option: ").strip()

        if choice == "0":
            print("Goodbye - good luck out there.")
            break

        action = ACTIONS.get(choice)
        if action is None:
            print("Not a valid option, try again.")
            continue

        try:
            action(conn)
        except Exception as exc:  # keep the menu loop alive on bad input
            print(f"Something went wrong: {exc}")

    conn.close()


if __name__ == "__main__":
    main()
