"""
Sync ISR updates from Google Sheets back into the local master database.

This script reads ISR-managed fields from the Google Sheet and writes them into:
- data/database/companies_master.csv
- data/database/contacts_master.csv

It also creates snapshot files:
- data/database/isr_company_updates.csv
- data/database/isr_contact_updates.csv
- data/database/isr_activity_log.csv

It does NOT call Apollo and does NOT consume Apollo credits.
"""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
from dotenv import load_dotenv

try:
    import gspread
except ImportError as exc:
    raise SystemExit(
        "Missing Google Sheets packages. Run: py -m pip install -r requirements-google.txt"
    ) from exc

load_dotenv()

BASE_DIR = Path(__file__).resolve().parents[1]
DATABASE_DIR = BASE_DIR / "data" / "database"
DATABASE_DIR.mkdir(parents=True, exist_ok=True)

COMPANIES_MASTER_FILE = DATABASE_DIR / "companies_master.csv"
CONTACTS_MASTER_FILE = DATABASE_DIR / "contacts_master.csv"

COMPANY_UPDATES_FILE = DATABASE_DIR / "isr_company_updates.csv"
CONTACT_UPDATES_FILE = DATABASE_DIR / "isr_contact_updates.csv"
ACTIVITY_LOG_FILE = DATABASE_DIR / "isr_activity_log.csv"

GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "config/google_credentials.json")
GOOGLE_SHEET_NAME = os.getenv("GOOGLE_SHEET_NAME", "Couno Prospect Intelligence Hub")
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "")

CALL_QUEUE_SHEET = "Weekly Call Queue"
CONTACTS_SHEET = "Marketing Contacts"
ACTIVITY_LOG_SHEET = "Activity Log"

