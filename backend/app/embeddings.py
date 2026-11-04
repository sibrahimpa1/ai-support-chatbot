"""Local sentence embeddings (no API key, runs on CPU via ONNX).

`BAAI/bge-small-en-v1.5` is a 384-dimensional model (~65 MB) that is downloaded
once into `model_cache_dir`. If it cannot be loaded (offline, no disk), callers
get `None` from `load_embedder` and fall back to keyword-only methods, so the
app always starts.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)


class Embedder:
    def __init__(self, model_name: str, cache_dir: Path):
        from fastembed import TextEmbedding

        self.model_name = model_name
        self._model = TextEmbedding(model_name, cache_dir=str(cache_dir))

    def embed(self, texts: list[str]) -> np.ndarray:
        """Unit-length vectors, so a dot product is cosine similarity."""
        if not texts:
            return np.zeros((0, 384), dtype=np.float32)
        vectors = np.asarray(list(self._model.embed(texts)), dtype=np.float32)
        return vectors / np.linalg.norm(vectors, axis=1, keepdims=True)

    def embed_one(self, text: str) -> np.ndarray:
        return self.embed([text])[0]


@lru_cache(maxsize=4)
def load_embedder(model_name: str, cache_dir: str) -> Embedder | None:
    try:
        Path(cache_dir).mkdir(parents=True, exist_ok=True)
        return Embedder(model_name, Path(cache_dir))
    except Exception as exc:  # network, disk or ONNX runtime problems
        log.warning("Embedding model unavailable, using keyword methods only: %s", exc)
        return None
