"""
Embedding provider — local-first.

Default: sentence-transformers (all-MiniLM-L6-v2, runs fully offline, dim=384)
Upgrade:  set EMBEDDING_PROVIDER=openai + OPENAI_API_KEY to use text-embedding-3-small

The active provider is resolved once at import time so the model is loaded
only once per process.
"""
from __future__ import annotations

import logging
import os
from typing import Any, List, Optional

logger = logging.getLogger(__name__)

EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "local").lower()
LOCAL_EMBED_MODEL  = os.getenv("LOCAL_EMBED_MODEL", "all-MiniLM-L6-v2")
OPENAI_EMBED_MODEL = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")
OPENAI_API_KEY     = os.getenv("OPENAI_API_KEY", "")

# Resolved at import — 384 for MiniLM, 1536 for text-embedding-3-small
EMBEDDING_DIM: int = 384

_st_model: Any = None  # lazy-loaded SentenceTransformer


def _load_st() -> Any:
    global _st_model
    if _st_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _st_model = SentenceTransformer(LOCAL_EMBED_MODEL)
            logger.info("sentence-transformers model loaded: %s", LOCAL_EMBED_MODEL)
        except Exception as exc:
            logger.warning("sentence-transformers unavailable: %s", exc)
    return _st_model


def _use_openai() -> bool:
    return EMBEDDING_PROVIDER == "openai" and bool(OPENAI_API_KEY)


async def embed(text: str) -> Optional[List[float]]:
    """Embed a single string. Returns None on failure."""
    if _use_openai():
        return await _openai_embed(text[:8000])
    model = _load_st()
    if model is None:
        return None
    try:
        vec = model.encode(text[:2000], normalize_embeddings=True)
        return vec.tolist()
    except Exception as exc:
        logger.warning("local embed() failed: %s", exc)
        return None


async def embed_batch(texts: List[str]) -> List[Optional[List[float]]]:
    """Embed a list of strings. Returns a list of the same length."""
    if _use_openai():
        return await _openai_embed_batch([t[:8000] for t in texts])
    model = _load_st()
    if model is None:
        return [None] * len(texts)
    try:
        vecs = model.encode([t[:2000] for t in texts], normalize_embeddings=True)
        return [v.tolist() for v in vecs]
    except Exception as exc:
        logger.warning("local embed_batch() failed: %s", exc)
        return [None] * len(texts)


# ── OpenAI helpers (only called when EMBEDDING_PROVIDER=openai) ──────────────

async def _openai_embed(text: str) -> Optional[List[float]]:
    try:
        from openai import AsyncOpenAI
        r = await AsyncOpenAI(api_key=OPENAI_API_KEY).embeddings.create(
            model=OPENAI_EMBED_MODEL, input=text
        )
        return r.data[0].embedding
    except Exception as exc:
        logger.warning("OpenAI embed() failed: %s", exc)
        return None


async def _openai_embed_batch(texts: List[str]) -> List[Optional[List[float]]]:
    try:
        from openai import AsyncOpenAI
        r = await AsyncOpenAI(api_key=OPENAI_API_KEY).embeddings.create(
            model=OPENAI_EMBED_MODEL, input=texts
        )
        return [d.embedding for d in r.data]
    except Exception as exc:
        logger.warning("OpenAI embed_batch() failed: %s", exc)
        return [None] * len(texts)
