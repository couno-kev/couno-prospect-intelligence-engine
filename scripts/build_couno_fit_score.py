from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]
INPUT_FILE = BASE_DIR / "data" / "output" / "linkedin_validated_prospects.csv"
OUTPUT_FILE = BASE_DIR / "data" / "output" / "couno_scored_prospects.csv"

PERSONA_POINTS = {
    "Leadership": 30,
    "Operations": 25,
    "IT / Technology": 25,
    "Practice / Office": 20,
    "Finance / Compliance": 20,
    "Other": 5,
}

SEGMENT_POINTS = {
    "Solicitors": 25,
    "Law Firm": 25,
    "Barristers Chambers": 20,
    "Legal LLP": 15,
}


def has_value(value) -> bool:
    return pd.notna(value) and str(value).strip() != ""


def employee_score(value) -> tuple[int, str]:
    try:
        employees = int(float(str(value).replace(",", "")))
    except (TypeError, ValueError):
        return 5, "Employee count unknown"

    if 20 <= employees <= 250:
        return 20, "Employee count in core SMB/mid-market range"
    if 10 <= employees < 20 or 251 <= employees <= 500:
        return 12, "Employee count near target range"
    if employees > 500:
        return 5, "Employee count larger than usual target"
    return 3, "Employee count smaller than usual target"


def calculate_fit_score(row: pd.Series) -> tuple[int, str, str]:
    score = 0
    reasons = []

    persona = str(row.get("Persona Group", "")).strip()
    persona_points = PERSONA_POINTS.get(persona, 5)
    score += persona_points
    reasons.append(f"Persona: {persona or 'Unknown'} (+{persona_points})")

    segment = str(row.get("Legal Segment", "")).strip()
    segment_points = SEGMENT_POINTS.get(segment, 10 if segment else 0)
    score += segment_points
    reasons.append(f"Legal segment: {segment or 'Unknown'} (+{segment_points})")

    emp_points, emp_reason = employee_score(row.get("Employees", ""))
    score += emp_points
    reasons.append(f"{emp_reason} (+{emp_points})")

    if has_value(row.get("Email")):
        score += 10
        reasons.append("Email available (+10)")
    else:
        reasons.append("Email missing (+0)")

    if has_value(row.get("LinkedIn URL")):
        score += 5
        reasons.append("LinkedIn URL available (+5)")
    else:
        reasons.append("LinkedIn URL missing (+0)")

    if row.get("Employment Validation Status") == "Likely Current":
        score += 5
        reasons.append("Likely-current employment (+5)")

    if row.get("LinkedIn Validation Status") == "High Confidence":
        score += 5
        reasons.append("High-confidence LinkedIn validation (+5)")

    score = min(score, 100)

    if score >= 80:
        tier = "A - Priority"
    elif score >= 65:
        tier = "B - Good Fit"
    elif score >= 50:
        tier = "C - Review"
    else:
        tier = "D - Low Fit"

    return score, tier, "; ".join(reasons)


def main():
    df = pd.read_csv(INPUT_FILE)
    print(f"LinkedIn validated prospects loaded: {len(df)}")

    scores = df.apply(calculate_fit_score, axis=1)
    df["Couno Fit Score"] = scores.apply(lambda item: item[0])
    df["Couno Fit Tier"] = scores.apply(lambda item: item[1])
    df["Couno Fit Reason"] = scores.apply(lambda item: item[2])

    df = df.sort_values(
        by=["Couno Fit Score", "LinkedIn Validation Score", "Contact Quality Score"],
        ascending=[False, False, False],
    )

    df.to_csv(OUTPUT_FILE, index=False)

    print("\nFinished.")
    print(df["Couno Fit Tier"].value_counts(dropna=False))
    print("Output created:")
    print(OUTPUT_FILE)


if __name__ == "__main__":
    main()
