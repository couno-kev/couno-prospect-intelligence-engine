from pathlib import Path
from urllib.parse import urlparse
import re

import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = BASE_DIR / "data" / "output"
DATABASE_DIR = BASE_DIR / "data" / "database"
DATABASE_DIR.mkdir(parents=True, exist_ok=True)

COMPANIES_MASTER_FILE = DATABASE_DIR / "companies_master.csv"
CONTACTS_MASTER_FILE = DATABASE_DIR / "contacts_master.csv"

QUALIFIED_COMPANIES_FILE = OUTPUT_DIR / "qualified_companies.csv"
ENRICHED_CONTACTS_FILE = OUTPUT_DIR / "company_people_enriched.csv"
SCORED_PROSPECTS_FILE = OUTPUT_DIR / "couno_scored_prospects.csv"
LINKEDIN_VALIDATED_FILE = OUTPUT_DIR / "linkedin_validated_prospects.csv"
MARKETING_CAMPAIGN_FILE = OUTPUT_DIR / "marketing_campaign.csv"

TODAY = pd.Timestamp.today().date().isoformat()


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
    domain = domain.replace("www.", "", 1)
    return domain.strip("/")


def normalise_text(value: str) -> str:
    if pd.isna(value):
        return ""
    value = str(value).lower().strip()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def read_csv_if_exists(path: Path) -> pd.DataFrame:
    if path.exists():
        return pd.read_csv(path)
    return pd.DataFrame()


def choose_contact_source() -> tuple[pd.DataFrame, str]:
    for path, label in [
        (SCORED_PROSPECTS_FILE, "couno_scored_prospects.csv"),
        (LINKEDIN_VALIDATED_FILE, "linkedin_validated_prospects.csv"),
        (MARKETING_CAMPAIGN_FILE, "marketing_campaign.csv"),
        (ENRICHED_CONTACTS_FILE, "company_people_enriched.csv"),
    ]:
        if path.exists():
            return pd.read_csv(path), label
    return pd.DataFrame(), "No contact source found"


def ensure_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for column in columns:
        if column not in df.columns:
            df[column] = ""
    return df


def build_company_key(row: pd.Series) -> str:
    domain = normalise_domain(row.get("Domain", "") or row.get("Website", ""))
    if domain:
        return domain
    return "name:" + normalise_text(row.get("Company Name", ""))


def build_contact_key(row: pd.Series) -> str:
    email = str(row.get("Email", "") or "").lower().strip()
    if email and email != "nan":
        return "email:" + email
    apollo_id = str(row.get("Apollo Person ID", "") or "").strip()
    if apollo_id and apollo_id.lower() != "nan":
        return "apollo:" + apollo_id
    full_name = normalise_text(row.get("Full Name", ""))
    company_key = str(row.get("Company Key", "") or build_company_key(row))
    return "name_company:" + full_name + "|" + company_key


def merge_master(existing: pd.DataFrame, incoming: pd.DataFrame, key_column: str, preserve_columns: list[str]) -> pd.DataFrame:
    existing = ensure_columns(existing, [key_column, "First Seen", "Last Seen", "Record Status"] + preserve_columns)
    incoming = ensure_columns(incoming, [key_column, "First Seen", "Last Seen", "Record Status"] + preserve_columns)

    if existing.empty:
        incoming["First Seen"] = incoming["First Seen"].replace("", TODAY).fillna(TODAY)
        incoming["Last Seen"] = TODAY
        incoming["Record Status"] = incoming["Record Status"].replace("", "Active").fillna("Active")
        return incoming.drop_duplicates(subset=[key_column], keep="last")

    existing_by_key = existing.drop_duplicates(subset=[key_column], keep="last").set_index(key_column, drop=False)
    incoming_by_key = incoming.drop_duplicates(subset=[key_column], keep="last").set_index(key_column, drop=False)

    all_columns = list(dict.fromkeys(list(existing.columns) + list(incoming.columns)))
    existing_by_key = ensure_columns(existing_by_key, all_columns)
    incoming_by_key = ensure_columns(incoming_by_key, all_columns)

    combined_rows = []
    all_keys = sorted(set(existing_by_key.index.astype(str)) | set(incoming_by_key.index.astype(str)))

    for key in all_keys:
        if key in incoming_by_key.index and key in existing_by_key.index:
            old = existing_by_key.loc[key].copy()
            new = incoming_by_key.loc[key].copy()
            merged = old.copy()
            for column in all_columns:
                value = new.get(column, "")
                if not pd.isna(value) and str(value).strip() != "":
                    merged[column] = value
            for column in preserve_columns:
                old_value = old.get(column, "")
                if not pd.isna(old_value) and str(old_value).strip() != "":
                    merged[column] = old_value
            merged["First Seen"] = old.get("First Seen", "") or TODAY
            merged["Last Seen"] = TODAY
            merged["Record Status"] = old.get("Record Status", "") or "Active"
            combined_rows.append(merged)
        elif key in incoming_by_key.index:
            row = incoming_by_key.loc[key].copy()
            row["First Seen"] = row.get("First Seen", "") or TODAY
            row["Last Seen"] = TODAY
            row["Record Status"] = row.get("Record Status", "") or "Active"
            combined_rows.append(row)
        else:
            row = existing_by_key.loc[key].copy()
            row["Record Status"] = row.get("Record Status", "") or "Not Seen In Latest Run"
            combined_rows.append(row)

    return pd.DataFrame(combined_rows)[all_columns]


