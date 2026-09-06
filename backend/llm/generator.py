"""
LangChain chain that wires a PromptTemplate to a locally-running Ollama model.
"""
import os
from typing import List

from langchain_core.prompts import PromptTemplate
from langchain_ollama import OllamaLLM

from llm.prompts import QA_PROMPT

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
# Cap how many tokens the model can generate — the single biggest lever on
# response latency on CPU-only Windows/Ollama installs.
OLLAMA_NUM_PREDICT = int(os.getenv("OLLAMA_NUM_PREDICT", "400"))
# Keep the model resident in memory between requests so each call doesn't
# pay a fresh model-load cost.
OLLAMA_KEEP_ALIVE = os.getenv("OLLAMA_KEEP_ALIVE", "30m")
OLLAMA_REQUEST_TIMEOUT = float(os.getenv("OLLAMA_REQUEST_TIMEOUT", "20"))

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
        )
    return _llm_singleton


def _format_context(chunks: List[dict]) -> str:
    if not chunks:
        return "No relevant legal context was found."
    blocks = []
    for c in chunks:
        blocks.append(
            f"[{c.get('section_id', '')} - {c.get('act', '')}: {c.get('title', '')}]\n{c.get('text', '')}"
        )
    return "\n\n".join(blocks)


def generate_answer(query: str, context_chunks: List[dict], language: str = "en") -> str:
    """
    Builds the QA chain (PromptTemplate | llm) and generates a grounded
    answer for `query` using the retrieved `context_chunks`.
    """
    prompt = PromptTemplate(
        input_variables=["context", "question"],
        template=QA_PROMPT,
    )
    llm = get_llm()
    chain = prompt | llm

    context_text = _format_context(context_chunks)
    result = chain.invoke({"context": context_text, "question": query})
    return result.strip() if isinstance(result, str) else str(result).strip()
