"""
One-time corpus ingestion script.

Reads corpus/sample_ipc.json, embeds every section with BGE-M3, and upserts
the vectors + metadata into the Pinecone "statutes" index (PINECONE_API_KEY
must be set in .env). Also builds corpus/bm25_corpus.json so the sparse
(BM25) side of hybrid retrieval has a matching corpus to search over.

Run once from the backend/ directory:
    python corpus/ingest.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv

load_dotenv()

from rag.indexer import build_index_text, index_sections  # noqa: E402

_CORPUS_DIR = os.path.dirname(__file__)
_SAMPLE_PATH = os.path.join(_CORPUS_DIR, "sample_ipc.json")
_BM25_OUTPUT_PATH = os.path.join(_CORPUS_DIR, "bm25_corpus.json")


def main():
    print(f"Loading corpus from {_SAMPLE_PATH} ...")
    with open(_SAMPLE_PATH, "r", encoding="utf-8") as f:
        sections = json.load(f)
    print(f"Loaded {len(sections)} sections.")

    print("Embedding sections with BAAI/bge-m3 and upserting to Pinecone (this may take a minute the first time)...")
    count = index_sections(sections)
    print(f"Indexed {count} sections into the Pinecone index.")

    print("Building BM25 sparse corpus file...")
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
    print(f"Wrote BM25 corpus with {len(bm25_data['ids'])} entries to {_BM25_OUTPUT_PATH}.")

    print("\nIngestion complete. You can now start the backend with:")
    print("    uvicorn main:app --reload --port 8000")


if __name__ == "__main__":
    main()
