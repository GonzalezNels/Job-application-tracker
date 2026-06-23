"""
gmail_sync.py
-------------
Scans your Gmail for job-related emails and automatically updates
job_applications.db to match.

How it works:
  1. Searches Gmail for emails that look like application updates.
  2. Tries to match each email to an existing application by company name.
  3. Classifies the email as a status change (Applied, Phone Screen,
     Interview, Offer, Rejected, Withdrawn).
  4. Updates the DB if the detected status is different from current.
  5. Saves processed Gmail message IDs to processed_emails.json so
     re-running never double-counts the same email.

Run it with:
    python gmail_sync.py

First-time setup (one-time only):
  1. Go to https://console.cloud.google.com/
  2. Create a project → Enable the Gmail API.
  3. Create OAuth 2.0 credentials (Desktop app) → download credentials.json
     and place it in this folder.
  4. Install dependencies:
         pip install google-api-python-client google-auth-oauthlib
  5. Run the script — a browser window will open for you to log in.
     After approving, token.json is saved and future runs skip the login.
"""

import json
import re
from pathlib import Path
from datetime import datetime, timedelta, timezone

# Gmail API
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

import db

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).parent
CREDENTIALS_FILE = BASE_DIR / "credentials.json"
TOKEN_FILE = BASE_DIR / "token.json"
PROCESSED_FILE = BASE_DIR / "processed_emails.json"

# Only need read access to Gmail.
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# How far back to look on each run (days).
LOOKBACK_DAYS = 30

# ---------------------------------------------------------------------------
# Gmail authentication
# ---------------------------------------------------------------------------

def get_gmail_service():
    """Authenticate and return a Gmail API service object.

    On the first run this opens a browser for OAuth consent.
    After that, token.json is refreshed automatically.
    """
    creds = None

    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_FILE.exists():
                raise FileNotFoundError(
                    "credentials.json not found. "
                    "Download it from Google Cloud Console and place it here."
                )
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        TOKEN_FILE.write_text(creds.to_json())

    return build("gmail", "v1", credentials=creds)


# ---------------------------------------------------------------------------
# Processed-email tracking
# ---------------------------------------------------------------------------

def load_processed_ids() -> set[str]:
    if PROCESSED_FILE.exists():
        return set(json.loads(PROCESSED_FILE.read_text()))
    return set()


def save_processed_ids(ids: set[str]) -> None:
    PROCESSED_FILE.write_text(json.dumps(sorted(ids), indent=2))


# ---------------------------------------------------------------------------
# Gmail search
# ---------------------------------------------------------------------------

# Gmail query that catches the most common recruiting email patterns.
GMAIL_QUERY = (
    "subject:(application OR applied OR interview OR "
    "\"phone screen\" OR offer OR rejection OR \"next steps\" OR "
    "\"not moving forward\" OR \"thank you for applying\" OR "
    "\"we received your\" OR \"unfortunately\" OR \"moving forward\")"
)


def fetch_recent_messages(service, lookback_days: int = LOOKBACK_DAYS) -> list[dict]:
    """Return a list of raw Gmail message dicts from the past lookback_days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    after = cutoff.strftime("%Y/%m/%d")
    query = f"{GMAIL_QUERY} after:{after}"

    results = service.users().messages().list(
        userId="me", q=query, maxResults=100
    ).execute()

    messages = results.get("messages", [])

    # Fetch full metadata for each message.
    full = []
    for msg in messages:
        detail = service.users().messages().get(
            userId="me", id=msg["id"], format="metadata",
            metadataHeaders=["Subject", "From", "Date"],
        ).execute()
        full.append(detail)

    return full


# ---------------------------------------------------------------------------
# Status classification
# ---------------------------------------------------------------------------

# Each tuple: (regex pattern, status to assign).
# Patterns are checked in order — first match wins.
STATUS_PATTERNS = [
    # Offer (job-specific — avoids retail/promo "offer" emails)
    (r"job offer|employment offer|offer of employment|pleased to offer|welcome aboard|congratulations.*position|we.d like to offer you", "Offer"),

    # Rejection
    (
        r"not move forward|not moving forward|not selected|"
        r"decided (not|to pursue other)|unfortunately|"
        r"we regret|position has been filled|will not be",
        "Rejected",
    ),

    # Interview
    (
        r"interview|schedule (a |your )?(call|meeting|time)|"
        r"video (call|interview)|on-?site|technical (round|interview)",
        "Interview",
    ),

    # Phone screen
    (r"phone screen|phone interview|recruiter call|introductory call", "Phone Screen"),

    # Application confirmed
    (
        r"received your (application|resume)|application (received|confirmed)|"
        r"thank you for (applying|your application)|we got your application",
        "Applied",
    ),
]


def classify_email(subject: str, snippet: str) -> str | None:
    """Return the detected status, or None if the email isn't job-related."""
    text = f"{subject} {snippet}".lower()
    for pattern, status in STATUS_PATTERNS:
        if re.search(pattern, text):
            return status
    return None


