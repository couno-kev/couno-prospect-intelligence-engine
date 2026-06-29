from pathlib import Path
import pandas as pd
import math

BASE_DIR = Path(__file__).resolve().parents[1]

INPUT_FILE = (
    BASE_DIR
    / "data"
    / "output"
    / "linkedin_validated_prospects.csv"
)

OUTPUT_FILE = (
    BASE_DIR
    / "data"
    / "output"
    / "weekly_call_queue.csv"
)

COMPANIES_PER_WEEK = 75

df = pd.read_csv(INPUT_FILE)

print(f"LinkedIn validated prospect records loaded: {len(df)}")

# Only use the highest quality prospects
df = df[
    df["Employment Validation Status"] == "Likely Current"
]

df = df[
    df["LinkedIn Validation Status"] == "High Confidence"
]

df = df[
    df["Company Name"].notna()
]

df = df[
    df["Company Name"] != ""
]

print(f"High confidence records used: {len(df)}")

companies = (
    df.groupby("Company Name")
    .agg({
        "Website": "first",
        "Domain": "first",
        "Employees": "first",
        "Company City": "first",
        "Full Name": lambda x: " | ".join(
            x.dropna().astype(str).head(5)
        ),
        "Job Title": lambda x: " | ".join(
            x.dropna().astype(str).head(5)
        ),
        "Email": lambda x: " | ".join(
            x.dropna().astype(str).head(5)
        ),
        "Persona Group": lambda x: " | ".join(
            x.dropna().astype(str).head(5)
        ),
        "LinkedIn URL": lambda x: " | ".join(
            x.dropna().astype(str).head(5)
        ),
        "Contact Quality Score": "max",
        "LinkedIn Validation Score": "max",
    })
    .reset_index()
)

companies = companies.rename(columns={
    "Full Name": "Top Contacts",
    "Job Title": "Top Contact Titles",
    "Email": "Top Contact Emails",
    "Persona Group": "Persona Groups",
    "LinkedIn URL": "Top Contact LinkedIn URLs",
    "Contact Quality Score": "Best Contact Quality Score",
    "LinkedIn Validation Score": "Best LinkedIn Validation Score",
})

companies["Week Number"] = companies.index.map(
    lambda i: math.floor(i / COMPANIES_PER_WEEK) + 1
)

companies["Assigned To"] = ""
companies["Call Status"] = "Not Started"
companies["First Call Date"] = ""
companies["Last Call Date"] = ""
companies["Outcome"] = ""
companies["Next Action"] = ""
companies["Notes"] = ""

companies.to_csv(OUTPUT_FILE, index=False)

print()
print("Finished.")
print(f"Companies queued: {len(companies)}")
print(f"Weeks created: {companies['Week Number'].max()}")
print("Output created:")
print(OUTPUT_FILE)