"""
Optional single-call LLM polish for free-text "narrative" fields inside a
template-driven draft (e.g. "Grounds for Bail"). Structured fields are
substituted directly via docxtpl (see document_gen/template_engine.py) and
never touch the LLM at all — this keeps drafting fast and deterministic.
"""
from langchain_core.prompts import PromptTemplate

from llm.generator import get_llm
from llm.prompts import NARRATIVE_POLISH_PROMPT


def polish_narrative(raw_text: str, field_label: str) -> str:
    """Rewrites a user's rough notes into a formal paragraph. Falls back to
    the raw text unchanged if the LLM call fails or returns nothing usable."""
    if not raw_text or not raw_text.strip():
        return raw_text

    prompt = PromptTemplate(
        input_variables=["field_label", "raw_text"],
        template=NARRATIVE_POLISH_PROMPT,
    )
    llm = get_llm()
    chain = prompt | llm
    result = chain.invoke({"field_label": field_label, "raw_text": raw_text})
    result = result.strip() if isinstance(result, str) else str(result).strip()
    return result or raw_text
