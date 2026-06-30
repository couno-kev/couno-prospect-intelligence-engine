from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]

INPUT_FILE = BASE_DIR / "data" / "output" / "validated_prospects.csv"
OUTPUT_FILE = BASE_DIR / "data" / "output" / "linkedin_validated_prospects.csv"

TARGET_PERSONAS = [
    "Leadership",
    "Operations",
    "IT / Technology",
    "Practice / Office",
    "Finance / Compliance",
]


def has_value(value):
    return pd.notna(value) and str(value).strip() != ""


def calculate_linkedin_score(row):
    score = 0
    reasons = []

    if row.get("Employment Validation Status") == "Likely Current":
        score += 25
        reasons.append("Employment status likely current")
    else:
        reasons.append("Employment status requires review")

    if has_value(row.get("LinkedIn URL")):
        score += 20
        reasons.append("LinkedIn URL found")
    else:
        reasons.append("Missing LinkedIn URL")

    if has_value(row.get("Email")):
        score += 20
        reasons.append("Email found")
    else:
        reasons.append("Missing email")

    if has_value(row.get("Domain")):
        score += 15
        reasons.append("Company domain found")
    else:
        reasons.append("Missing company domain")

    if row.get("Persona Group") in TARGET_PERSONAS:
        score += 15
        reasons.append("Target persona match")
    else:
        reasons.append("Persona requires review")

    if has_value(row.get("Full Name")):
        score += 5
        reasons.append("Full name found")
    else:
        reasons.append("Missing full name")

    return score, "; ".join(reasons)


def linkedin_status(score):
    if score >= 85:
        return "High Confidence"
    if score >= 65:
        return "Medium Confidence"
    return "Review Required"


df = pd.read_csv(INPUT_FILE)

print(f"Validated prospects loaded: {len(df)}")

linkedin_scores = df.apply(calculate_linkedin_score, axis=1)

df["LinkedIn Validation Score"] = linkedin_scores.apply(lambda x: x[0])
df["LinkedIn Validation Reason"] = linkedin_scores.apply(lambda x: x[1])
df["LinkedIn Validation Status"] = df["LinkedIn Validation Score"].apply(linkedin_status)

df.to_csv(OUTPUT_FILE, index=False)

print()
print("Finished.")
print(df["LinkedIn Validation Status"].value_counts())
print("Output created:")
print(OUTPUT_FILE)
