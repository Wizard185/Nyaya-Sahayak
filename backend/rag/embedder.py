"""
Singleton wrapper around the BAAI/bge-m3 sentence embedding model.
Ensures the (large) model is loaded into memory only once per process.
"""
import threading
from typing import List

import numpy as np
from sentence_transformers import SentenceTransformer

_MODEL_NAME = "BAAI/bge-m3"


class Embedder:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._model = SentenceTransformer(_MODEL_NAME)
                    cls._instance = instance
        return cls._instance

    def encode(self, texts: List[str]) -> np.ndarray:
        """Encode a list of strings into L2-normalized embedding vectors."""
        if not texts:
            return np.zeros((0, self._model.get_sentence_embedding_dimension()))
        embeddings = self._model.encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return embeddings

    def encode_one(self, text: str) -> List[float]:
        return self.encode([text])[0].tolist()


_embedder_singleton = None


def get_embedder() -> Embedder:
    global _embedder_singleton
    if _embedder_singleton is None:
        _embedder_singleton = Embedder()
    return _embedder_singleton
