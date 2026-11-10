import asyncio
import logging
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

from ddgs import DDGS

from app.config import (
    WEB_SEARCH_MAX_RESULTS,
    WEB_SEARCH_RETRIES,
    WEB_SEARCH_TIMEOUT_SECONDS,
    WEB_PAGE_FETCH_LIMIT,
)
from app.utils.cache import TTLCache
from app.utils.webpage_extract import extract_webpage

logger = logging.getLogger(__name__)

# Web results change over time, so a shorter TTL than embeddings.
_cache = TTLCache(maxsize=512, ttl=600.0)

DEFAULT_TIMEOUT_S = WEB_SEARCH_TIMEOUT_SECONDS


def _is_valid_result_url(url: object) -> bool:
    if not isinstance(url, str):
        return False
    try:
        parsed = urlparse(url)
        return (
            parsed.scheme.lower() in {"http", "https"}
            and bool(parsed.hostname)
            and parsed.username is None
            and parsed.password is None
        )
    except (TypeError, ValueError):
        return False


def search_web(query: str, k: int | None = None) -> list[dict]:
    """Returns up to k results as [{"title": ..., "url": ..., "body": ...}].
    An empty list means "no results / search failed" -- callers must treat
    that as "no evidence found", never as "claim is false".
    """
    result_limit = WEB_SEARCH_MAX_RESULTS if k is None else k
    if result_limit < 1:
        return []

    cache_key = f"{query}\0{result_limit}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    raw_results = None
    for attempt in range(max(0, WEB_SEARCH_RETRIES) + 1):
        try:
            with DDGS() as ddgs:
                raw_results = list(ddgs.text(query, max_results=result_limit))
            break
        except Exception as e:
            logger.warning("search_web failed (%s)", type(e).__name__)
            if attempt >= max(0, WEB_SEARCH_RETRIES):
                return []
            time.sleep(min(0.25 * (2 ** attempt), 1.0))

    retrieved_at = datetime.now(timezone.utc).isoformat()
    results = []
    for result in raw_results or []:
        if not isinstance(result, dict):
            continue
        body = result.get("body")
        url = result.get("href")
        if not isinstance(body, str) or not body.strip() or not _is_valid_result_url(url):
            continue
        title = result.get("title")
        results.append(
            {
                "title": title if isinstance(title, str) else "",
                "url": url,
                "publisher": urlparse(url).hostname,
                "author": None,
                "body": body,
                "evidence_type": "SEARCH_RESULT_SNIPPET",
                "published_at": result.get("date") if isinstance(result.get("date"), str) else None,
                "retrieved_at": retrieved_at,
            }
        )
    _cache.set(cache_key, results)
    return results


async def search_web_async(
    query: str, k: int | None = None, timeout: float = DEFAULT_TIMEOUT_S
) -> list[dict]:
    async def search_and_enrich() -> list[dict]:
        results = await asyncio.to_thread(search_web, query, k)
        if not results:
            return []

        async def enrich(index: int, result: dict) -> dict:
            if index >= WEB_PAGE_FETCH_LIMIT:
                return result
            try:
                page = await extract_webpage(result["url"])
            except Exception as error:
                logger.info("Webpage extraction failed (%s)", type(error).__name__)
                return result
            if not page:
                return result
            return {
                **result,
                **page,
                "title": page.get("title") or result.get("title", ""),
                "publisher": page.get("publisher") or result.get("publisher"),
            }

        return await asyncio.gather(
            *(enrich(index, result) for index, result in enumerate(results))
        )

    try:
        return await asyncio.wait_for(search_and_enrich(), timeout=timeout)
    except asyncio.TimeoutError:
        logger.warning("search_web_async timed out after %.1fs", timeout)
        return []


def cache_stats() -> dict:
    return _cache.stats()
