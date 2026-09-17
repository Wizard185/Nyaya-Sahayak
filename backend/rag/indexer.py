"""
Corpus ingestion into Pinecone with dynamic vector dimension resolution.

Two knowledge bases live side by side in the same Pinecone index, kept apart
by namespace:
  - "acts"  — statute/section text (IPC, CrPC, BSA, Constitution, etc.)
  - "cases" — landmark case law (facts, issues, ratio decidendi, summary)

This mirrors the retrieval split of "what law applies" (ACT KB) vs "how has
it actually been applied" (CASE KB) — see rag/retriever.py.
"""
import os
from typing import List, Optional

from pinecone import Pinecone, ServerlessSpec
from rag.embedder import get_embedder

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "nyaya-sahayak-statutes")
PINECONE_CLOUD = os.getenv("PINECONE_CLOUD", "aws")
PINECONE_REGION = os.getenv("PINECONE_REGION", "us-east-1")

ACTS_NAMESPACE = "acts"
CASES_NAMESPACE = "cases"

_pc_client: Optional[Pinecone] = None


def get_pinecone_client() -> Pinecone:
    global _pc_client
    if _pc_client is None:
        if not PINECONE_API_KEY:
            raise RuntimeError("PINECONE_API_KEY is not set in environment variables.")
        _pc_client = Pinecone(api_key=PINECONE_API_KEY)
    return _pc_client


def get_pinecone_index():
    pc = get_pinecone_client()
    existing = {idx["name"] for idx in pc.list_indexes()}

    if PINECONE_INDEX_NAME not in existing:
        # Dynamically determine the dimension directly from the configured embedding model
        dimension = get_embedder().get_dimension()
        pc.create_index(
            name=PINECONE_INDEX_NAME,
            dimension=dimension,
            metric="cosine",
            spec=ServerlessSpec(cloud=PINECONE_CLOUD, region=PINECONE_REGION),
        )

    return pc.Index(PINECONE_INDEX_NAME)


def clear_namespace(namespace: str) -> None:
    """Delete every vector in a namespace so re-ingestion doesn't leave stale entries behind."""
    index = get_pinecone_index()
    try:
        index.delete(delete_all=True, namespace=namespace)
    except Exception:
        # A namespace that doesn't exist yet (fresh index, or nothing ever
        # ingested into it) raises on some Pinecone client versions — safe
        # to ignore, there's nothing to clear.
        pass


def build_index_text(section: dict) -> str:
    section_id = section["section_id"]
    number = section_id.split("_", 1)[1] if "_" in section_id else section_id
    return f"{section['act']} Section {number}: {section['title']}. {section['text']}"


def index_sections(sections: List[dict]) -> int:
    """Embed + upsert statute sections into the 'acts' namespace (the ACT KB)."""
    index = get_pinecone_index()
    embedder = get_embedder()
    texts = [build_index_text(s) for s in sections]
    embeddings = embedder.encode(texts)

    vectors = [
        {
            "id": s["section_id"],
            "values": emb,
            "metadata": {
                "kind": "act",
                "section_id": s["section_id"],
                "act": s["act"],
                "title": s["title"],
                "text": text,
            },
        }
        for s, text, emb in zip(sections, texts, embeddings)
    ]

    batch_size = 100
    for i in range(0, len(vectors), batch_size):
        index.upsert(vectors=vectors[i : i + batch_size], namespace=ACTS_NAMESPACE)

    return len(sections)


def build_case_index_text(case: dict) -> str:
    """Combine the fields that actually make a case findable by a natural-language question."""
    sections = ", ".join(case.get("sections", []))
    issues = " ".join(case.get("issues", []))
    return (
        f"{case['case_name']} ({case.get('citation', '')}) — {case.get('court', '')}, {case.get('year', '')}.\n"
        f"Relevant law: {sections}\n"
        f"Issues: {issues}\n"
        f"Facts: {case.get('facts', '')}\n"
        f"Ratio decidendi: {case.get('ratio_decidendi', '')}\n"
        f"Summary: {case.get('summary', '')}"
    )


def index_cases(cases: List[dict]) -> int:
    """Embed + upsert landmark case law into the 'cases' namespace (the CASE KB)."""
    index = get_pinecone_index()
    embedder = get_embedder()
    texts = [build_case_index_text(c) for c in cases]
    embeddings = embedder.encode(texts)

    vectors = [
        {
            "id": c["case_id"],
            "values": emb,
            "metadata": {
                "kind": "case",
                "case_id": c["case_id"],
                "case_name": c["case_name"],
                "citation": c.get("citation", ""),
                "court": c.get("court", ""),
                "year": c.get("year", ""),
                "act": c.get("act", ""),
                "sections": c.get("sections", []),
                "ratio_decidendi": c.get("ratio_decidendi", ""),
                "summary": c.get("summary", ""),
                "text": text,
            },
        }
        for c, text, emb in zip(cases, texts, embeddings)
    ]

    batch_size = 100
    for i in range(0, len(vectors), batch_size):
        index.upsert(vectors=vectors[i : i + batch_size], namespace=CASES_NAMESPACE)

    return len(cases)
