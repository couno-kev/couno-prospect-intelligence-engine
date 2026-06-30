from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]
DATABASE_DIR = BASE_DIR / "data" / "database"
OUTPUT_DIR = BASE_DIR / "data" / "output"

CONTACTS_MASTER_FILE = DATABASE_DIR / "contacts_master.csv"
MARKETING_OUTPUT = OUTPUT_DIR / "marketing_campaign_from_master.csv"
CALL_QUEUE_OUTPUT = OUTPUT_DIR / "weekly_call_queue_from_master.csv"

WEEKLY_COMPANY_LIMIT = 75


def ensure_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for column in columns:
        if column not in df.columns:
            df[column] = ""
    return df


def build_marketing_from_master(df: pd.DataFrame) -> pd.DataFrame:
    df = ensure_columns(df, [
        "Employment Validation Status", "LinkedIn Validation Status", "Email", "Do Not Contact", "Assigned To",
        "Marketing Status", "Campaign Name", "Email Sent Date", "Last Marketing Activity", "Record Status",
    ])

    campaign = df.copy()
    campaign = campaign[campaign["Record Status"].fillna("Active") == "Active"]
    campaign = campaign[campaign["Employment Validation Status"] == "Likely Current"]
    campaign = campaign[campaign["LinkedIn Validation Status"] == "High Confidence"]
    campaign = campaign[campaign["Email"].fillna("").astype(str).str.strip() != ""]
    campaign = campaign[campaign["Do Not Contact"].fillna("") != "Yes"]
    campaign = campaign[campaign["Assigned To"].fillna("") == ""]

    campaign["Marketing Status"] = campaign["Marketing Status"].replace("", "Ready").fillna("Ready")
    campaign["Campaign Name"] = campaign["Campaign Name"].replace("", "Legal Outreach Campaign").fillna("Legal Outreach Campaign")
    campaign["Email Sent Date"] = campaign["Email Sent Date"].fillna("")
    campaign["Last Marketing Activity"] = campaign["Last Marketing Activity"].fillna("")

    sort_cols = [c for c in ["Couno Fit Score", "LinkedIn Validation Score", "Contact Quality Score"] if c in campaign.columns]
    if sort_cols:
        campaign = campaign.sort_values(by=sort_cols, ascending=[False] * len(sort_cols), na_position="last")
    return campaign


def build_weekly_queue(campaign: pd.DataFrame) -> pd.DataFrame:
    if campaign.empty:
        return campaign

    company_col = "Company Key" if "Company Key" in campaign.columns else "Company Name"
    sort_cols = [c for c in ["Couno Fit Score", "LinkedIn Validation Score", "Contact Quality Score"] if c in campaign.columns]

    company_scores = campaign.copy()
    if sort_cols:
        company_scores = company_scores.sort_values(by=sort_cols, ascending=[False] * len(sort_cols), na_position="last")

    ordered_companies = company_scores.drop_duplicates(subset=[company_col], keep="first")[[company_col]].reset_index(drop=True)
    ordered_companies["Week Batch"] = (ordered_companies.index // WEEKLY_COMPANY_LIMIT) + 1
    ordered_companies["Company Call Order"] = ordered_companies.index + 1

    queue = campaign.merge(ordered_companies, on=company_col, how="left")
    queue = queue.sort_values(by=["Week Batch", "Company Call Order"] + sort_cols, ascending=[True, True] + ([False] * len(sort_cols)), na_position="last")
    return queue


def main():
    if not CONTACTS_MASTER_FILE.exists():
        raise FileNotFoundError("contacts_master.csv not found. Run build_master_database.py first.")

    df = pd.read_csv(CONTACTS_MASTER_FILE)
    print(f"Contacts loaded from master database: {len(df)}")

    campaign = build_marketing_from_master(df)
    queue = build_weekly_queue(campaign)

    campaign.to_csv(MARKETING_OUTPUT, index=False)
    queue.to_csv(CALL_QUEUE_OUTPUT, index=False)

    print("\nFinished.")
    print(f"Marketing-ready records from master: {len(campaign)}")
    print(f"Companies queued from master: {queue['Company Key'].nunique() if 'Company Key' in queue.columns and not queue.empty else 0}")
    print("Outputs created:")
    print(MARKETING_OUTPUT)
    print(CALL_QUEUE_OUTPUT)


if __name__ == "__main__":
    main()
