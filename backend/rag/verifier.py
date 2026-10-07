"""
Hallucination check: scans a generated answer for section references
(e.g. "Section 302", "IPC 420", "Article 21") and case-name references
(e.g. "Imperia Structures Ltd. v. Anil Patni"), flagging any that were not
actually present in the citations retrieved for that answer.

Section checks are act-aware: "Section 302 of the Consumer Protection Act"
is flagged even though 302 is a real section number, because it's really
an IPC section — matching the number alone isn't enough (see
_normalize_act / _ACT_ALIASES).
"""
import re
from typing import List, Optional, Tuple

_SECTION_PATTERNS = [
    re.compile(r"\bSection\s+(\d+[A-Za-z]*)\b(?:\s+of\s+(?:the\s+)?([A-Za-z][A-Za-z \.]*?)(?=[,.\n]|$))?", re.IGNORECASE),
    re.compile(r"\b(IPC|CrPC|BNS|BSA)\s+(\d+[A-Za-z]*)\b", re.IGNORECASE),
    re.compile(r"\bArticle\s+(\d+[A-Za-z]*)\b", re.IGNORECASE),
]

# Matches "Party Name v. Other Party" / "vs." style case-name mentions.
# Deliberately excludes "(" / ")" from the allowed characters so a trailing
# citation like "... Diseases (2024 INSC 410)" doesn't get swallowed into
# the captured name (that broke the substring match against the real case
# name). Words after the leading capital may be lowercase (e.g. "Bar of
# Indian Lawyers through its President ...") since real case names often
# contain connector words that aren't themselves capitalized.
_CASE_NAME_PATTERN = re.compile(
    r"\b([A-Z][A-Za-z.&'\-]*(?:\s+[A-Za-z.&'\-]+)*\s+v\.?s?\.?\s+[A-Z][A-Za-z.&'\-]*(?:\s+[A-Za-z.&'\-]+)*)"
)

# Normalizes both act names typed in a generated answer ("the Consumer
# Protection Act", "IPC", "Bharatiya Sakshya Adhiniyam") and the `act` field
# stored on our own citations ("Consumer Protection Act", "BSA") down to one
# canonical key, so the two can be compared even when phrased differently.
_ACT_ALIASES = {
    "ipc": "ipc",
    "indianpenalcode": "ipc",
    "indianpenalcode1860": "ipc",
    "crpc": "crpc",
    "codeofcriminalprocedure": "crpc",
    "codeofcriminalprocedure1973": "crpc",
    "bns": "bns",
    "bharatiyanyayasanhita": "bns",
    "bharatiyanyayasanhita2023": "bns",
    "bsa": "bsa",
    "bharatiyasakshyaadhiniyam": "bsa",
    "bharatiyasakshyaadhiniyam2023": "bsa",
    "constitution": "constitution",
    "constitutionofindia": "constitution",
    "cpa": "cpa",
    "consumerprotectionact": "cpa",
    "consumerprotectionact2019": "cpa",
    "rti": "rti",
    "rtiact": "rti",
    "righttoinformationact": "rti",
    "righttoinformationact2005": "rti",
    "bnss": "bnss",
    "bharatiyanagariksurakshasanhita": "bnss",
    "bharatiyanagariksurakshasanhita2023": "bnss",
    "tpa": "tpa",
    "transferofpropertyact": "tpa",
    "transferofpropertyact1882": "tpa",
    "tamilnadutenancyact": "tnta",
    "tamilnadutenancyact2017": "tnta",
    "tamilnaduregulationofrightsandresponsibilitiesoflandlordsandtenantsact": "tnta",
    "tamilnaduregulationofrightsandresponsibilitiesoflandlordsandtenantsact2017": "tnta",
}


def _normalize_act(raw: str) -> str:
    if not raw:
        return ""
    key = re.sub(r"[^a-z0-9]", "", raw.lower())
    return _ACT_ALIASES.get(key, key)


def _extract_referenced_sections(answer: str) -> List[Tuple[str, Optional[str], str]]:
    """Return a de-duplicated list of (number, normalized_act_or_None, human-readable label)."""
    found = []

    for match in _SECTION_PATTERNS[0].finditer(answer):
        number, act = match.groups()
        act = (act or "").strip() or None
        label = f"Section {number}" + (f" of {act}" if act else "")
        found.append((number.upper(), _normalize_act(act) if act else None, label))

    for match in _SECTION_PATTERNS[1].finditer(answer):
        act, number = match.groups()
        found.append((number.upper(), _normalize_act(act), f"{act.upper()} {number}"))

    for match in _SECTION_PATTERNS[2].finditer(answer):
        number = match.group(1)
        found.append((number.upper(), "constitution", f"Article {number}"))

    seen = set()
    unique = []
    for number, act, label in found:
        key = (number, act)
        if key not in seen:
            seen.add(key)
            unique.append((number, act, label))
    return unique


def _extract_referenced_cases(answer: str) -> List[str]:
    """Return de-duplicated raw text of 'X v. Y'-style case-name mentions found in the answer."""
    found = []
    seen = set()
    for match in _CASE_NAME_PATTERN.finditer(answer):
        text = match.group(1).strip()
        key = text.lower()
        if key not in seen:
            seen.add(key)
            found.append(text)
    return found


def _case_is_cited(mentioned: str, cited_case_names: List[str]) -> bool:
    """Loose match: the mentioned span and a cited case name overlap substantially.

    Case names in answers are rarely typed identically to the source ("Imperia
    Structures v. Anil Patni" vs the full "Imperia Structures Ltd. v. Anil
    Patni"), so this checks whether one contains the other rather than
    requiring an exact string match.
    """
    mentioned_lower = mentioned.lower()
    for cited in cited_case_names:
        cited_lower = cited.lower()
        if mentioned_lower in cited_lower or cited_lower in mentioned_lower:
            return True
    return False


def hallucination_check(
    answer: str,
    act_citations: List[dict],
    case_citations: List[dict] = None,
) -> List[str]:
    """
    Returns a list of human-readable section/case references that appear in
    `answer` but are NOT backed by any entry in `act_citations`/`case_citations`.
    A section number attributed to the wrong act (e.g. real IPC section 302
    described as being "of the Consumer Protection Act") is flagged even
    though the number alone is real.
    """
    case_citations = case_citations or []

    cited_numbers = set()
    cited_pairs = set()
    for c in act_citations:
        section_id = str(c.get("section_id", ""))
        act_key = _normalize_act(str(c.get("act", "")))
        digits = re.findall(r"\d+[A-Za-z]*", section_id)
        for d in digits:
            cited_numbers.add(d.upper())
            if act_key:
                cited_pairs.add((d.upper(), act_key))

    cited_case_names = [str(c.get("case_name", "")) for c in case_citations if c.get("case_name")]

    flags = []

    for number, act, label in _extract_referenced_sections(answer):
        if act is None:
            # No act specified in the answer text — can only check the number.
            if number not in cited_numbers:
                flags.append(label)
        elif (number, act) not in cited_pairs:
            flags.append(label)

    for mentioned in _extract_referenced_cases(answer):
        if not _case_is_cited(mentioned, cited_case_names):
            flags.append(mentioned)

    return flags
