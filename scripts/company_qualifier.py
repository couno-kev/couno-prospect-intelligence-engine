from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]

INPUT_FILE = BASE_DIR / "data" / "output" / "matched_companies.csv"
OUTPUT_FILE = BASE_DIR / "data" / "output" / "qualified_companies.csv"

TARGET_KEYWORDS = {
    "Solicitors": ["solicitors", "solicitor"],
    "Barristers Chambers": ["chambers", "barristers", "barrister"],
    "Law Firm": ["law firm", "lawyers"],
    "Legal LLP": ["llp"],
}

REVIEW_KEYWORDS = {
    "Legal Network / Association": ["alliance", "network", "association", "group of accountants and lawyers"],
    "LawTech / Legal Tech": ["lawtech", "legal tech", "legal technology"],
    "Legal Aid / Community": ["legal aid", "law centre", "law center", "community law"],
    "Student / Union": ["students", "student", "union"],
    "Legal Consultancy": ["legal consultancy", "legal consultant"],
    "Immigration / Visa": ["immigration", "visas"],
}

EXCLUDE_KEYWORDS = {
    "Recruitment": ["recruitment", "recruiter", "talent", "staffing", "headhunter", "executive search"],
    "Software": ["software", "saas", "platform", "app", "technology vendor"],
    "Training": ["training", "academy", "learning", "courses", "education"],
    "Marketing": ["marketing", "media", "advertising", "agency"],
}


def text_blob(row):
    fields = [
        row.get("Company Name", ""),
        row.get("Website", ""),
        row.get("Company City", ""),
    ]
    return " ".join(str(x).lower() for x in fields if pd.notna(x))


def classify_company(row):
    text = text_blob(row)

    score = 0
    reasons = []
    segment = ""

    for label, keywords in EXCLUDE_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            score -= 100
            reasons.append(f"Exclude keyword: {label}")

    review_hit = False
    for label, keywords in REVIEW_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            review_hit = True
            score += 20
            reasons.append(f"Review keyword: {label}")
            if not segment:
                segment = label

    for label, keywords in TARGET_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            if label == "Solicitors":
                score += 50
            elif label == "Barristers Chambers":
                score += 45
            elif label == "Law Firm":
                score += 40
            elif label == "Legal LLP":
                score += 10

            reasons.append(f"Target keyword: {label}")
            if not segment:
                segment = label

    if score < 20:
        status = "Exclude"
    elif review_hit and score < 80:
        status = "Review"
    elif score >= 40:
        status = "Target"
    else:
        status = "Review"

    if not segment:
        segment = "Unknown"

    return pd.Series({
        "Legal Segment": segment,
        "ICP Score": score,
        "Qualification Status": status,
        "Qualification Reason": "; ".join(reasons),
    })


df = pd.read_csv(INPUT_FILE)

print(f"Companies loaded: {len(df)}")

qualified = df.apply(classify_company, axis=1)
df = pd.concat([df, qualified], axis=1)

df.to_csv(OUTPUT_FILE, index=False)

print()
print("Finished.")
print(df["Qualification Status"].value_counts())
print("Output created:")
print(OUTPUT_FILE)
