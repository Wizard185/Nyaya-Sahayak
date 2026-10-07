"""
Hybrid retrieval over two separate knowledge bases:

  USER QUERY -> RETRIEVER -> ACT KB   ("what law applies?")
                           -> CASE KB  ("how has it been applied?" -> similar
                                        cases / precedents)

Each side combines:
  - Dense retrieval (Ollama embeddings against its own Pinecone namespace)
  - Sparse retrieval (BM25Okapi over its own local JSON corpus)
  - Reciprocal Rank Fusion (RRF) to merge the two ranked lists

Both result sets are handed to the LLM together so it can answer with both
the governing law and how courts have actually applied it.
"""
import json
import os
import re
from typing import Dict, List

from rank_bm25 import BM25Okapi

from rag.embedder import get_embedder
from rag.indexer import ACTS_NAMESPACE, CASES_NAMESPACE, get_pinecone_index

_CORPUS_DIR = os.path.join(os.path.dirname(__file__), "..", "corpus")
_ONTOLOGY_PATH = os.path.join(_CORPUS_DIR, "ontology.json")
_BM25_ACTS_PATH = os.path.join(_CORPUS_DIR, "bm25_acts.json")
_BM25_CASES_PATH = os.path.join(_CORPUS_DIR, "bm25_cases.json")

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


class _SparseIndex:
    """A single BM25 index + id/text/metadata store, loaded from one bm25_*.json file."""

    def __init__(self, path: str):
        self.ids: List[str] = []
        self.texts: List[str] = []
        self.metadata_by_id: Dict[str, dict] = {}
        self.bm25 = None
        self._load(path)

    def _load(self, path: str):
        if not os.path.exists(path):
            return
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.ids = data.get("ids", [])
        self.texts = data.get("texts", [])
        metadatas = data.get("metadatas", [])
        for doc_id, meta in zip(self.ids, metadatas):
            self.metadata_by_id[doc_id] = meta
        if self.texts:
            self.bm25 = BM25Okapi([_tokenize(t) for t in self.texts])

    def search(self, query: str, n: int) -> List[dict]:
        if not self.bm25 or not self.ids:
            return []
        tokens = _tokenize(query)
        scores = self.bm25.get_scores(tokens)
        ranked_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:n]
        hits = []
        for idx in ranked_indices:
            doc_id = self.ids[idx]
            meta = dict(self.metadata_by_id.get(doc_id, {}))
            meta["id"] = doc_id
            meta.setdefault("text", self.texts[idx])
            hits.append(meta)
        return hits



# The corpus is heavily skewed toward BSA (evidence-law boilerplate: "Opinion
# as to X, when relevant" repeated dozens of times) and CPA (mostly short
# generic definitions). Both flood BM25 with keyword collisions on common
# words ("opinion", "relevant", "government") regardless of what the query
# is actually about, badly outranking the real answer in the sparse list.
# Dense (embedding) search doesn't have this problem to nearly the same
# degree, so it's weighted far more heavily in the fusion — sparse still
# contributes (helps exact-term lookups like a specific section number) but
# can no longer single-handedly drag an off-topic BSA/CPA section to the
# top. Tuned empirically against a small set of known-answer test queries
# (see the KB-quality test notes) — 10:1 fixed 4/5 known failures without
# regressing anything that was already correct. Raised further to 80:1
# after adding BNSS (560 total act sections) reintroduced a similar failure
# for the thin 5-section RTI Act getting edged out by BSA on both dense
# (close second) and sparse; 80:1 fixed that too with no further
# regressions found. This is a coarse, empirically-tuned knob, not a
# principled fix — a proper fix would be a reranking stage or trimming the
# still-oversized BSA/CPA sections (see corpus-quality notes) rather than
# pushing this weight indefinitely higher every time a new thin act is added.
_DENSE_WEIGHT = 80.0
_SPARSE_WEIGHT = 1.0


def _reciprocal_rank_fusion(dense_hits: List[dict], sparse_hits: List[dict], k: int = 60) -> List[dict]:
    """Fuse two ranked lists (each a list of metadata dicts with an 'id' key) using weighted RRF."""
    scores: Dict[str, float] = {}
    doc_lookup: Dict[str, dict] = {}

    for rank, hit in enumerate(dense_hits):
        key = hit["id"]
        scores[key] = scores.get(key, 0.0) + _DENSE_WEIGHT / (k + rank + 1)
        doc_lookup[key] = hit

    for rank, hit in enumerate(sparse_hits):
        key = hit["id"]
        scores[key] = scores.get(key, 0.0) + _SPARSE_WEIGHT / (k + rank + 1)
        doc_lookup.setdefault(key, hit)

    fused = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    results = []
    for key, score in fused:
        doc = dict(doc_lookup[key])
        doc["score"] = score
        results.append(doc)
    return results