def build_companies_master() -> pd.DataFrame:
    companies = read_csv_if_exists(QUALIFIED_COMPANIES_FILE)
    contacts, _ = choose_contact_source()

    company_rows = []
    if not companies.empty:
        company_rows.append(companies)
    if not contacts.empty:
        contact_company_cols = [
            "Company Name", "Website", "Domain", "Employees", "Company City", "Legal Segment",
            "ICP Score", "Qualification Status", "Qualification Reason", "Couno Status",
        ]
        contact_companies = contacts[[c for c in contact_company_cols if c in contacts.columns]].copy()
        company_rows.append(contact_companies)

    if not company_rows:
        return pd.DataFrame()

    incoming = pd.concat(company_rows, ignore_index=True)
    incoming = ensure_columns(incoming, ["Company Name", "Website", "Domain"])
    incoming["Domain"] = incoming.apply(lambda row: normalise_domain(row.get("Domain", "") or row.get("Website", "")), axis=1)
    incoming["Company Key"] = incoming.apply(build_company_key, axis=1)
    incoming["Database Source"] = "Latest pipeline output"
    incoming["Last Pipeline Update"] = TODAY

    if not contacts.empty and "Company Name" in contacts.columns:
        contact_counts = contacts.copy()
        contact_counts["Company Key"] = contact_counts.apply(lambda row: build_company_key(row), axis=1)
        contact_counts = contact_counts.groupby("Company Key").agg(
            Total_Contacts=("Company Key", "size"),
            Contacts_With_Email=("Email", lambda s: s.fillna("").astype(str).str.strip().ne("").sum() if "Email" in contacts.columns else 0),
        ).reset_index().rename(columns={"Total_Contacts": "Total Contacts", "Contacts_With_Email": "Contacts With Email"})
        incoming = incoming.merge(contact_counts, on="Company Key", how="left")

    existing = read_csv_if_exists(COMPANIES_MASTER_FILE)
    preserve_columns = ["Company Owner", "Do Not Contact Company", "Company Notes", "Company Priority", "Manual Review Status"]
    master = merge_master(existing, incoming, "Company Key", preserve_columns)
    return master.sort_values(by=["Company Name", "Domain"], na_position="last")


def build_contacts_master() -> pd.DataFrame:
    contacts, source_name = choose_contact_source()
    if contacts.empty:
        return pd.DataFrame()

    contacts = ensure_columns(contacts, ["Company Name", "Website", "Domain", "Email", "Apollo Person ID", "Full Name"])
    contacts["Domain"] = contacts.apply(lambda row: normalise_domain(row.get("Domain", "") or row.get("Website", "")), axis=1)
    contacts["Company Key"] = contacts.apply(build_company_key, axis=1)
    contacts["Contact Key"] = contacts.apply(build_contact_key, axis=1)
    contacts["Database Source"] = source_name
    contacts["Last Pipeline Update"] = TODAY

    management_columns = [
        "Do Not Contact", "Assigned To", "Prospect Status", "Marketing Status", "Campaign Status",
        "Call Status", "Last Contacted", "Last Activity", "Notes", "Manual Review Status",
    ]
    contacts = ensure_columns(contacts, management_columns)

    existing = read_csv_if_exists(CONTACTS_MASTER_FILE)
    preserve_columns = management_columns
    master = merge_master(existing, contacts, "Contact Key", preserve_columns)

    sort_cols = [c for c in ["Couno Fit Score", "Company Name", "Full Name"] if c in master.columns]
    ascending = [False if c == "Couno Fit Score" else True for c in sort_cols]
    if sort_cols:
        master = master.sort_values(by=sort_cols, ascending=ascending, na_position="last")
    return master


def main():
    companies_master = build_companies_master()
    contacts_master = build_contacts_master()

    if companies_master.empty:
        print("No company data found. Run the main pipeline first.")
    else:
        companies_master.to_csv(COMPANIES_MASTER_FILE, index=False)

    if contacts_master.empty:
        print("No contact data found. Run the main pipeline first.")
    else:
        contacts_master.to_csv(CONTACTS_MASTER_FILE, index=False)

    print("\nFinished.")
    print(f"Companies in master database: {len(companies_master)}")
    print(f"Contacts in master database: {len(contacts_master)}")
    print("Outputs created:")
    print(COMPANIES_MASTER_FILE)
    print(CONTACTS_MASTER_FILE)


if __name__ == "__main__":
    main()
