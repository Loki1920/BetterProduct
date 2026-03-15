from __future__ import annotations

from functools import lru_cache
from typing import List

import numpy as np

from backend.config import settings


@lru_cache(maxsize=1)
def _model():
    """Load sentence-transformer model once and cache in memory."""
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(settings.EMBEDDING_MODEL)


def encode(texts: List[str]) -> np.ndarray:
    return _model().encode(texts, normalize_embeddings=True, show_progress_bar=False)


def cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity for unit-normalised vectors (= dot product)."""
    return float(np.dot(a, b))
