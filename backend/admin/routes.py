"""
Developer-only ingestion routes: run corpus (re-)embedding into Pinecone.

Never linked from the frontend. Protected by a static admin key so it isn't
just an open unauthenticated route sitting on the API — set ADMIN_API_KEY in
.env and pass it as the `X-Admin-Key` header.
"""
import json
import os

from fastapi import APIRouter, Header, HTTPException

router = APIRouter(prefix="/admin", tags=["admin"])

ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "")

_CORPUS_DIR = os.path.join(os.path.dirname(__file__), "..", "corpus")
_SAMPLE_PATH = os.path.join(_CORPUS_DIR, "sample_ipc.json")
_BM25_OUTPUT_PATH = os.path.join(_CORPUS_DIR, "bm25_corpus.json")


def _require_admin(x_admin_key: str = Header(default="")):
    if not ADMIN_API_KEY or x_admin_key != ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid or missing admin key.")


@router.post("/ingest/corpus")
def ingest_corpus(x_admin_key: str = Header(default="")):
    _require_admin(x_admin_key)

    from rag.indexer import build_index_text, index_sections
    from rag.retriever import get_retriever

    with open(_SAMPLE_PATH, "r", encoding="utf-8") as f:
        sections = json.load(f)

    count = index_sections(sections)

    bm25_data = {
        "ids": [s["section_id"] for s in sections],
        "texts": [build_index_text(s) for s in sections],
        "metadatas": [
            {"section_id": s["section_id"], "act": s["act"], "title": s["title"]}
            for s in sections
        ],
    }
    with open(_BM25_OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(bm25_data, f, ensure_ascii=False, indent=2)

    get_retriever().reload()

    return {"status": "ok", "sections_indexed": count}


@router.get("/ingest/status")
def ingest_status(x_admin_key: str = Header(default="")):
    _require_admin(x_admin_key)

    from rag.retriever import get_retriever

    retriever = get_retriever()
    try:
        stats = retriever.pinecone_index.describe_index_stats()
        vector_count = stats.get("total_vector_count", 0)
    except Exception as e:
        vector_count = f"error: {e}"

    return {
        "pinecone_vector_count": vector_count,
        "bm25_sections_loaded": len(retriever._bm25_ids),
    }
