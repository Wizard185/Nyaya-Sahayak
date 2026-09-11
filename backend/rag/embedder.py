
import os
from typing import List

import requests
from huggingface_hub import InferenceClient


class Embedder:
    _instance = None
    _dimension = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @property
    def environment(self) -> str:
        return os.getenv("ENVIRONMENT", "development").lower()

    # ---------------------------------------------------------
    # Hugging Face
    # ---------------------------------------------------------

    def _encode_hf(self, texts: List[str]) -> List[List[float]]:
        hf_key = os.getenv("HF_API_KEY")

        if not hf_key:
            raise RuntimeError("HF_API_KEY is not set")

        hf_model = os.getenv(
            "HF_EMBED_MODEL",
            "sentence-transformers/all-MiniLM-L6-v2"
        )

        client = InferenceClient(
            provider="hf-inference",
            api_key=hf_key
        )

        embeddings = client.feature_extraction(
            texts,
            model=hf_model
        )

        # Convert numpy-like output if necessary
        return embeddings.tolist()

    # ---------------------------------------------------------
    # Ollama
    # ---------------------------------------------------------

    def _encode_ollama(self, texts: List[str]) -> List[List[float]]:
        ollama_url = os.getenv(
            "OLLAMA_BASE_URL",
            "http://localhost:11434"
        ).rstrip("/")

        ollama_model = os.getenv(
            "OLLAMA_EMBED_MODEL",
            "all-minilm"
        )

        response = requests.post(
            f"{ollama_url}/api/embed",
            json={
                "model": ollama_model,
                "input": texts
            },
            timeout=120
        )

        response.raise_for_status()

        data = response.json()

        embeddings = data.get("embeddings", [])

        if not embeddings:
            raise RuntimeError(
                f"Ollama returned no embeddings: {data}"
            )

        return embeddings

    # ---------------------------------------------------------
    # Main encode
    # ---------------------------------------------------------

    def encode(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        if self.environment == "production":

            try:
                print("[Embedder] Using Hugging Face")

                embeddings = self._encode_hf(texts)

            except Exception as e:

                print(
                    f"[Embedder] Hugging Face failed: {e}"
                )

                print(
                    "[Embedder] Falling back to Ollama"
                )

                embeddings = self._encode_ollama(texts)

        else:

            print("[Embedder] Using local Ollama")

            embeddings = self._encode_ollama(texts)

        # Store embedding dimension
        if embeddings and self._dimension is None:
            self._dimension = len(embeddings[0])

        return embeddings

    # ---------------------------------------------------------
    # Single text
    # ---------------------------------------------------------

    def encode_one(self, text: str) -> List[float]:
        embeddings = self.encode([text])

        if not embeddings:
            raise RuntimeError(
                "No embedding was generated"
            )

        return embeddings[0]

    # ---------------------------------------------------------
    # Dimension
    # ---------------------------------------------------------

    def get_dimension(self) -> int:

        if self._dimension is None:
            self._dimension = len(
                self.encode_one("dimension_probe")
            )

        return self._dimension


# -------------------------------------------------------------
# Singleton
# -------------------------------------------------------------

_embedder_singleton = None


def get_embedder() -> Embedder:
    global _embedder_singleton

    if _embedder_singleton is None:
        _embedder_singleton = Embedder()

    return _embedder_singleton