COMPANY_ISR_COLUMNS = [
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


def normalise_domain(value: str) -> str:
    if pd.isna(value) or not str(value).strip():
        return ""
    value = str(value).strip().lower()
    if "@" in value and not value.startswith(("http://", "https://")):
        value = value.split("@")[-1]
    if not value.startswith(("http://", "https://")):
        value = "https://" + value
    parsed = urlparse(value)
    domain = parsed.netloc or parsed.path
    domain = domain.lower().strip()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain.strip("/")


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    return df.fillna("")


def read_csv_if_exists(path: Path) -> pd.DataFrame:
    if path.exists():
        return clean_dataframe(pd.read_csv(path))
    return pd.DataFrame()


def ensure_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    df = df.copy()
    for col in columns:
        if col not in df.columns:
            df[col] = ""
    return df


def worksheet_to_dataframe(spreadsheet, title: str) -> pd.DataFrame:
    try:
        ws = spreadsheet.worksheet(title)
    except gspread.WorksheetNotFound:
        print(f"Worksheet not found, skipping: {title}")
        return pd.DataFrame()

    values = ws.get_all_values()
    if not values:
        return pd.DataFrame()
    headers = [str(h).strip() for h in values[0]]
    rows = values[1:]
    df = pd.DataFrame(rows, columns=headers)
    return clean_dataframe(df)


def open_spreadsheet():
    credentials_path = BASE_DIR / GOOGLE_CREDENTIALS_FILE
    if not credentials_path.exists():
        raise FileNotFoundError(f"Google credentials file not found: {credentials_path}")

    gc = gspread.service_account(filename=str(credentials_path))
    if GOOGLE_SHEET_ID:
        return gc.open_by_key(GOOGLE_SHEET_ID)
    return gc.open(GOOGLE_SHEET_NAME)


def prepare_company_updates(call_queue: pd.DataFrame) -> pd.DataFrame:
    if call_queue.empty:
        return pd.DataFrame()

    call_queue = ensure_columns(call_queue, ["Company", "Website", "Record Key"] + COMPANY_ISR_COLUMNS)
    updates = call_queue[["Record Key", "Company", "Website"] + COMPANY_ISR_COLUMNS].copy()
    updates["Company Key"] = updates["Website"].apply(normalise_domain)
    updates["Last ISR Sync"] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
    return updates.drop_duplicates(subset=["Company Key"], keep="last")


def prepare_contact_updates(contacts: pd.DataFrame) -> pd.DataFrame:
    if contacts.empty:
        return pd.DataFrame()

    contacts = ensure_columns(contacts, ["Record Key", "Email", "Contact Name", "Company"] + CONTACT_ISR_COLUMNS)
    updates = contacts[["Record Key", "Email", "Contact Name", "Company"] + CONTACT_ISR_COLUMNS].copy()
    updates["Contact Key"] = "email:" + updates["Email"].astype(str).str.lower().str.strip()
    updates.loc[updates["Email"].astype(str).str.strip().eq(""), "Contact Key"] = ""
    updates["Last ISR Sync"] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
    return updates[updates["Contact Key"].ne("")].drop_duplicates(subset=["Contact Key"], keep="last")


def merge_company_updates(master: pd.DataFrame, updates: pd.DataFrame) -> pd.DataFrame:
    if master.empty or updates.empty:
        return master

    master = ensure_columns(
        master,
        [
            "Company Key",
            "Company Owner",
            "ISR Status",
            "Last Contacted",
            "Next Action Date",
            "Next Action",
            "Company Notes",
            "Last ISR Sync",
        ],
    )

    updates_by_key = updates.set_index("Company Key", drop=False)
    for idx, row in master.iterrows():
        key = str(row.get("Company Key", "")).strip()
        if not key or key not in updates_by_key.index:
            continue
        update = updates_by_key.loc[key]
        if isinstance(update, pd.DataFrame):
            update = update.iloc[-1]

        master.at[idx, "Company Owner"] = update.get("Assigned To", "")
        master.at[idx, "ISR Status"] = update.get("ISR Status", "")
        master.at[idx, "Last Contacted"] = update.get("Last Contacted", "")
        master.at[idx, "Next Action Date"] = update.get("Next Action Date", "")
        master.at[idx, "Next Action"] = update.get("Next Action", "")
        master.at[idx, "Company Notes"] = update.get("Notes", "")
        master.at[idx, "Last ISR Sync"] = update.get("Last ISR Sync", "")

    return master


def merge_contact_updates(master: pd.DataFrame, updates: pd.DataFrame) -> pd.DataFrame:
    if master.empty or updates.empty:
        return master

    master = ensure_columns(
        master,
        [
            "Contact Key",
            "Marketing Status",
            "Last Email Sent",
            "Reply Status",
            "Notes",
            "Last ISR Sync",
        ],
    )

    updates_by_key = updates.set_index("Contact Key", drop=False)
    for idx, row in master.iterrows():
        key = str(row.get("Contact Key", "")).strip()
        if not key or key not in updates_by_key.index:
            continue
        update = updates_by_key.loc[key]
        if isinstance(update, pd.DataFrame):
            update = update.iloc[-1]

        master.at[idx, "Marketing Status"] = update.get("Contact Status", "")
        master.at[idx, "Last Email Sent"] = update.get("Last Email Sent", "")
        master.at[idx, "Reply Status"] = update.get("Reply Status", "")
        master.at[idx, "Notes"] = update.get("Notes", "")
        master.at[idx, "Last ISR Sync"] = update.get("Last ISR Sync", "")

    return master


def main() -> None:
    sh = open_spreadsheet()

    call_queue = worksheet_to_dataframe(sh, CALL_QUEUE_SHEET)
    contacts = worksheet_to_dataframe(sh, CONTACTS_SHEET)
    activity_log = worksheet_to_dataframe(sh, ACTIVITY_LOG_SHEET)

    company_updates = prepare_company_updates(call_queue)
    contact_updates = prepare_contact_updates(contacts)

    company_updates.to_csv(COMPANY_UPDATES_FILE, index=False)
    contact_updates.to_csv(CONTACT_UPDATES_FILE, index=False)
    activity_log.to_csv(ACTIVITY_LOG_FILE, index=False)

    companies_master = read_csv_if_exists(COMPANIES_MASTER_FILE)
    contacts_master = read_csv_if_exists(CONTACTS_MASTER_FILE)

    companies_master = merge_company_updates(companies_master, company_updates)
    contacts_master = merge_contact_updates(contacts_master, contact_updates)

    if not companies_master.empty:
        companies_master.to_csv(COMPANIES_MASTER_FILE, index=False)
    if not contacts_master.empty:
        contacts_master.to_csv(CONTACTS_MASTER_FILE, index=False)

    print("Finished Google Sheets pull-back sync.")
    print(f"Company ISR updates pulled: {len(company_updates)}")
    print(f"Contact ISR updates pulled: {len(contact_updates)}")
    print(f"Activity log rows pulled: {len(activity_log)}")
    print("Updated files:")
    print(COMPANIES_MASTER_FILE)
    print(CONTACTS_MASTER_FILE)
    print("Snapshot files:")
    print(COMPANY_UPDATES_FILE)
    print(CONTACT_UPDATES_FILE)
    print(ACTIVITY_LOG_FILE)
    print("No Apollo calls were made.")


if __name__ == "__main__":
    main()
