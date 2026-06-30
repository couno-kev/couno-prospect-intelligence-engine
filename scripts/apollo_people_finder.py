import os
import time
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parents[1]
INPUT_FILE = BASE_DIR / "data" / "output" / "qualified_companies.csv"
OUTPUT_FILE = BASE_DIR / "data" / "output" / "company_people_export.csv"
CACHE_DIR = BASE_DIR / "data" / "cache"
COMPANY_PEOPLE_CACHE_FILE = CACHE_DIR / "company_people_search_cache.csv"

APOLLO_API_KEY = os.getenv("APOLLO_API_KEY")
APOLLO_PEOPLE_SEARCH_URL = "https://api.apollo.io/api/v1/mixed_people/api_search"

MAX_CONTACTS_PER_COMPANY = 5
REQUEST_DELAY_SECONDS = 1
FORCE_REFRESH = os.getenv("FORCE_APOLLO_REFRESH", "false").lower() in {"1", "true", "yes"}

TITLE_GROUPS = {
    "Leadership": ["Managing Partner", "Partner", "CEO", "Founder", "Director"],
    "Operations": ["COO", "Operations Director", "Head of Operations", "Operations Manager"],
    "IT / Technology": ["CTO", "IT Director", "Head of IT", "IT Manager", "Technology Director"],
    "Practice / Office": ["Practice Manager", "Office Manager", "Chambers Director", "Chambers Administrator"],
    "Finance / Compliance": ["Finance Director", "CFO", "Financial Controller", "Compliance Director", "Risk Director", "COLP", "COFA"],
}

OUTPUT_COLUMNS = [
    "Company Name", "Website", "Domain", "Employees", "Company City", "Legal Segment", "ICP Score",
    "Qualification Status", "Qualification Reason", "First Name", "Last Name", "Full Name", "Job Title",
    "Persona Group", "LinkedIn URL", "Apollo Person ID", "Email", "Phone", "Data Source", "Search Cached At",
]


def clean_domain(website: str) -> str:
    if pd.isna(website) or not str(website).strip():
        return ""
    website = str(website).strip()
    if not website.startswith(("http://", "https://")):
        website = "https://" + website
    parsed = urlparse(website)
    return parsed.netloc.lower().replace("www.", "").strip()


def flatten_titles() -> list[str]:
    titles = []
    for group_titles in TITLE_GROUPS.values():
        titles.extend(group_titles)
    return titles


def classify_persona(title: str) -> str:
    title_lower = str(title).lower()
    for group, titles in TITLE_GROUPS.items():
        for target_title in titles:
            if target_title.lower() in title_lower:
                return group
    return "Other"


def load_cache() -> pd.DataFrame:
    if COMPANY_PEOPLE_CACHE_FILE.exists():
        cache_df = pd.read_csv(COMPANY_PEOPLE_CACHE_FILE)
        for column in OUTPUT_COLUMNS:
            if column not in cache_df.columns:
                cache_df[column] = ""
        return cache_df[OUTPUT_COLUMNS]
    return pd.DataFrame(columns=OUTPUT_COLUMNS)


def save_cache(cache_df: pd.DataFrame) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_df = cache_df.drop_duplicates(subset=["Domain", "Apollo Person ID"], keep="last")
    cache_df.to_csv(COMPANY_PEOPLE_CACHE_FILE, index=False)


def search_people(company_name: str, domain: str) -> list[dict]:
    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
        "X-Api-Key": APOLLO_API_KEY,
    }
    payload = {
        "q_organization_domains_list": [domain],
        "person_titles": flatten_titles(),
        "include_similar_titles": True,
        "page": 1,
        "per_page": 25,
    }
    response = requests.post(APOLLO_PEOPLE_SEARCH_URL, headers=headers, json=payload, timeout=30)
    if response.status_code != 200:
        print(f"Error for {company_name}: {response.status_code} - {response.text}")
        return []
    return response.json().get("people", [])


