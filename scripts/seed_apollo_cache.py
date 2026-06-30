from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = BASE_DIR / "data" / "output"
CACHE_DIR = BASE_DIR / "data" / "cache"

PEOPLE_SEARCH_OUTPUT = OUTPUT_DIR / "company_people_export.csv"
ENRICHMENT_OUTPUT = OUTPUT_DIR / "company_people_enriched.csv"
PEOPLE_SEARCH_CACHE = CACHE_DIR / "company_people_search_cache.csv"
ENRICHMENT_CACHE = CACHE_DIR / "people_enrichment_cache.csv"

PEOPLE_SEARCH_COLUMNS = [
    "Company Name", "Website", "Domain", "Employees", "Company City", "Legal Segment", "ICP Score",
    "Qualification Status", "Qualification Reason", "First Name", "Last Name", "Full Name", "Job Title",
    "Persona Group", "LinkedIn URL", "Apollo Person ID", "Email", "Phone", "Data Source", "Search Cached At",
]

ENRICHMENT_COLUMNS = [
    "Company Name", "Website", "Domain", "Employees", "Company City", "First Name", "Last Name", "Full Name",
    "Job Title", "Persona Group", "Apollo Person ID", "Email", "Phone", "LinkedIn URL", "Enrichment Source", "Enriched Cached At",
]


def normalise_columns(df: pd.DataFrame, columns: list[str], timestamp_column: str, source_column: str, source_value: str) -> pd.DataFrame:
    for column in columns:
        if column not in df.columns:
            df[column] = ""
    if timestamp_column in df.columns:
        df[timestamp_column] = df[timestamp_column].fillna("")
        df.loc[df[timestamp_column].astype(str).str.strip() == "", timestamp_column] = pd.Timestamp.now().isoformat(timespec="seconds")
    if source_column in df.columns:
        df[source_column] = df[source_column].fillna("")
        df.loc[df[source_column].astype(str).str.strip() == "", source_column] = source_value
    return df[columns]


def main():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    if PEOPLE_SEARCH_OUTPUT.exists():
        search_df = pd.read_csv(PEOPLE_SEARCH_OUTPUT)
        search_df = normalise_columns(
            search_df,
            PEOPLE_SEARCH_COLUMNS,
            "Search Cached At",
            "Data Source",
            "Seeded from existing company_people_export.csv",
        )
        search_df = search_df.drop_duplicates(subset=["Domain", "Apollo Person ID"], keep="last")
        search_df.to_csv(PEOPLE_SEARCH_CACHE, index=False)
        print(f"People search cache created: {len(search_df)} rows")
        print(f"{PEOPLE_SEARCH_CACHE}")
    else:
        print(f"Skipped people search cache. Missing file: {PEOPLE_SEARCH_OUTPUT}")

    if ENRICHMENT_OUTPUT.exists():
        enrichment_df = pd.read_csv(ENRICHMENT_OUTPUT)
        enrichment_df = normalise_columns(
            enrichment_df,
            ENRICHMENT_COLUMNS,
            "Enriched Cached At",
            "Enrichment Source",
            "Seeded from existing company_people_enriched.csv",
        )
        enrichment_df = enrichment_df.drop_duplicates(subset=["Apollo Person ID"], keep="last")
        enrichment_df.to_csv(ENRICHMENT_CACHE, index=False)
        print(f"Enrichment cache created: {len(enrichment_df)} rows")
        print(f"{ENRICHMENT_CACHE}")
    else:
        print(f"Skipped enrichment cache. Missing file: {ENRICHMENT_OUTPUT}")

    print("\nFinished. This script does not call Apollo or use credits.")


if __name__ == "__main__":
    main()
