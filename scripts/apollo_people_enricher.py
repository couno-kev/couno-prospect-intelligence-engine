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
CACHE_DIR = BASE_DIR / "data" / "cache"
ENRICHMENT_CACHE_FILE = CACHE_DIR / "people_enrichment_cache.csv"
FORCE_REFRESH = os.getenv("FORCE_APOLLO_REFRESH", "false").lower() in {"1", "true", "yes"}

OUTPUT_COLUMNS = [
    "Company Name", "Website", "Domain", "Employees", "Company City", "First Name", "Last Name", "Full Name",
    "Job Title", "Persona Group", "Apollo Person ID", "Email", "Phone", "LinkedIn URL", "Enrichment Source", "Enriched Cached At",
]


def load_cache() -> pd.DataFrame:
    if ENRICHMENT_CACHE_FILE.exists():
        cache_df = pd.read_csv(ENRICHMENT_CACHE_FILE)
        for column in OUTPUT_COLUMNS:
            if column not in cache_df.columns:
                cache_df[column] = ""
        return cache_df[OUTPUT_COLUMNS]
    return pd.DataFrame(columns=OUTPUT_COLUMNS)


def save_cache(cache_df: pd.DataFrame) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_df = cache_df.drop_duplicates(subset=["Apollo Person ID"], keep="last")
    cache_df.to_csv(ENRICHMENT_CACHE_FILE, index=False)


def enrich_person(person_id: str, row: pd.Series) -> dict | None:
    url = "https://api.apollo.io/api/v1/people/match"
    payload = {"id": person_id}
    headers = {"Content-Type": "application/json", "X-Api-Key": API_KEY}
    response = requests.post(url, json=payload, headers=headers, timeout=30)

    if response.status_code != 200:
        print(f"Error {response.status_code}: {response.text}")
        return None

    person = response.json().get("person", {})
    first_name = person.get("first_name", row.get("First Name", "")) or ""
    last_name = person.get("last_name", row.get("Last Name", "")) or ""
    full_name = " ".join(x for x in [first_name, last_name] if str(x).lower() != "none" and str(x).strip())

    return {
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
        "Enrichment Source": "Apollo People Match",
        "Enriched Cached At": pd.Timestamp.now().isoformat(timespec="seconds"),
    }


def main():
    if not API_KEY:
        raise ValueError("APOLLO_API_KEY not found. Check your .env file.")

    df = pd.read_csv(INPUT_FILE)
    cache_df = load_cache()
    results = []
    new_cache_rows = []
    api_calls = 0
    cache_hits = 0

    for _, row in df.iterrows():
        person_id = row.get("Apollo Person ID")
        if pd.isna(person_id) or not str(person_id).strip():
            print(f"Skipping missing Apollo Person ID for: {row.get('Company Name', '')}")
            continue

        person_id = str(person_id).strip()
        cached = cache_df[cache_df["Apollo Person ID"].astype(str) == person_id]
        if not FORCE_REFRESH and not cached.empty:
            print(f"Using cached enrichment: {person_id}")
            results.append(cached.iloc[-1].to_dict())
            cache_hits += 1
            continue

        print(f"Enriching Apollo Person ID: {person_id}")
        enriched = enrich_person(person_id, row)
        if enriched:
            results.append(enriched)
            new_cache_rows.append(enriched)
            api_calls += 1

    output_df = pd.DataFrame(results, columns=OUTPUT_COLUMNS)
    output_df = output_df.drop_duplicates(subset=["Apollo Person ID"], keep="last")
    output_df.to_csv(OUTPUT_FILE, index=False)

    if new_cache_rows:
        updated_cache = pd.concat([cache_df, pd.DataFrame(new_cache_rows)], ignore_index=True)
        save_cache(updated_cache)

    print("\nFinished.")
    print(f"Records enriched/exported: {len(output_df)}")
    print(f"Enrichment cache hits: {cache_hits}")
    print(f"Apollo enrichment API calls made: {api_calls}")
    print(f"Output created: {OUTPUT_FILE}")
    print(f"Cache file: {ENRICHMENT_CACHE_FILE}")


if __name__ == "__main__":
    main()
