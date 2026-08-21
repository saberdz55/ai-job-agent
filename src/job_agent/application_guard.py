"""Deterministic safety and mapping helpers for application forms."""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class FieldProposal:
    field: str
    category: str
    value: str | None
    status: str
    reason: str


_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    ("email", ("email", "e-mail")),
    ("phone", ("phone", "mobile", "telephone", "tel")),
    ("first_name", ("first name", "given name", "prénom", "prenom")),
    ("last_name", ("last name", "surname", "family name", "nom")),
    ("city", ("city", "town", "ville")),
    ("country", ("country", "pays")),
    ("linkedin", ("linkedin",)),
    ("portfolio", ("portfolio", "website", "personal site")),
    ("work_authorization", ("work authorization", "right to work", "eligible to work")),
    ("sponsorship", ("sponsor", "visa sponsorship", "sponsorship")),
    ("experience_years", ("years of experience", "experience (years)", "years' experience")),
]

# These fields can have legal/immigration consequences and are never auto-filled.
SENSITIVE_CATEGORIES = frozenset({"work_authorization", "sponsorship"})


def classify_field(label: str, name: str = "") -> str:
    hay = re.sub(r"\s+", " ", f"{label} {name}".lower()).strip()
    for category, patterns in _PATTERNS:
        if any(pattern in hay for pattern in patterns):
            return category
    return "unknown"


def propose_field(label: str, name: str, facts: dict[str, object]) -> FieldProposal:
    category = classify_field(label, name)
    field = label or name
    if category == "unknown":
        return FieldProposal(field, category, None, "REVIEW", "No trusted mapping exists.")
    raw = facts.get(category)
    if category in SENSITIVE_CATEGORIES:
        return FieldProposal(field, category, None, "REVIEW",
                             "Sensitive/legal field: candidate must explicitly review and answer it.")
    if raw is None or str(raw).strip() == "":
        return FieldProposal(field, category, None, "UNKNOWN", "Candidate fact is missing.")
    return FieldProposal(field, category, str(raw), "VERIFIED", "Value comes directly from candidate facts.")


def validate_answer(category: str, answer: str, facts: dict[str, object]) -> tuple[bool, str]:
    """Return whether an answer is explicitly supported by candidate facts."""
    answer = answer.strip()
    if not answer:
        return False, "empty_answer"
    if category in SENSITIVE_CATEGORIES:
        return False, "sensitive_field_requires_human_review"
    if category == "experience_years":
        expected = facts.get(category)
        if expected is None:
            return False, "missing_candidate_fact"
        try:
            return float(answer) <= float(expected), "supported_by_candidate_fact"
        except ValueError:
            return False, "numeric_fact_required"
    expected = facts.get(category)
    if expected is None:
        return False, "missing_candidate_fact"
    return answer.casefold() == str(expected).casefold(), "exact_candidate_fact_match"
