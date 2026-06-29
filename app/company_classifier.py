import pandas as pd

POSITIVE_LAW_KEYWORDS = [
    "solicitor", "solicitors", "law firm", "law practice", "barrister", "barristers",
    "chambers", "conveyancing", "litigation", "private client", "family law",
    "employment law", "commercial law", "criminal law", "legal services"
]

NEGATIVE_KEYWORDS = {
    "Legal Recruiter": ["recruitment", "recruiter", "staffing", "talent", "executive search"],
    "Legal Technology": ["software", "saas", "platform", "technology", "tech", "case management"],
    "Consultancy": ["consultancy", "consulting", "advisor", "advisory"],
    "Membership Organisation": ["association", "membership", "alliance", "network"],
    "Outsourced Legal Services": ["outsourced", "outsourcing", "document review", "process outsourcing"],
}

def classify_company(row: pd.Series) -> tuple[str, str, str]:
    text = " ".join(str(row.get(c, "")) for c in row.index).lower()

    if "chambers" in text or "barrister" in text:
        return "Barristers Chambers", "Target", "Company appears to be a chambers or barristers practice."

    for company_type, keywords in NEGATIVE_KEYWORDS.items():
        if any(k in text for k in keywords):
            return company_type, "Exclude", f"Company appears to be {company_type.lower()}."

    if any(k in text for k in POSITIVE_LAW_KEYWORDS):
        return "Law Firm", "Target", "Company appears to be a qualified law practice."

    return "Unknown", "Review", "Not enough information to confirm qualified law practice."
