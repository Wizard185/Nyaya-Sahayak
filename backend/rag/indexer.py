"""
Corpus ingestion into Pinecone with dynamic vector dimension resolution.
"""
import os
from typing import List, Optional

from pinecone import Pinecone, ServerlessSpec
from rag.embedder import get_embedder

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "nyaya-sahayak-statutes")
PINECONE_CLOUD = os.getenv("PINECONE_CLOUD", "aws")
PINECONE_REGION = os.getenv("PINECONE_REGION", "us-east-1")

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


def build_index_text(section: dict) -> str:
    section_id = section["section_id"]
    number = section_id.split("_", 1)[1] if "_" in section_id else section_id
    return f"{section['act']} Section {number}: {section['title']}. {section['text']}"


def index_sections(sections: List[dict]) -> int:
    index = get_pinecone_index()
    embedder = get_embedder()
    texts = [build_index_text(s) for s in sections]
    embeddings = embedder.encode(texts)

    vectors = [
        {
            "id": s["section_id"],
            "values": emb,
            "metadata": {
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
        index.upsert(vectors=vectors[i : i + batch_size])

    return len(sections)