# ---------------------------------------------------------------------------
# Company matching
# ---------------------------------------------------------------------------

def normalize(name: str) -> str:
    """Lowercase and strip common noise words for fuzzy matching."""
    noise = r"\b(inc|llc|corp|ltd|co|company|technologies|solutions|group|the)\b"
    name = name.lower()
    name = re.sub(noise, "", name)
    name = re.sub(r"[^a-z0-9 ]", " ", name)
    return " ".join(name.split())


def extract_company_from_sender(sender: str) -> str:
    """Pull the display name from a 'Name <email>' sender string."""
    match = re.match(r'^"?([^"<]+)"?\s*<', sender)
    if match:
        return match.group(1).strip()
    # Fall back to the domain part of the email address.
    email_match = re.search(r"@([\w.-]+)", sender)
    if email_match:
        domain = email_match.group(1)
        # Drop TLD and split on dots/dashes for a rough company name.
        parts = re.split(r"[.\-]", domain)
        return parts[0] if parts else domain
    return sender


def find_matching_application(conn, company_hint: str) -> dict | None:
    """Return the best-matching application row, or None."""
    hint_norm = normalize(company_hint)
    if not hint_norm:
        return None

    applications = db.list_applications(conn)
    for app in applications:
        if normalize(app["company"]) in hint_norm or hint_norm in normalize(app["company"]):
            return app

    return None


# ---------------------------------------------------------------------------
# Header helpers
# ---------------------------------------------------------------------------

def get_header(message: dict, name: str) -> str:
    for header in message.get("payload", {}).get("headers", []):
        if header["name"].lower() == name.lower():
            return header["value"]
    return ""


# ---------------------------------------------------------------------------
# Main sync logic
# ---------------------------------------------------------------------------

def sync(conn, service) -> None:
    processed = load_processed_ids()
    messages = fetch_recent_messages(service)

    updated = 0
    skipped_already_processed = 0
    skipped_no_match = 0
    skipped_no_status = 0
    skipped_same_status = 0

    for msg in messages:
        msg_id = msg["id"]

        if msg_id in processed:
            skipped_already_processed += 1
            continue

        subject = get_header(msg, "Subject")
        sender = get_header(msg, "From")
        snippet = msg.get("snippet", "")

        detected_status = classify_email(subject, snippet)
        if not detected_status:
            processed.add(msg_id)
            skipped_no_status += 1
            continue

        company_hint = extract_company_from_sender(sender)
        app = find_matching_application(conn, company_hint)

        # Also try matching from the subject line if sender didn't help.
        if not app:
            app = find_matching_application(conn, subject)

        if not app:
            print(
                f"  [no match] {subject[:60]!r} "
                f"(sender: {company_hint!r}, status would be: {detected_status})"
            )
            processed.add(msg_id)
            skipped_no_match += 1
            continue

        if app["status"] == detected_status:
            processed.add(msg_id)
            skipped_same_status += 1
            continue

        # Status precedence: don't downgrade (e.g., don't go Interview → Applied).
        STATUS_RANK = {s: i for i, s in enumerate(db.VALID_STATUSES)}
        current_rank = STATUS_RANK.get(app["status"], 0)
        new_rank = STATUS_RANK.get(detected_status, 0)
        if new_rank <= current_rank and detected_status != "Rejected":
            processed.add(msg_id)
            skipped_same_status += 1
            continue

        print(
            f"  [update] {app['company']} — {app['status']} → {detected_status}\n"
            f"           Email: {subject[:70]!r}"
        )
        db.update_status(conn, app["id"], detected_status)
        processed.add(msg_id)
        updated += 1

    save_processed_ids(processed)

    print(f"\nDone. {updated} updated, "
          f"{skipped_no_match} unmatched, "
          f"{skipped_same_status} already current, "
          f"{skipped_already_processed} previously processed.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Connecting to Gmail...")
    try:
        service = get_gmail_service()
    except FileNotFoundError as e:
        print(f"\nSetup required: {e}")
        print("\nSteps:")
        print("  1. Go to https://console.cloud.google.com/")
        print("  2. Create a project → APIs & Services → Enable Gmail API")
        print("  3. Credentials → Create → OAuth 2.0 Client ID (Desktop app)")
        print("  4. Download credentials.json → place it in this folder")
        print("  5. pip install google-api-python-client google-auth-oauthlib")
        print("  6. Re-run this script")
        raise SystemExit(1)

    conn = db.get_connection()
    db.init_db(conn)

    print(f"Scanning emails from the last {LOOKBACK_DAYS} days...\n")
    sync(conn, service)
    conn.close()
