"""Embedding service — lazy-loaded SentenceTransformer singleton.

Uses the all-MiniLM-L6-v2 model (384-dim) configured in settings.
"""
from __future__ import annotations

import logging
from functools import lru_cache

from sentence_transformers import SentenceTransformer

from app.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _load_model() -> SentenceTransformer:
    """Load and cache the embedding model (one-time cost ~200 MB)."""
    model_name = get_settings().embedding_model
    logger.info("Loading embedding model: %s", model_name)
    return SentenceTransformer(model_name)


def embed_text(text: str) -> list[float]:
    """Embed a single string and return a flat list of floats."""
    model = _load_model()
    vec = model.encode(text, normalize_embeddings=True)
    return vec.tolist()


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Batch-embed a list of strings."""
    model = _load_model()
    vecs = model.encode(texts, normalize_embeddings=True, batch_size=64)
    return [v.tolist() for v in vecs]
