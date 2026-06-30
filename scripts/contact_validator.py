from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]

INPUT_FILE = BASE_DIR / "data" / "output" / "prospect_master.csv"
OUTPUT_FILE = BASE_DIR / "data" / "output" / "validated_prospects.csv"

TARGET_PERSONAS = [
    "Leadership",
    "Operations",
    "IT / Technology",
    "Practice / Office",
    "Finance / Compliance",
]


def has_value(value):
    return pd.notna(value) and str(value).strip() != ""


def calculate_score(row):
    score = 0
    reasons = []

    if has_value(row.get("Apollo Person ID")):
        score += 20
        reasons.append("Apollo Person ID found")
    else:
        reasons.append("Missing Apollo Person ID")

    if has_value(row.get("Email")):
        score += 25
        reasons.append("Email found")
    else:
        reasons.append("Missing email")

    if has_value(row.get("LinkedIn URL")):
        score += 20
        reasons.append("LinkedIn URL found")
    else:
        reasons.append("Missing LinkedIn URL")

    if has_value(row.get("Domain")):
        score += 15
        reasons.append("Company domain found")
    else:
        reasons.append("Missing company domain")

    if row.get("Persona Group") in TARGET_PERSONAS:
        score += 20
        reasons.append("Target persona match")
    else:
        reasons.append("Persona requires review")

    return score, "; ".join(reasons)


def validation_status(score):
    if score >= 80:
        return "Likely Current"
    if score >= 50:
        return "Review Required"
    return "Do Not Use"


df = pd.read_csv(INPUT_FILE)

print(f"Prospects loaded: {len(df)}")

scores = df.apply(calculate_score, axis=1)

df["Contact Quality Score"] = scores.apply(lambda x: x[0])
df["Validation Reason"] = scores.apply(lambda x: x[1])
df["Employment Validation Status"] = df["Contact Quality Score"].apply(validation_status)

df.to_csv(OUTPUT_FILE, index=False)

print()
print("Finished.")
print(df["Employment Validation Status"].value_counts())
print("Output created:")
print(OUTPUT_FILE)
