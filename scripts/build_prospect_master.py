from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]
INPUT_FILE = BASE_DIR / "data" / "output" / "company_people_enriched.csv"
OUTPUT_FILE = BASE_DIR / "data" / "output" / "prospect_master.csv"

df = pd.read_csv(INPUT_FILE)

print(f"Contacts loaded: {len(df)}")

df["Prospect Status"] = "New"
df["Assigned To"] = ""
df["Date Added"] = pd.Timestamp.today().date()
df["Last Contacted"] = ""
df["Last Activity"] = ""
df["Campaign Status"] = ""
df["Call Status"] = ""
df["Notes"] = ""

df = df.drop_duplicates(
    subset=["Company Name", "Email"],
    keep="first"
)

print(f"Unique contacts: {len(df)}")

df.to_csv(OUTPUT_FILE, index=False)

print("\nFinished.")
print("Prospect master created:")
print(OUTPUT_FILE)
