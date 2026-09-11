import asyncio
import os
from typing import Dict, List

from fastapi import HTTPException

from llm.generator import generate_answer
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

LANG_MAP = {
    "hi": "hi",
    "ka": "kn",
    "kn": "kn",
    "en": "en",
    "mr": "hi",
    "ne": "hi"
}


async def _translate_to_english(text: str, source_lang: str) -> str:
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(translate_to_english, text, source_lang),
            timeout=TRANSLATION_TIMEOUT_SECONDS,
        )
    except Exception:
        return text


async def _translate_from_english(text: str, target_lang: str) -> str:
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(translate_from_english, text, target_lang),
            timeout=TRANSLATION_TIMEOUT_SECONDS,
        )
    except Exception:
        return text


async def run_qa(query: str, language: str = "auto") -> Dict:
    if not query or not query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    detected = await asyncio.to_thread(detect_language, query) if language == "auto" else language
    working_lang = LANG_MAP.get(detected, detected)

    query_en = await _translate_to_english(query, working_lang)

    retriever = get_retriever()
    try:
        chunks: List[dict] = await asyncio.wait_for(
            asyncio.to_thread(retriever.get_hybrid_results, query_en, 6),
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

    try:
        answer_en = await asyncio.wait_for(
            asyncio.to_thread(generate_answer, query_en, chunks, working_lang),
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

    citations = [
        {
            "section_id": c["section_id"],
            "act": c["act"],
            "title": c["title"],
            "excerpt": (c["text"][:280] + "...") if len(c["text"]) > 280 else c["text"],
        }
        for c in chunks
    ]

    flags = hallucination_check(answer_en, citations)

    final_answer = (
        await _translate_from_english(answer_en, working_lang)
        if working_lang != "en"
        else answer_en
    )

    return {
        "answer": final_answer,
        "citations": citations,
        "detected_language": detected,
        "hallucination_flags": flags,
    }