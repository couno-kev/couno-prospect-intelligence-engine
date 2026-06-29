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

APOLLO_API_KEY = os.getenv("APOLLO_API_KEY")
APOLLO_PEOPLE_SEARCH_URL = "https://api.apollo.io/api/v1/mixed_people/api_search"

MAX_COMPANIES = 100
MAX_CONTACTS_PER_COMPANY = 5

TITLE_GROUPS = {
    "Leadership": ["Managing Partner", "Partner", "CEO", "Founder", "Director"],
    "Operations": ["COO", "Operations Director", "Head of Operations", "Operations Manager"],
    "IT / Technology": ["CTO", "IT Director", "Head of IT", "IT Manager", "Technology Director"],
    "Practice / Office": ["Practice Manager", "Office Manager", "Chambers Director", "Chambers Administrator"],
    "Finance / Compliance": ["Finance Director", "CFO", "Financial Controller", "Compliance Director", "Risk Director", "COLP", "COFA"],
}


def clean_domain(website: str) -> str:
    if pd.isna(website) or not str(website).strip():
        return ""

    website = str(website).strip()

    if not website.startswith(("http://", "https://")):
        website = "https://" + website

    parsed = urlparse(website)
    return parsed.netloc.replace("www.", "").replace("https", "").strip()


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

    response = requests.post(
        APOLLO_PEOPLE_SEARCH_URL,
        headers=headers,
        json=payload,
        timeout=30,
    )

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

    companies_to_process = qualified_companies.head(MAX_COMPANIES)

    rows = []

    print(f"Qualified target companies available: {len(qualified_companies)}")
    print(f"Searching Apollo for {len(companies_to_process)} companies...")

    for _, company in companies_to_process.iterrows():
        company_name = company["Company Name"]
        domain = company["Domain"]

        print(f"Searching: {company_name} ({domain})")

        people = search_people(company_name, domain)
        selected_people = select_top_contacts(people)

        for person in selected_people:
            rows.append({
                "Company Name": company_name,
                "Website": company.get("Website", ""),
                "Domain": domain,
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
            })

        time.sleep(1)

    output_df = pd.DataFrame(rows)
    output_df.to_csv(OUTPUT_FILE, index=False)

    print()
    print("Finished.")
    print(f"Contacts found: {len(output_df)}")
    print(f"Output created: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()