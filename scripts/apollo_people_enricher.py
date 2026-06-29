import os
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("APOLLO_API_KEY")

BASE_DIR = Path(__file__).resolve().parents[1]
INPUT_FILE = BASE_DIR / "data" / "output" / "company_people_export.csv"
OUTPUT_FILE = BASE_DIR / "data" / "output" / "company_people_enriched.csv"

df = pd.read_csv(INPUT_FILE)

# Test mode: only enrich first 50 contacts
df = df.head(50)

results = []

for _, row in df.iterrows():
    person_id = row.get("Apollo Person ID")

    if pd.isna(person_id) or not str(person_id).strip():
        print(f"Skipping missing Apollo Person ID for: {row.get('Company Name', '')}")
        continue

    print(f"Enriching Apollo Person ID: {person_id}")

    url = "https://api.apollo.io/api/v1/people/match"

    payload = {"id": person_id}

    headers = {
        "Content-Type": "application/json",
        "X-Api-Key": API_KEY
    }

    response = requests.post(url, json=payload, headers=headers)

    if response.status_code != 200:
        print(f"Error {response.status_code}: {response.text}")
        continue

    data = response.json()
    person = data.get("person", {})

    first_name = person.get("first_name", row.get("First Name", "")) or ""
    last_name = person.get("last_name", row.get("Last Name", "")) or ""

    full_name = " ".join(
        x for x in [first_name, last_name]
        if str(x).lower() != "none" and str(x).strip()
    )

    results.append({
        "Company Name": row.get("Company Name", ""),
        "Website": row.get("Website", ""),
        "Domain": row.get("Domain", ""),
        "Employees": row.get("Employees", ""),
        "Company City": row.get("Company City", ""),
        "First Name": first_name,
        "Last Name": last_name,
        "Full Name": full_name,
        "Job Title": person.get("title", row.get("Job Title", "")),
        "Persona Group": row.get("Persona Group", ""),
        "Apollo Person ID": person_id,
        "Email": person.get("email", ""),
        "Phone": person.get("phone_number", ""),
        "LinkedIn URL": person.get("linkedin_url", row.get("LinkedIn URL", "")),
        "Enrichment Source": "Apollo People Match"
    })

output_df = pd.DataFrame(results)
output_df.to_csv(OUTPUT_FILE, index=False)

print("\nFinished.")
print(f"Records enriched: {len(output_df)}")
print(f"Output created: {OUTPUT_FILE}")