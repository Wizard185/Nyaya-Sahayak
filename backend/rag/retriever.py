"""
Hybrid retrieval over the local legal corpus.

Combines:
  - Dense retrieval (BGE-M3 embeddings against a Pinecone index)
  - Sparse retrieval (BM25Okapi over the same corpus, kept local — no
    external dependency for this half of the search)
  - Reciprocal Rank Fusion (RRF) to merge the two ranked lists.
"""
import json
import os
import re
from typing import Dict, List

from rank_bm25 import BM25Okapi

from rag.embedder import get_embedder
from rag.indexer import get_pinecone_index

_CORPUS_DIR = os.path.join(os.path.dirname(__file__), "..", "corpus")
_ONTOLOGY_PATH = os.path.join(_CORPUS_DIR, "ontology.json")
_BM25_CORPUS_PATH = os.path.join(_CORPUS_DIR, "bm25_corpus.json")

_TOKEN_RE = re.compile(r"[a-zA-Z0-9]+")

# Common English words filtered out of BM25 tokens so that generic
# question phrasing ("what is...") doesn't outweigh the legal terms
# (section numbers, act names) that actually distinguish documents.
_STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "what", "which", "who", "whom", "this", "that", "these", "those",
    "am", "i", "you", "he", "she", "it", "we", "they", "and", "or", "but",
    "if", "then", "so", "as", "of", "at", "by", "for", "with", "about",
    "against", "between", "into", "through", "during", "before", "after",
    "above", "below", "to", "from", "up", "down", "in", "out", "on", "off",
    "over", "under", "again", "further", "once", "here", "there", "when",
    "where", "why", "how", "all", "any", "both", "each", "few", "more",
    "most", "other", "some", "such", "no", "nor", "not", "only", "own",
    "same", "than", "too", "very", "can", "will", "just", "do", "does",
    "did", "doing", "has", "have", "had", "having", "my", "your", "his",
    "her", "its", "our", "their", "me", "him", "them",
}


def _tokenize(text: str) -> List[str]:
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS]


class HybridRetriever:
    def __init__(self):
        self._pinecone_index = None
        self._bm25 = None
        self._bm25_ids: List[str] = []
        self._bm25_texts: List[str] = []
        self._metadata_by_id: Dict[str, dict] = {}
        self._load_sparse_corpus()

    @property
    def pinecone_index(self):
        if self._pinecone_index is None:
            self._pinecone_index = get_pinecone_index()
        return self._pinecone_index

    def _load_sparse_corpus(self):
        """Build the BM25 index from bm25_corpus.json (falls back to ontology.json)."""
        self._metadata_by_id = {}

        if os.path.exists(_BM25_CORPUS_PATH):
            with open(_BM25_CORPUS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._bm25_ids = data.get("ids", [])
            self._bm25_texts = data.get("texts", [])
            metadatas = data.get("metadatas", [])
            for section_id, meta in zip(self._bm25_ids, metadatas):
                self._metadata_by_id[section_id] = meta
        elif os.path.exists(_ONTOLOGY_PATH):
            with open(_ONTOLOGY_PATH, "r", encoding="utf-8") as f:
                ontology = json.load(f)
            for section_id, entry in ontology.items():
                self._bm25_ids.append(section_id)
                self._bm25_texts.append(entry.get("text", entry.get("title", "")))
        else:
            self._bm25_ids = []
            self._bm25_texts = []

        if self._bm25_texts:
            tokenized = [_tokenize(t) for t in self._bm25_texts]
            self._bm25 = BM25Okapi(tokenized)

        # ontology.json enriches/overrides metadata (adds cross_refs, curated titles)
        if os.path.exists(_ONTOLOGY_PATH):
            with open(_ONTOLOGY_PATH, "r", encoding="utf-8") as f:
                ontology = json.load(f)
            for section_id, entry in ontology.items():
                self._metadata_by_id.setdefault(section_id, {})
                self._metadata_by_id[section_id].update(entry)

    def reload(self):
        """Re-read corpus files and rebuild the BM25 index (e.g. after ingest)."""
        self._bm25 = None
        self._bm25_ids = []
        self._bm25_texts = []
        self._metadata_by_id = {}
        self._load_sparse_corpus()

    def _dense_search(self, query: str, n: int = 10) -> List[dict]:
        embedder = get_embedder()
        query_vec = embedder.encode_one(query)
        response = self.pinecone_index.query(vector=query_vec, top_k=n, include_metadata=True)
        hits = []
        for match in response.get("matches", []):
            meta = match.get("metadata") or {}
            hits.append({
                "id": match["id"],
                "text": meta.get("text", ""),
                "section_id": meta.get("section_id", match["id"]),
                "act": meta.get("act", ""),
                "title": meta.get("title", ""),
            })
        return hits

    def _sparse_search(self, query: str, n: int = 10) -> List[dict]:
        if not self._bm25 or not self._bm25_ids:
            return []
        tokens = _tokenize(query)
        scores = self._bm25.get_scores(tokens)
        ranked_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:n]
        hits = []
        for idx in ranked_indices:
            section_id = self._bm25_ids[idx]
            text = self._bm25_texts[idx]
            meta = self._metadata_by_id.get(section_id, {})
            hits.append({
                "id": section_id,
                "text": text,
                "section_id": section_id,
                "act": meta.get("act", ""),
                "title": meta.get("title", ""),
            })
        return hits

    @staticmethod
    def _reciprocal_rank_fusion(dense_hits: List[dict], sparse_hits: List[dict], k: int = 60) -> List[dict]:
        """Fuse two ranked lists using RRF: score = sum(1 / (k + rank))."""
        scores: Dict[str, float] = {}
        doc_lookup: Dict[str, dict] = {}

        for rank, hit in enumerate(dense_hits):
            key = hit["section_id"]
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
            doc_lookup[key] = hit

        for rank, hit in enumerate(sparse_hits):
            key = hit["section_id"]
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
            doc_lookup.setdefault(key, hit)

        fused = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        results = []
        for key, score in fused:
            doc = doc_lookup[key]
            results.append({
                "text": doc["text"],
                "section_id": doc["section_id"],
                "act": doc["act"],
                "title": doc["title"],
                "score": score,
            })
        return results

    def get_hybrid_results(self, query: str, n: int = 6) -> List[dict]:
        dense_hits = self._dense_search(query, n=10)
        sparse_hits = self._sparse_search(query, n=10)
        fused = self._reciprocal_rank_fusion(dense_hits, sparse_hits, k=60)
        return fused[:n]


_retriever_singleton = None


def get_retriever() -> HybridRetriever:
    global _retriever_singleton
    if _retriever_singleton is None:
        _retriever_singleton = HybridRetriever()
    return _retriever_singleton