# State laws only apply in their state. Without this, a deposit question from
# anywhere in India pulls in Tamil Nadu tenancy sections (they match "security
# deposit" best) and crowds out the central Transfer of Property Act.
_STATE_ACT_KEYWORDS = {
    "Tamil Nadu Tenancy Act": re.compile(
        r"tamil\s*nadu|\bTN\b|chennai|madras|coimbatore|madurai|tiruchirappalli|trichy|salem|tirunelveli|vellore|erode|tiruppur",
        re.IGNORECASE,
    ),
}


def _state_act_applies(act: str, query: str) -> bool:
    pattern = _STATE_ACT_KEYWORDS.get(act)
    return pattern is None or bool(pattern.search(query))


class HybridRetriever:
    def __init__(self):
        self._pinecone_index = None
        self._acts_sparse = _SparseIndex(_BM25_ACTS_PATH)
        self._cases_sparse = _SparseIndex(_BM25_CASES_PATH)
        self._act_ontology: Dict[str, dict] = {}
        self._load_ontology()

    @property
    def pinecone_index(self):
        if self._pinecone_index is None:
            self._pinecone_index = get_pinecone_index()
        return self._pinecone_index

    # kept for the /admin/ingest/status route, which reports how many BM25
    # rows are loaded
    @property
    def _bm25_ids(self) -> List[str]:
        return self._acts_sparse.ids + self._cases_sparse.ids

    def _load_ontology(self):
        """ontology.json enriches/overrides act metadata (adds cross_refs, curated titles)."""
        self._act_ontology = {}
        if os.path.exists(_ONTOLOGY_PATH):
            with open(_ONTOLOGY_PATH, "r", encoding="utf-8") as f:
                self._act_ontology = json.load(f)

    def reload(self):
        """Re-read corpus files and rebuild both BM25 indexes (e.g. after ingest)."""
        self._acts_sparse = _SparseIndex(_BM25_ACTS_PATH)
        self._cases_sparse = _SparseIndex(_BM25_CASES_PATH)
        self._load_ontology()

    def _dense_search(self, query: str, namespace: str, n: int) -> List[dict]:
        embedder = get_embedder()
        query_vec = embedder.encode_one(query)
        response = self.pinecone_index.query(
            vector=query_vec, top_k=n, include_metadata=True, namespace=namespace
        )
        hits = []
        for match in response.get("matches", []):
            meta = dict(match.get("metadata") or {})
            meta["id"] = match["id"]
            hits.append(meta)
        return hits

    def _act_hit(self, doc: dict) -> dict:
        section_id = doc.get("section_id", doc.get("id", ""))
        enrichment = self._act_ontology.get(section_id, {})
        return {
            "kind": "act",
            "section_id": section_id,
            "act": doc.get("act", ""),
            "title": enrichment.get("title", doc.get("title", "")),
            "text": doc.get("text", ""),
            "score": doc.get("score", 0.0),
        }

    @staticmethod
    def _case_hit(doc: dict) -> dict:
        return {
            "kind": "case",
            "case_id": doc.get("case_id", doc.get("id", "")),
            "case_name": doc.get("case_name", ""),
            "citation": doc.get("citation", ""),
            "court": doc.get("court", ""),
            "year": doc.get("year", ""),
            "act": doc.get("act", ""),
            "sections": doc.get("sections", []),
            "ratio_decidendi": doc.get("ratio_decidendi", ""),
            "summary": doc.get("summary", ""),
            "text": doc.get("text", doc.get("summary", "")),
            "score": doc.get("score", 0.0),
        }

    def search_acts(self, query: str, n: int = 6) -> List[dict]:
        """ACT KB: 'what law applies?' — statute/section text."""
        dense_hits = self._dense_search(query, ACTS_NAMESPACE, n=15)
        sparse_hits = self._acts_sparse.search(query, n=15)
        fused = _reciprocal_rank_fusion(dense_hits, sparse_hits, k=60)
        fused = [d for d in fused if _state_act_applies(d.get("act", ""), query)]
        return [self._act_hit(d) for d in fused[:n]]

    def search_cases(self, query: str, n: int = 3) -> List[dict]:
        """CASE KB: 'how was it used?' — similar cases / precedents."""
        dense_hits = self._dense_search(query, CASES_NAMESPACE, n=10)
        sparse_hits = self._cases_sparse.search(query, n=10)
        fused = _reciprocal_rank_fusion(dense_hits, sparse_hits, k=60)
        return [self._case_hit(d) for d in fused[:n]]

    def get_hybrid_results_by_kb(self, query: str, n_acts: int = 6, n_cases: int = 3) -> Dict[str, List[dict]]:
        """Retriever -> {acts: [...], cases: [...]}, matching the ACT KB / CASE KB split."""
        return {
            "acts": self.search_acts(query, n=n_acts),
            "cases": self.search_cases(query, n=n_cases),
        }


_retriever_singleton = None


def get_retriever() -> HybridRetriever:
    global _retriever_singleton
    if _retriever_singleton is None:
        _retriever_singleton = HybridRetriever()
    return _retriever_singleton
