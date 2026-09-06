"""
Dynamic Ollama embedder.
Reads configuration from environment variables and automatically detects
the vector dimension without hardcoded values.
"""
import os
from typing import List, Optional
import requests

class Embedder:
    _instance = None
    _dimension: Optional[int] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @property
    def base_url(self) -> str:
        return os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    @property
    def model(self) -> str:
        model_name = os.getenv("OLLAMA_EMBED_MODEL")
        if not model_name:
            raise ValueError("OLLAMA_EMBED_MODEL is not set in environment variables.")
        return model_name

    def encode(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        response = requests.post(
            f"{self.base_url}/api/embed",
            json={"model": self.model, "input": texts},
            timeout=120,
        )
        response.raise_for_status()

        embeddings = response.json().get("embeddings", [])
        if embeddings and self._dimension is None:
            self._dimension = len(embeddings[0])

        return embeddings

    def encode_one(self, text: str) -> List[float]:
        return self.encode([text])[0]

    def get_dimension(self) -> int:
        """Returns the embedding vector dimension by probing the model if not yet cached."""
        if self._dimension is None:
            self._dimension = len(self.encode_one("dimension_probe"))
        return self._dimension


_embedder_singleton = None


def get_embedder() -> Embedder:
    global _embedder_singleton
    if _embedder_singleton is None:
        _embedder_singleton = Embedder()
    return _embedder_singleton