def select_top_contacts(people: list[dict]) -> list[dict]:
    selected = []
    used_groups = set()
    for person in people:
        persona_group = classify_persona(person.get("title", ""))
        if persona_group != "Other" and persona_group not in used_groups:
            person["persona_group"] = persona_group
            selected.append(person)
            used_groups.add(persona_group)
        if len(selected) >= MAX_CONTACTS_PER_COMPANY:
            return selected
    for person in people:
        if len(selected) >= MAX_CONTACTS_PER_COMPANY:
            break
        if person not in selected:
            person["persona_group"] = classify_persona(person.get("title", ""))
            selected.append(person)
    return selected


def build_rows(company: pd.Series, people: list[dict]) -> list[dict]:
    now = pd.Timestamp.now().isoformat(timespec="seconds")
    rows = []
    for person in people:
        rows.append({
            "Company Name": company.get("Company Name", ""),
            "Website": company.get("Website", ""),
            "Domain": company.get("Domain", ""),
            "Employees": company.get("# Employees", ""),
            "Company City": company.get("Company City", ""),
            "Legal Segment": company.get("Legal Segment", ""),
            "ICP Score": company.get("ICP Score", ""),
            "Qualification Status": company.get("Qualification Status", ""),
            "Qualification Reason": company.get("Qualification Reason", ""),
            "First Name": person.get("first_name", ""),
            "Last Name": person.get("last_name", ""),
            "Full Name": person.get("name", ""),
            "Job Title": person.get("title", ""),
            "Persona Group": person.get("persona_group", ""),
            "LinkedIn URL": person.get("linkedin_url", ""),
            "Apollo Person ID": person.get("id", ""),
            "Email": "",
            "Phone": "",
            "Data Source": "Apollo People Search",
            "Search Cached At": now,
        })
    return rows


def main():
    if not APOLLO_API_KEY:
        raise ValueError("APOLLO_API_KEY not found. Check your .env file.")

    companies_df = pd.read_csv(INPUT_FILE)
    qualified_companies = companies_df[
        (companies_df["Qualification Status"] == "Target")
        & (companies_df["Couno Status"] == "New")
    ].copy()
    qualified_companies["Domain"] = qualified_companies["Website"].apply(clean_domain)
    qualified_companies = qualified_companies[qualified_companies["Domain"] != ""]

    cache_df = load_cache()
    output_rows = []
    new_cache_rows = []
    api_calls = 0
    cache_hits = 0

    print(f"Qualified target companies available: {len(qualified_companies)}")
    print(f"Cached company search rows available: {len(cache_df)}")

    for _, company in qualified_companies.iterrows():
        company_name = company["Company Name"]
        domain = company["Domain"]
        cached_rows = cache_df[cache_df["Domain"].astype(str).str.lower() == domain]

        if not FORCE_REFRESH and not cached_rows.empty:
            print(f"Using cached people search: {company_name} ({domain})")
            output_rows.extend(cached_rows.to_dict("records"))
            cache_hits += 1
            continue

        print(f"Searching Apollo: {company_name} ({domain})")
        people = search_people(company_name, domain)
        selected_people = select_top_contacts(people)
        rows = build_rows(company, selected_people)
        output_rows.extend(rows)
        new_cache_rows.extend(rows)
        api_calls += 1
        time.sleep(REQUEST_DELAY_SECONDS)

    output_df = pd.DataFrame(output_rows, columns=OUTPUT_COLUMNS)
    output_df = output_df.drop_duplicates(subset=["Domain", "Apollo Person ID"], keep="last")
    output_df.to_csv(OUTPUT_FILE, index=False)

    if new_cache_rows:
        updated_cache = pd.concat([cache_df, pd.DataFrame(new_cache_rows)], ignore_index=True)
        save_cache(updated_cache)

    print("\nFinished.")
    print(f"Contacts exported: {len(output_df)}")
    print(f"Company cache hits: {cache_hits}")
    print(f"Apollo people search API calls made: {api_calls}")
    print(f"Output created: {OUTPUT_FILE}")
    print(f"Cache file: {COMPANY_PEOPLE_CACHE_FILE}")


if __name__ == "__main__":
    main()
