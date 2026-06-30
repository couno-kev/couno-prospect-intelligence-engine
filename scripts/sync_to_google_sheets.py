"""
Sync Couno Prospect Intelligence Engine outputs to Google Sheets.

This script writes engine-controlled data into a Google Sheet while preserving
ISR-managed columns such as Status, Assigned To, Notes and Next Action Date.

It does NOT call Apollo and does NOT consume Apollo credits.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List

import pandas as pd
from dotenv import load_dotenv

try:
    import gspread
    from gspread.utils import rowcol_to_a1
except ImportError as exc:
    raise SystemExit(
        "Missing Google Sheets packages. Run: py -m pip install -r requirements-google.txt"
    ) from exc

load_dotenv()

BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = BASE_DIR / "data" / "output"

GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "google_service_account.json")
GOOGLE_SHEET_NAME = os.getenv("GOOGLE_SHEET_NAME", "Couno Prospect Intelligence Hub")

# Engine source files
MARKETING_FILE = OUTPUT_DIR / "marketing_campaign_from_master.csv"
CALL_QUEUE_FILE = OUTPUT_DIR / "weekly_call_queue_from_master.csv"
MANUAL_REVIEW_FILE = OUTPUT_DIR / "manual_review_dashboard.csv"

# ISR-owned columns are preserved during sync.
CALL_QUEUE_ISR_COLUMNS = [
    "Assigned To",
    "ISR Status",
    "Last Contacted",
    "Next Action Date",
    "Next Action",
    "Notes",
]

CONTACT_ISR_COLUMNS = [
    "Contact Status",
    "Last Email Sent",
    "Reply Status",
    "Notes",
]

DEFAULT_CALL_STATUS = "Not Started"
DEFAULT_CONTACT_STATUS = "Not Started"

STATUS_VALUES = [
    "Not Started",
    "Attempt 1",
    "Attempt 2",
    "Attempt 3",
    "Connected",
    "Meeting Booked",
    "Nurture",
    "Not Interested",
    "Bad Data",
]

REPLY_VALUES = [
    "No Reply",
    "Positive Reply",
    "Neutral Reply",
    "Negative Reply",
    "Bounce",
    "Unsubscribed",
]


def normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    return df.fillna("")


def pick_column(df: pd.DataFrame, candidates: List[str], fallback: str = "") -> pd.Series:
    for col in candidates:
        if col in df.columns:
            return df[col].astype(str).fillna("")
    return pd.Series([fallback] * len(df))


def make_contact_name(df: pd.DataFrame) -> pd.Series:
    if "Contact Name" in df.columns:
        return df["Contact Name"].astype(str)
    first = pick_column(df, ["First Name", "first_name", "first_name"])
    last = pick_column(df, ["Last Name", "last_name", "last_name"])
    return (first + " " + last).str.strip()


def read_existing_records(worksheet) -> Dict[str, Dict[str, str]]:
    records = worksheet.get_all_records()
    existing = {}
    for row in records:
        key = str(row.get("Record Key", "")).strip().lower()
        if key:
            existing[key] = row
    return existing


def merge_isr_columns(df: pd.DataFrame, existing: Dict[str, Dict[str, str]], isr_columns: List[str]) -> pd.DataFrame:
    df = df.copy()
    for col in isr_columns:
        if col not in df.columns:
            df[col] = ""

    for idx, row in df.iterrows():
        key = str(row.get("Record Key", "")).strip().lower()
        previous = existing.get(key, {})
        for col in isr_columns:
            previous_value = previous.get(col, "")
            if previous_value not in (None, ""):
                df.at[idx, col] = previous_value

    if "ISR Status" in df.columns:
        df["ISR Status"] = df["ISR Status"].replace("", DEFAULT_CALL_STATUS)
    if "Contact Status" in df.columns:
        df["Contact Status"] = df["Contact Status"].replace("", DEFAULT_CONTACT_STATUS)
    if "Reply Status" in df.columns:
        df["Reply Status"] = df["Reply Status"].replace("", "No Reply")

    return df


def get_or_create_worksheet(spreadsheet, title: str, rows: int = 1000, cols: int = 30):
    try:
        return spreadsheet.worksheet(title)
    except gspread.WorksheetNotFound:
        return spreadsheet.add_worksheet(title=title, rows=rows, cols=cols)


def set_dataframe(worksheet, df: pd.DataFrame) -> None:
    worksheet.clear()
    values = [df.columns.tolist()] + df.astype(str).values.tolist()
    if not values:
        return
    end_cell = rowcol_to_a1(len(values), len(values[0]))
    worksheet.update(f"A1:{end_cell}", values)
    worksheet.freeze(rows=1)

    # Basic header formatting and filter.
    worksheet.format(
        "1:1",
        {
            "textFormat": {"bold": True},
            "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9},
        },
    )
    try:
        worksheet.set_basic_filter()
    except Exception:
        pass


def add_dropdown(worksheet, column_name: str, values: List[str]) -> None:
    headers = worksheet.row_values(1)
    if column_name not in headers:
        return
    col_index = headers.index(column_name) + 1
    col_letter = rowcol_to_a1(1, col_index).rstrip("1")
    cell_range = f"{col_letter}2:{col_letter}1000"
    try:
        worksheet.add_validation(
            cell_range,
            gspread.ValidationConditionType.one_of_list,
            values,
            strict=False,
            showCustomUi=True,
        )
    except Exception:
        # Some gspread versions/environments may not support validation helpers.
        pass


def build_dashboard(companies_count: int, contacts_count: int, marketing_ready: int, queued_companies: int, review_count: int) -> pd.DataFrame:
    return pd.DataFrame(
        [
            ["Companies in Master Database", companies_count],
            ["Contacts in Master Database", contacts_count],
            ["Marketing Ready Contacts", marketing_ready],
            ["Companies in Weekly Queue", queued_companies],
            ["Manual Review Records", review_count],
            ["Last Sync", pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")],
        ],
        columns=["Metric", "Value"],
    )


def build_call_queue() -> pd.DataFrame:
    if not CALL_QUEUE_FILE.exists():
        raise FileNotFoundError(f"Missing call queue file: {CALL_QUEUE_FILE}")

    df = normalise_columns(pd.read_csv(CALL_QUEUE_FILE))
    company = pick_column(df, ["Company", "Company Name", "company"])
    website = pick_column(df, ["Website", "Company Website", "website", "Domain"])

    out = pd.DataFrame()
    out["Record Key"] = (company + "|" + website).str.lower().str.strip()
    out["Company"] = company
    out["Website"] = website
    out["Couno Fit Tier"] = pick_column(df, ["Couno Fit Tier", "Fit Tier"])
    out["Couno Fit Score"] = pick_column(df, ["Couno Fit Score", "Fit Score"])
    out["Week Batch"] = pick_column(df, ["Week Batch", "Weekly Batch", "Batch"])
    out["Contacts Available"] = pick_column(df, ["Contacts Available", "Contact Count", "Contacts"])
    out["Primary Contact"] = pick_column(df, ["Primary Contact", "Contact Name"])
    out["Primary Title"] = pick_column(df, ["Primary Title", "Title"])
    out["Primary Email"] = pick_column(df, ["Primary Email", "Email"])

    for col in CALL_QUEUE_ISR_COLUMNS:
        out[col] = ""
    out["ISR Status"] = DEFAULT_CALL_STATUS

    return out.drop_duplicates(subset=["Record Key"], keep="first")


def build_marketing_contacts() -> pd.DataFrame:
    if not MARKETING_FILE.exists():
        raise FileNotFoundError(f"Missing marketing file: {MARKETING_FILE}")

    df = normalise_columns(pd.read_csv(MARKETING_FILE))
    email = pick_column(df, ["Email", "email"])
    company = pick_column(df, ["Company", "Company Name", "company"])
    contact = make_contact_name(df)

    out = pd.DataFrame()
    out["Record Key"] = email.str.lower().str.strip()
    out["Contact Name"] = contact
    out["First Name"] = pick_column(df, ["First Name", "first_name"])
    out["Last Name"] = pick_column(df, ["Last Name", "last_name"])
    out["Company"] = company
    out["Title"] = pick_column(df, ["Title", "Job Title", "title"])
    out["Email"] = email
    out["LinkedIn URL"] = pick_column(df, ["LinkedIn URL", "LinkedIn", "linkedin_url"])
    out["Website"] = pick_column(df, ["Website", "Company Website", "website", "Domain"])
    out["Couno Fit Tier"] = pick_column(df, ["Couno Fit Tier", "Fit Tier"])
    out["Couno Fit Score"] = pick_column(df, ["Couno Fit Score", "Fit Score"])
    out["Employment Validation Status"] = pick_column(df, ["Employment Validation Status"])
    out["LinkedIn Validation Status"] = pick_column(df, ["LinkedIn Validation Status"])

    for col in CONTACT_ISR_COLUMNS:
        out[col] = ""
    out["Contact Status"] = DEFAULT_CONTACT_STATUS
    out["Reply Status"] = "No Reply"

    return out.drop_duplicates(subset=["Record Key"], keep="first")


def build_manual_review() -> pd.DataFrame:
    if MANUAL_REVIEW_FILE.exists():
        return normalise_columns(pd.read_csv(MANUAL_REVIEW_FILE))
    return pd.DataFrame(columns=["No manual review file found"])


def main() -> None:
    credentials_path = BASE_DIR / GOOGLE_CREDENTIALS_FILE
    if not credentials_path.exists():
        raise FileNotFoundError(
            f"Google service account file not found: {credentials_path}\n"
            "Add GOOGLE_CREDENTIALS_FILE=your_json_file_name.json to .env if using a different file name."
        )

    gc = gspread.service_account(filename=str(credentials_path))

    try:
        sh = gc.open(GOOGLE_SHEET_NAME)
    except gspread.SpreadsheetNotFound as exc:
        raise SystemExit(
            f"Google Sheet not found: {GOOGLE_SHEET_NAME}\n"
            "Create the sheet first, then share it with the service account client_email."
        ) from exc

    companies_master = BASE_DIR / "data" / "database" / "companies_master.csv"
    contacts_master = BASE_DIR / "data" / "database" / "contacts_master.csv"
    companies_count = len(pd.read_csv(companies_master)) if companies_master.exists() else 0
    contacts_count = len(pd.read_csv(contacts_master)) if contacts_master.exists() else 0

    call_queue = build_call_queue()
    contacts = build_marketing_contacts()
    manual_review = build_manual_review()
    dashboard = build_dashboard(
        companies_count=companies_count,
        contacts_count=contacts_count,
        marketing_ready=len(contacts),
        queued_companies=len(call_queue),
        review_count=len(manual_review),
    )

    dashboard_ws = get_or_create_worksheet(sh, "Dashboard", rows=50, cols=10)
    call_ws = get_or_create_worksheet(sh, "Weekly Call Queue", rows=max(len(call_queue) + 10, 100), cols=30)
    contacts_ws = get_or_create_worksheet(sh, "Marketing Contacts", rows=max(len(contacts) + 10, 300), cols=30)
    review_ws = get_or_create_worksheet(sh, "Manual Review", rows=max(len(manual_review) + 10, 100), cols=30)
    log_ws = get_or_create_worksheet(sh, "Activity Log", rows=1000, cols=10)
    settings_ws = get_or_create_worksheet(sh, "Settings", rows=100, cols=10)

    # Preserve ISR edits before overwriting engine-controlled sheets.
    call_existing = read_existing_records(call_ws)
    contacts_existing = read_existing_records(contacts_ws)
    call_queue = merge_isr_columns(call_queue, call_existing, CALL_QUEUE_ISR_COLUMNS)
    contacts = merge_isr_columns(contacts, contacts_existing, CONTACT_ISR_COLUMNS)

    set_dataframe(dashboard_ws, dashboard)
    set_dataframe(call_ws, call_queue)
    set_dataframe(contacts_ws, contacts)
    set_dataframe(review_ws, manual_review)

    if not log_ws.get_all_values():
        set_dataframe(log_ws, pd.DataFrame(columns=["Date", "User", "Company", "Action", "Notes"]))

    settings = pd.DataFrame(
        {
            "Setting": ["ISR Status Values", "Reply Status Values"],
            "Values": [", ".join(STATUS_VALUES), ", ".join(REPLY_VALUES)],
        }
    )
    set_dataframe(settings_ws, settings)

    add_dropdown(call_ws, "ISR Status", STATUS_VALUES)
    add_dropdown(contacts_ws, "Contact Status", STATUS_VALUES)
    add_dropdown(contacts_ws, "Reply Status", REPLY_VALUES)

    print("Finished Google Sheets sync.")
    print(f"Sheet updated: {GOOGLE_SHEET_NAME}")
    print(f"Weekly Call Queue rows: {len(call_queue)}")
    print(f"Marketing Contact rows: {len(contacts)}")
    print(f"Manual Review rows: {len(manual_review)}")
    print("ISR columns preserved where matching Record Key values already existed.")


if __name__ == "__main__":
    main()
