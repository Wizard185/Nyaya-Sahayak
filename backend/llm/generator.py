"""
LangChain chain that wires a PromptTemplate to a locally-running Ollama model.
"""
import os
import re
from typing import List, Optional

from langchain_core.prompts import PromptTemplate
from langchain_ollama import OllamaLLM

from llm.prompts import CLARIFY_DECISION_PROMPT, QA_PROMPT

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
# Cap how many tokens the model can generate — the single biggest lever on
# response latency on CPU-only Windows/Ollama installs.
OLLAMA_NUM_PREDICT = int(os.getenv("OLLAMA_NUM_PREDICT", "400"))
# Keep the model resident in memory between requests so each call doesn't
# pay a fresh model-load cost.
OLLAMA_KEEP_ALIVE = os.getenv("OLLAMA_KEEP_ALIVE", "30m")
OLLAMA_REQUEST_TIMEOUT = float(os.getenv("OLLAMA_REQUEST_TIMEOUT", "20"))
# Ollama's default 4096-token window is too small once retrieved sections +
# chat history + the answer are included, and Ollama silently drops the
# *start* of an overlong prompt — i.e. the instructions.
OLLAMA_NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "8192"))

_llm_singleton = None


def get_llm() -> OllamaLLM:
    global _llm_singleton
    if _llm_singleton is None:
        _llm_singleton = OllamaLLM(
            model=OLLAMA_MODEL,
            base_url=OLLAMA_BASE_URL,
            num_predict=OLLAMA_NUM_PREDICT,
            keep_alive=OLLAMA_KEEP_ALIVE,
            timeout=OLLAMA_REQUEST_TIMEOUT,
            num_ctx=OLLAMA_NUM_CTX,
        )
    return _llm_singleton


_decider_singleton = None


def get_decider_llm() -> OllamaLLM:
    """Same model, tuned for the short ask-or-answer decision: deterministic
    (temperature 0) and capped to a few questions' worth of tokens."""
    global _decider_singleton
    if _decider_singleton is None:
        _decider_singleton = OllamaLLM(
            model=OLLAMA_MODEL,
            base_url=OLLAMA_BASE_URL,
            num_predict=200,
            temperature=0,
            keep_alive=OLLAMA_KEEP_ALIVE,
            timeout=OLLAMA_REQUEST_TIMEOUT,
            num_ctx=OLLAMA_NUM_CTX,
        )
    return _decider_singleton


# Long sections (e.g. TPA 108 is ~5,600 chars) make prompt processing the
# dominant cost on CPU. Above this length, only the clauses most relevant to
# the question are sent, in their original order.
_MAX_SECTION_CHARS = int(os.getenv("MAX_SECTION_CHARS", "1200"))
_CLAUSE_SPLIT_RE = re.compile(r"(?<=[;.:])\s*(?=\(?[a-z0-9]{1,4}\))|(?<=;)\s+")
_WORD_RE = re.compile(r"[a-z]{3,}")
_STOP = {"the", "and", "for", "that", "with", "any", "such", "shall", "which", "this", "from",
         "have", "has", "his", "her", "not", "are", "was", "may", "who", "what", "can", "under"}


def _relevant_excerpt(text: str, query: str) -> str:
    if len(text) <= _MAX_SECTION_CHARS:
        return text
    clauses = [c.strip() for c in _CLAUSE_SPLIT_RE.split(text) if c.strip()]
    # Crude stemming so "damaged" ~ "damage", "deposit" ~ "deposited".
    q_stems = {w[:5] for w in set(_WORD_RE.findall(query.lower())) - _STOP}

    def score(clause: str) -> int:
        return sum(1 for w in set(_WORD_RE.findall(clause.lower())) if w[:5] in q_stems)

    # Always keep the opening clause (it frames the section), then the best-scoring ones.
    keep, total = {0}, len(clauses[0])
    for i in sorted(range(1, len(clauses)), key=lambda i: score(clauses[i]), reverse=True):
        if score(clauses[i]) == 0 or total + len(clauses[i]) > _MAX_SECTION_CHARS:
            continue
        keep.add(i)
        total += len(clauses[i])
    return " ... ".join(clauses[i] for i in sorted(keep))


