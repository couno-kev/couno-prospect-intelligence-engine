from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]
INPUT_FILE = BASE_DIR / "data" / "output" / "marketing_campaign.csv"
OUTPUT_DIR = BASE_DIR / "data" / "output"
INSTANTLY_OUTPUT_FILE = OUTPUT_DIR / "instantly_upload.csv"
APOLLO_OUTPUT_FILE = OUTPUT_DIR / "apollo_sequence_upload.csv"


def split_full_name(full_name: str) -> tuple[str, str]:
    parts = str(full_name or "").strip().split()
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def value(row: pd.Series, column: str) -> str:
    item = row.get(column, "")
    return "" if pd.isna(item) else str(item).strip()


def main():
    df = pd.read_csv(INPUT_FILE)
    print(f"Marketing campaign records loaded: {len(df)}")

    if "Couno Fit Score" in df.columns:
        df = df.sort_values(by=["Couno Fit Score"], ascending=False)

    instantly_rows = []
    apollo_rows = []

    for _, row in df.iterrows():
        first_name = value(row, "First Name")
        last_name = value(row, "Last Name")
        if not first_name and not last_name:
            first_name, last_name = split_full_name(value(row, "Full Name"))

        common_custom_fields = {
            "legal_segment": value(row, "Legal Segment"),
            "persona_group": value(row, "Persona Group"),
            "couno_fit_score": value(row, "Couno Fit Score"),
            "couno_fit_tier": value(row, "Couno Fit Tier"),
            "linkedin_url": value(row, "LinkedIn URL"),
        }

        instantly_rows.append({
            "email": value(row, "Email"),
            "first_name": first_name,
            "last_name": last_name,
            "company_name": value(row, "Company Name"),
            "website": value(row, "Website"),
            "title": value(row, "Job Title"),
            **common_custom_fields,
        })

        apollo_rows.append({
            "Email": value(row, "Email"),
            "First Name": first_name,
            "Last Name": last_name,
            "Company": value(row, "Company Name"),
            "Website": value(row, "Website"),
            "Title": value(row, "Job Title"),
            "Phone": value(row, "Phone"),
            "LinkedIn URL": value(row, "LinkedIn URL"),
            "Legal Segment": value(row, "Legal Segment"),
            "Persona Group": value(row, "Persona Group"),
            "Couno Fit Score": value(row, "Couno Fit Score"),
            "Couno Fit Tier": value(row, "Couno Fit Tier"),
        })

    pd.DataFrame(instantly_rows).to_csv(INSTANTLY_OUTPUT_FILE, index=False)
    pd.DataFrame(apollo_rows).to_csv(APOLLO_OUTPUT_FILE, index=False)

    print("\nFinished.")
    print(f"Instantly upload rows: {len(instantly_rows)}")
    print(f"Apollo upload rows: {len(apollo_rows)}")
    print("Outputs created:")
    print(INSTANTLY_OUTPUT_FILE)
    print(APOLLO_OUTPUT_FILE)


if __name__ == "__main__":
    main()
