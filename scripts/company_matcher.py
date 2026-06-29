import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
INPUT_DIR = BASE_DIR / "data" / "input"
OUTPUT_DIR = BASE_DIR / "data" / "output"

APOLLO_FILE = INPUT_DIR / "Automated List - Legal Bot Companies.csv"
PBR_FILE = INPUT_DIR / "Couno PBR New Connor.xlsx"
OUTPUT_FILE = OUTPUT_DIR / "matched_companies.csv"

apollo_df = pd.read_csv(APOLLO_FILE)

pbr_df = pd.read_excel(
    PBR_FILE,
    usecols="C:Q",
    header=17
).dropna(how="all")

apollo_df["Company Match Name"] = (
    apollo_df["Company Name"]
    .astype(str)
    .str.lower()
    .str.strip()
)

pbr_df["PBR Match Name"] = (
    pbr_df["Company Name"]
    .astype(str)
    .str.lower()
    .str.strip()
)

pbr_companies = set(pbr_df["PBR Match Name"].dropna())

apollo_df["Couno Status"] = apollo_df["Company Match Name"].apply(
    lambda company: "Already Worked" if company in pbr_companies else "New"
)

output_columns = [
    "Company Name",
    "Website",
    "# Employees",
    "Company City",
    "Couno Status",
]

output_df = apollo_df[output_columns]

output_df.to_csv(OUTPUT_FILE, index=False)

print("Finished successfully.")
print(output_df["Couno Status"].value_counts())
print(f"Output created here: {OUTPUT_FILE}")