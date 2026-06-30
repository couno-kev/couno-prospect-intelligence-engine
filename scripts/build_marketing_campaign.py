import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]

INPUT_FILE = BASE_DIR / "data" / "output" / "couno_scored_prospects.csv"
FALLBACK_INPUT_FILE = BASE_DIR / "data" / "output" / "linkedin_validated_prospects.csv"
OUTPUT_FILE = BASE_DIR / "data" / "output" / "marketing_campaign.csv"

input_file = INPUT_FILE if INPUT_FILE.exists() else FALLBACK_INPUT_FILE
df = pd.read_csv(input_file)

print(f"Prospects loaded: {len(df)}")

required_columns = [
    "Do Not Contact",
    "Assigned To",
    "Marketing Status",
    "Campaign Name",
    "Email Sent Date",
    "Last Marketing Activity",
]

for col in required_columns:
    if col not in df.columns:
        df[col] = ""

campaign_df = df.copy()

campaign_df = campaign_df[
    campaign_df["Employment Validation Status"] == "Likely Current"
]

campaign_df = campaign_df[
    campaign_df["LinkedIn Validation Status"] == "High Confidence"
]

campaign_df = campaign_df[
    campaign_df["Email"].notna()
]

campaign_df = campaign_df[
    campaign_df["Email"] != ""
]

campaign_df = campaign_df[
    campaign_df["Do Not Contact"].fillna("") != "Yes"
]

campaign_df = campaign_df[
    campaign_df["Assigned To"].fillna("") == ""
]

campaign_df["Marketing Status"] = campaign_df["Marketing Status"].replace("", "Ready")
campaign_df["Campaign Name"] = campaign_df["Campaign Name"].replace("", "Legal Outreach Campaign")
campaign_df["Email Sent Date"] = campaign_df["Email Sent Date"].fillna("")
campaign_df["Last Marketing Activity"] = campaign_df["Last Marketing Activity"].fillna("")

if "Couno Fit Score" in campaign_df.columns:
    campaign_df = campaign_df.sort_values(by=["Couno Fit Score", "LinkedIn Validation Score", "Contact Quality Score"], ascending=[False, False, False])

campaign_df.to_csv(OUTPUT_FILE, index=False)

print()
print("Finished.")
print(f"Marketing-ready prospects: {len(campaign_df)}")
print("Output created:")
print(OUTPUT_FILE)