def _format_act_context(chunks: List[dict], query: str = "") -> str:
    if not chunks:
        return "No relevant statute sections were found."
    blocks = []
    for c in chunks:
        blocks.append(
            f"[{c.get('section_id', '')} - {c.get('act', '')}: {c.get('title', '')}]\n"
            f"{_relevant_excerpt(c.get('text', ''), query)}"
        )
    return "\n\n".join(blocks)


def _format_case_context(chunks: List[dict]) -> str:
    if not chunks:
        return "No directly relevant case law was found."
    blocks = []
    for c in chunks:
        blocks.append(
            f"[{c.get('case_name', '')} ({c.get('citation', '')}) - {c.get('court', '')}]\n"
            f"Ratio decidendi: {c.get('ratio_decidendi', '')}\n"
            f"Summary: {c.get('summary', '')}"
        )
    return "\n\n".join(blocks)


# How many prior messages of the chat are shown to the model — enough to
# cover a question, the follow-up questions and the user's replies, without
# bloating the prompt (and CPU latency) on long chats.
_HISTORY_MESSAGES = 6

# Matches the decision reply's leading verdict, tolerating markdown/quotes
# ("**ASK**", "Reply: ASK").
_DECISION_RE = re.compile(r"^\W*(?:reply\W*)?(ASK|ANSWER)\b\W*", re.IGNORECASE)
_QUESTION_RE = re.compile(r"^\s*\d+[.)]\s+\S")

# Follow-up questions only make sense when the user is describing their OWN
# situation. Small models over-ask on general questions ("How do I file an
# RTI?"), so this deterministic gate keeps those out of the decision call
# entirely (and saves a model call's worth of latency).
_PERSONAL_RE = re.compile(
    r"\b(my|me|mine|our|us)\b"
    r"|\bI\s+(?:was|am|have|had|got|did|paid|rented|bought|sold|lost|lent|gave|took|signed|moved|left|live|work|worked|received)\b"
    r"|\bI'(?:m|ve)\b",
    re.IGNORECASE,
)


def _format_history(history: List[dict]) -> str:
    if not history:
        return "(This is the start of the conversation.)"
    lines = []
    for m in history[-_HISTORY_MESSAGES:]:
        speaker = "User" if m.get("role") == "user" else "Assistant"
        lines.append(f"{speaker}: {m.get('content', '')}")
    return "\n\n".join(lines)


def decide_clarification(query: str, history: List[dict] = None) -> Optional[str]:
    """
    Asks the model whether `query` needs follow-up questions before it can be
    answered well. Returns the numbered questions as markdown, or None to
    answer straight away (also None on any unparseable reply — answering is
    the safe fallback).
    """
    if not _PERSONAL_RE.search(query):
        return None

    prompt = PromptTemplate(input_variables=["history", "question"], template=CLARIFY_DECISION_PROMPT)
    result = (prompt | get_decider_llm()).invoke(
        {"history": _format_history(history or []), "question": query}
    )
    text = (result if isinstance(result, str) else str(result)).strip()

    match = _DECISION_RE.match(text)
    if not match or match.group(1).upper() != "ASK":
        return None

    # Keep only the numbered questions — drops any stray commentary or a
    # hallucinated next "Message:" example the model may run on into.
    questions = []
    for line in text[match.end():].splitlines():
        if line.strip().lower().startswith("message:"):
            break
        if _QUESTION_RE.match(line):
            questions.append(line.strip())
    if not questions:
        return None
    return "Before I answer, I need a few details so I can give you advice that fits your situation:\n\n" + "\n".join(questions[:4])


def generate_answer(
    query: str,
    act_chunks: List[dict],
    case_chunks: List[dict] = None,
    language: str = "en",
    history: List[dict] = None,
) -> str:
    """
    Builds the QA chain (PromptTemplate | llm) and generates a plain-language
    answer for `query` using the retrieved ACT KB (`act_chunks`) and CASE KB
    (`case_chunks`) results plus the prior chat `history` (English).
    """
    prompt = PromptTemplate(
        input_variables=["act_context", "case_context", "history", "question"],
        template=QA_PROMPT,
    )
    llm = get_llm()
    chain = prompt | llm

    result = chain.invoke(
        {
            "act_context": _format_act_context(act_chunks, query),
            "case_context": _format_case_context(case_chunks or []),
            "history": _format_history(history or []),
            "question": query,
        }
    )
    return result.strip() if isinstance(result, str) else str(result).strip()
