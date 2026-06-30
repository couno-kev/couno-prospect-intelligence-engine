from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]
INPUT_FILE = BASE_DIR / "data" / "output" / "couno_scored_prospects.csv"
FALLBACK_INPUT_FILE = BASE_DIR / "data" / "output" / "linkedin_validated_prospects.csv"
OUTPUT_FILE = BASE_DIR / "data" / "output" / "manual_review_dashboard.csv"

REVIEW_COLUMNS = [
    "Review Owner", "Review Status", "Review Decision", "Review Notes", "Reviewed Date",
]


def has_value(value) -> bool:
    return pd.notna(value) and str(value).strip() != ""


def review_reason(row: pd.Series) -> str:
    reasons = []
    if row.get("Employment Validation Status") != "Likely Current":
        reasons.append(f"Employment: {row.get('Employment Validation Status', 'Unknown')}")
    if row.get("LinkedIn Validation Status") != "High Confidence":
        reasons.append(f"LinkedIn: {row.get('LinkedIn Validation Status', 'Unknown')}")
    if not has_value(row.get("Email")):
        reasons.append("Missing email")
    if not has_value(row.get("LinkedIn URL")):
        reasons.append("Missing LinkedIn URL")
    if str(row.get("Persona Group", "")).strip() in {"", "Other"}:
        reasons.append("Persona requires review")
    if str(row.get("Qualification Status", "")).strip() == "Review":
        reasons.append("Company qualification requires review")
    if has_value(row.get("Couno Fit Tier")) and str(row.get("Couno Fit Tier", "")).startswith("C"):
        reasons.append("Couno Fit Tier C")
    return "; ".join(reasons) if reasons else "General spot-check"


def main():
    input_file = INPUT_FILE if INPUT_FILE.exists() else FALLBACK_INPUT_FILE
    df = pd.read_csv(input_file)
    print(f"Prospects loaded: {len(df)}")

    mask = (
        (df.get("Employment Validation Status", "") != "Likely Current")
        | (df.get("LinkedIn Validation Status", "") != "High Confidence")
        | (df.get("Email", pd.Series(index=df.index, dtype=str)).fillna("") == "")
        | (df.get("LinkedIn URL", pd.Series(index=df.index, dtype=str)).fillna("") == "")
        | (df.get("Persona Group", pd.Series(index=df.index, dtype=str)).fillna("").isin(["", "Other"]))
    )

    review_df = df[mask].copy()
    review_df["Manual Review Reason"] = review_df.apply(review_reason, axis=1)

    for col in REVIEW_COLUMNS:
        if col not in review_df.columns:
            review_df[col] = ""

    priority_cols = REVIEW_COLUMNS + [
        "Manual Review Reason", "Company Name", "Website", "Domain", "Employees", "Company City", "Legal Segment",
        "ICP Score", "Qualification Status", "Qualification Reason", "Full Name", "Job Title", "Persona Group",
        "Email", "LinkedIn URL", "Apollo Person ID", "Employment Validation Status", "Contact Quality Score",
        "Validation Reason", "LinkedIn Validation Status", "LinkedIn Validation Score", "LinkedIn Validation Reason",
        "Couno Fit Score", "Couno Fit Tier", "Couno Fit Reason",
    ]
    existing_cols = [col for col in priority_cols if col in review_df.columns]
    remaining_cols = [col for col in review_df.columns if col not in existing_cols]
    review_df = review_df[existing_cols + remaining_cols]

    review_df.to_csv(OUTPUT_FILE, index=False)

    print("\nFinished.")
    print(f"Review records created: {len(review_df)}")
    print("Output created:")
    print(OUTPUT_FILE)


if __name__ == "__main__":
    main()
