"""
Citation Verifier ?" the most important file in this repo.
Extracts every [CASE: id] the model claims, checks it against the database,
and never presents an unverified citation as fact.
"""
import re
from db import case_exists, get_case

CITATION_PATTERN = re.compile(r"\[(?:CASE:\s*)?(NI138(?:-\d+)+)\]")

def extract_citations(answer_text: str):
    matches = CITATION_PATTERN.findall(answer_text)
    seen = set()
    ordered = []
    for m in matches:
        if m not in seen:
            seen.add(m)
            ordered.append(m)
    return ordered

def verify_citations(answer_text: str, validated_ids: set = None):
    claimed = extract_citations(answer_text)
    verified = []
    unverified = []
    clean_answer = answer_text

    for case_id in claimed:
        is_valid = case_exists(case_id)
        if is_valid and validated_ids is not None:
            if case_id not in validated_ids:
                is_valid = False

        if is_valid:
            case = get_case(case_id)
            year = (case["date"] or "")[:4]
            label = f"{case['title']} ({case['court']}, {year})"
            verified.append({
                "case_id": case_id, "title": case["title"],
                "court": case["court"], "date": case["date"],
            })
            clean_answer = re.sub(rf"\[(?:CASE:\s*)?{re.escape(case_id)}\]", f"[{label}]", clean_answer)
        else:
            unverified.append(case_id)
            clean_answer = re.sub(rf"\[(?:CASE:\s*)?{re.escape(case_id)}\]", f"[s UNVERIFIED CITATION: {case_id}]", clean_answer)

    return {
        "verified": verified,
        "unverified": unverified,
        "clean_answer": clean_answer,
        "accuracy_note": (
            f"{len(verified)}/{len(claimed)} citations verified and grounded" if claimed else "No citations were made"
        ),
    }
