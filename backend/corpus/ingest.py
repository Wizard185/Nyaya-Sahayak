"""
One-time (or re-run-anytime) corpus ingestion script.

Reads two knowledge bases and embeds each into its own Pinecone namespace:
  - corpus/acts.json      -> "acts" namespace   (ACT KB: statute sections)
  - corpus/case_law.json  -> "cases" namespace  (CASE KB: landmark judgments)

Also builds the matching local BM25 sparse corpora (bm25_acts.json,
bm25_cases.json) so hybrid retrieval has something to search on the sparse
side for each knowledge base.

Run once (or after editing either JSON file) from the backend/ directory:
    python corpus/ingest.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv

load_dotenv()

from rag.indexer import (  # noqa: E402
    ACTS_NAMESPACE,
    CASES_NAMESPACE,
    build_case_index_text,
    build_index_text,
    clear_namespace,
    index_cases,
    index_sections,
)

_CORPUS_DIR = os.path.dirname(__file__)
_ACTS_PATH = os.path.join(_CORPUS_DIR, "acts.json")
_CASE_LAW_PATH = os.path.join(_CORPUS_DIR, "case_law.json")
_BM25_ACTS_OUTPUT_PATH = os.path.join(_CORPUS_DIR, "bm25_acts.json")
_BM25_CASES_OUTPUT_PATH = os.path.join(_CORPUS_DIR, "bm25_cases.json")


def run_full_ingest() -> dict:
    """(Re-)ingests both knowledge bases into Pinecone + writes the BM25 corpora.

    Idempotent: clears each namespace first, so editing acts.json/case_law.json
    and re-running never leaves stale vectors from a previous ingest behind.
    Shared by the CLI script (below) and the /admin/ingest/corpus route.
    """
    with open(_ACTS_PATH, "r", encoding="utf-8") as f:
        acts = json.load(f)
    with open(_CASE_LAW_PATH, "r", encoding="utf-8") as f:
        cases = json.load(f)

    embed_model = os.getenv("OLLAMA_EMBED_MODEL", "bge-m3")

    print(f"Clearing existing '{ACTS_NAMESPACE}' and '{CASES_NAMESPACE}' namespaces...")
    clear_namespace(ACTS_NAMESPACE)
    clear_namespace(CASES_NAMESPACE)

    print(f"Loaded {len(acts)} act sections from {_ACTS_PATH}.")
    print(f"Embedding acts with {embed_model} and upserting to Pinecone namespace '{ACTS_NAMESPACE}'...")
    acts_count = index_sections(acts)
    print(f"Indexed {acts_count} act sections.")

    print(f"Loaded {len(cases)} cases from {_CASE_LAW_PATH}.")
    print(f"Embedding case law with {embed_model} and upserting to Pinecone namespace '{CASES_NAMESPACE}'...")
    cases_count = index_cases(cases)
    print(f"Indexed {cases_count} cases.")

    print("Building BM25 sparse corpora...")
    acts_bm25 = {
        "ids": [s["section_id"] for s in acts],
        "texts": [build_index_text(s) for s in acts],
        "metadatas": [
            {"kind": "act", "section_id": s["section_id"], "act": s["act"], "title": s["title"]}
            for s in acts
        ],
    }
    with open(_BM25_ACTS_OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(acts_bm25, f, ensure_ascii=False, indent=2)
    print(f"Wrote BM25 acts corpus with {len(acts_bm25['ids'])} entries to {_BM25_ACTS_OUTPUT_PATH}.")

    cases_bm25 = {
        "ids": [c["case_id"] for c in cases],
        "texts": [build_case_index_text(c) for c in cases],
        "metadatas": [
            {
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
            }
            for c in cases
        ],
    }
    with open(_BM25_CASES_OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(cases_bm25, f, ensure_ascii=False, indent=2)
    print(f"Wrote BM25 cases corpus with {len(cases_bm25['ids'])} entries to {_BM25_CASES_OUTPUT_PATH}.")

    return {"acts_indexed": acts_count, "cases_indexed": cases_count}


def main():
    result = run_full_ingest()
    print(f"\nIngestion complete: {result['acts_indexed']} acts + {result['cases_indexed']} cases indexed.")
    print("You can now start the backend with:")
    print("    uvicorn main:app --reload --port 8000")


if __name__ == "__main__":
    main()
