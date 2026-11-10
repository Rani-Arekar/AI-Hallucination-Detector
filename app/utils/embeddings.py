import hashlib
import logging
import os

from google import genai
from google.genai import types

from app.utils.cache import TTLCache

logger = logging.getLogger(__name__)

client = None
if os.getenv("GEMINI_API_KEY"):
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Embeddings are deterministic for a given input, so a longer TTL is safe.
_cache = TTLCache(maxsize=1024, ttl=3600.0)


def _cache_key(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def embed(texts: list[str]) -> list[list[float]]:
    """Embeds a batch of texts, serving cached vectors where available and
    only calling the API for the texts that actually miss the cache.
    """
    if not texts:
        return []

    results: list[list[float] | None] = [None] * len(texts)
    to_fetch: list[str] = []
    to_fetch_idx: list[int] = []

    for i, t in enumerate(texts):
        cached = _cache.get(_cache_key(t))
        if cached is not None:
            results[i] = cached
        else:
            to_fetch.append(t)
            to_fetch_idx.append(i)

    if to_fetch and client is not None:
        try:
            result = client.models.embed_content(
                model="gemini-embedding-001",
                contents=to_fetch,
                config=types.EmbedContentConfig(task_type="SEMANTIC_SIMILARITY"),
            )
            for idx, embedding in zip(to_fetch_idx, result.embeddings):
                vec = list(embedding.values)
                results[idx] = vec
                _cache.set(_cache_key(texts[idx]), vec)
        except Exception as e:
            logger.warning("embed() failed for %d texts: %s", len(to_fetch), e)
            # Leave the missed slots as None; caller must treat None as
            # "no embedding available" rather than crash the whole batch.
            for idx in to_fetch_idx:
                if results[idx] is None:
                    results[idx] = []

    return results  # type: ignore[return-value]


def cache_stats() -> dict:
    return _cache.stats()
