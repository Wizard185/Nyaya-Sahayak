"""
Developer-only ingestion routes: run corpus (re-)embedding into Pinecone.

Never linked from the frontend. Protected by a static admin key so it isn't
just an open unauthenticated route sitting on the API — set ADMIN_API_KEY in
.env and pass it as the `X-Admin-Key` header.
"""
import os

from fastapi import APIRouter, Header, HTTPException

router = APIRouter(prefix="/admin", tags=["admin"])

ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "")


def _require_admin(x_admin_key: str = Header(default="")):
    if not ADMIN_API_KEY or x_admin_key != ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid or missing admin key.")


@router.post("/ingest/corpus")
def ingest_corpus(x_admin_key: str = Header(default="")):
    _require_admin(x_admin_key)

    from corpus.ingest import run_full_ingest
    from rag.retriever import get_retriever

    result = run_full_ingest()
    get_retriever().reload()

    return {"status": "ok", **result}


@router.get("/ingest/status")
def ingest_status(x_admin_key: str = Header(default="")):
    _require_admin(x_admin_key)

    from rag.retriever import get_retriever

    retriever = get_retriever()
    try:
        stats = retriever.pinecone_index.describe_index_stats()
        namespaces = stats.get("namespaces", {})
        vector_count = stats.get("total_vector_count", 0)
    except Exception as e:
        namespaces = {}
        vector_count = f"error: {e}"

    return {
        "pinecone_vector_count": vector_count,
        "pinecone_namespaces": namespaces,
        "bm25_acts_loaded": len(retriever._acts_sparse.ids),
        "bm25_cases_loaded": len(retriever._cases_sparse.ids),
    }
