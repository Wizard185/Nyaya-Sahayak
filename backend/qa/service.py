"""
Shared async QA pipeline: translate-in -> hybrid retrieval -> LLM generation
-> hallucination check -> translate-out.

Every blocking step (translation, Pinecone/BM25 retrieval, Ollama generation)
runs off the event loop via asyncio.to_thread and is wrapped in its own
asyncio.wait_for + try/except, so a failure anywhere produces a specific,
actionable HTTPException detail instead of a generic frontend catch-all.
"""
import asyncio
import os
from typing import Dict, List

from fastapi import HTTPException

from llm.generator import decide_clarification, generate_answer
from multilingual.translator import (
    detect_language,
    translate_from_english,
    translate_to_english,
)
from rag.retriever import get_retriever
from rag.verifier import hallucination_check

RETRIEVAL_TIMEOUT_SECONDS = float(os.getenv("RETRIEVAL_TIMEOUT_SECONDS", "8"))
GENERATION_TIMEOUT_SECONDS = float(os.getenv("GENERATION_TIMEOUT_SECONDS", "25"))
TRANSLATION_TIMEOUT_SECONDS = float(os.getenv("TRANSLATION_TIMEOUT_SECONDS", "6"))


async def _translate_to_english(text: str, source_lang: str) -> str:
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(translate_to_english, text, source_lang),
            timeout=TRANSLATION_TIMEOUT_SECONDS,
        )
    except Exception:
        # translate_to_english already falls back to the original text on
        # internal errors; a hard timeout here just means "use as-is".
        return text


async def _translate_from_english(text: str, target_lang: str) -> str:
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(translate_from_english, text, target_lang),
            timeout=TRANSLATION_TIMEOUT_SECONDS,
        )
    except Exception:
        return text


def _retrieval_query(query_en: str, history: List[dict]) -> str:
    """
    A reply to follow-up questions ("he says I damaged the walls") retrieves
    poorly on its own, so search with every user message since the last full
    answer — i.e. the original question plus the replies.
    """
    pending = []
    for m in reversed(history):
        if m.get("role") == "assistant" and m.get("kind", "answer") == "answer":
            break
        if m.get("role") == "user":
            pending.append(m.get("content", ""))
    return " ".join(list(reversed(pending)) + [query_en])


async def run_qa(query: str, language: str = "auto", history: List[dict] = None) -> Dict:
    """
    `history` is the prior messages of this chat, oldest first, as
    {"role", "content" (English), "kind"} dicts.
    """
    if not query or not query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
    history = history or []

    # One round of follow-up questions per question: if the assistant just
    # asked some, this message is the user's reply and gets a full answer.
    last_assistant = next((m for m in reversed(history) if m.get("role") == "assistant"), None)
    allow_clarify = not (last_assistant and last_assistant.get("kind") == "clarification")

    detected = await asyncio.to_thread(detect_language, query) if language == "auto" else language
    working_lang = detected

    query_en = await _translate_to_english(query, working_lang)

    # Step 1: does the user's situation need follow-up questions first? A
    # failure or timeout here just means "answer straight away".
    if allow_clarify:
        try:
            questions_en = await asyncio.wait_for(
                asyncio.to_thread(decide_clarification, query_en, history),
                timeout=GENERATION_TIMEOUT_SECONDS,
            )
        except Exception:
            questions_en = None
        if questions_en:
            return {
                "answer": await _translate_from_english(questions_en, working_lang)
                if working_lang != "en"
                else questions_en,
                "answer_en": questions_en,
                "query_en": query_en,
                "kind": "clarification",
                "citations": [],
                "detected_language": detected,
                "hallucination_flags": [],
            }

    retriever = get_retriever()
    try:
        kb_results: Dict[str, List[dict]] = await asyncio.wait_for(
            asyncio.to_thread(retriever.get_hybrid_results_by_kb, _retrieval_query(query_en, history), 5, 2),
            timeout=RETRIEVAL_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail=f"Retrieval from the legal database (Pinecone) timed out after {RETRIEVAL_TIMEOUT_SECONDS:.0f}s. Check your internet connection and PINECONE_API_KEY.",
        )
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Could not reach the legal database (Pinecone). Check PINECONE_API_KEY and your internet connection. ({e})",
        )

    act_chunks = kb_results["acts"]
    case_chunks = kb_results["cases"]

    try:
        answer_en = await asyncio.wait_for(
            asyncio.to_thread(generate_answer, query_en, act_chunks, case_chunks, working_lang, history),
            timeout=GENERATION_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail=f"The AI model (Ollama) took longer than {GENERATION_TIMEOUT_SECONDS:.0f}s to respond. Try a shorter question, or check that Ollama is running with a fast model loaded.",
        )
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Could not reach the AI model. Is Ollama running at the configured OLLAMA_BASE_URL? ({e})",
        )

    act_citations = [
        {
            "kind": "act",
            "section_id": c["section_id"],
            "act": c["act"],
            "title": c["title"],
            "excerpt": (c["text"][:280] + "...") if len(c["text"]) > 280 else c["text"],
        }
        for c in act_chunks
    ]
    case_citations = [
        {
            "kind": "case",
            "case_id": c["case_id"],
            "case_name": c["case_name"],
            "citation": c["citation"],
            "court": c["court"],
            "act": c["act"],
            "excerpt": (c["summary"][:280] + "...") if len(c["summary"]) > 280 else c["summary"],
        }
        for c in case_chunks
    ]
    citations = act_citations + case_citations
    flags = hallucination_check(answer_en, act_citations, case_citations)

    final_answer = (
        await _translate_from_english(answer_en, working_lang)
        if working_lang != "en"
        else answer_en
    )

    return {
        "answer": final_answer,
        "answer_en": answer_en,
        "query_en": query_en,
        "kind": "answer",
        "citations": citations,
        "detected_language": detected,
        "hallucination_flags": flags,
    }
