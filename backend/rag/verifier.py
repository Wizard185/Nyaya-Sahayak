"""
Hallucination check: scans a generated answer for section references
(e.g. "Section 302", "IPC 420", "Article 21") and flags any that were
not actually present in the citations retrieved for that answer.
"""
import re
from typing import List

_SECTION_PATTERNS = [
    re.compile(r"\bSection\s+(\d+[A-Za-z]*)\b(?:\s+of\s+(?:the\s+)?([A-Za-z]+))?", re.IGNORECASE),
    re.compile(r"\b(IPC|CrPC|BNS)\s+(\d+[A-Za-z]*)\b", re.IGNORECASE),
    re.compile(r"\bArticle\s+(\d+[A-Za-z]*)\b", re.IGNORECASE),
]


def _extract_referenced_sections(answer: str) -> List[str]:
    """Return a de-duplicated list of human-readable section references found in the text."""
    found = []

    for match in _SECTION_PATTERNS[0].finditer(answer):
        number, act = match.groups()
        label = f"Section {number}" + (f" of {act}" if act else "")
        found.append((number.upper(), label))

    for match in _SECTION_PATTERNS[1].finditer(answer):
        act, number = match.groups()
        found.append((number.upper(), f"{act.upper()} {number}"))

    for match in _SECTION_PATTERNS[2].finditer(answer):
        number = match.group(1)
        found.append((number.upper(), f"Article {number}"))

    seen = set()
    unique_labels = []
    for number, label in found:
        if number not in seen:
            seen.add(number)
            unique_labels.append((number, label))
    return unique_labels


def hallucination_check(answer: str, citations: List[dict]) -> List[str]:
    """
    Returns a list of human-readable section references that appear in
    `answer` but are NOT backed by any entry in `citations`.
    """
    cited_numbers = set()
    for c in citations:
        section_id = str(c.get("section_id", ""))
        digits = re.findall(r"\d+[A-Za-z]*", section_id)
        for d in digits:
            cited_numbers.add(d.upper())

    referenced = _extract_referenced_sections(answer)

    flags = []
    for number, label in referenced:
        if number not in cited_numbers:
            flags.append(label)
    return flags
