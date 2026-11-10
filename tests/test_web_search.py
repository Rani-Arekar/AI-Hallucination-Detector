from datetime import datetime
from unittest.mock import MagicMock, patch

from app.utils.web_search import search_web, search_web_async


@patch("app.utils.web_search._cache")
@patch("app.utils.web_search.DDGS")
def test_search_uses_configured_limit_filters_urls_and_timestamps_results(
    mock_ddgs, mock_cache
):
    mock_cache.get.return_value = None
    mock_ddgs.return_value.__enter__.return_value.text.return_value = [
        {"title": "Valid", "href": "https://example.org/article", "body": "Snippet"},
        {"title": "Unsafe", "href": "javascript:alert(1)", "body": "Ignore"},
        {"title": "Null URL", "href": None, "body": "Ignore"},
        {"title": "Malformed body", "href": "https://example.org/other", "body": 123},
    ]

    with patch("app.utils.web_search.WEB_SEARCH_MAX_RESULTS", 8):
        results = search_web("a factual claim")

    mock_ddgs.return_value.__enter__.return_value.text.assert_called_once_with(
        "a factual claim", max_results=8
    )
    assert len(results) == 1
    assert results[0]["url"] == "https://example.org/article"
    assert results[0]["body"] == "Snippet"
    datetime.fromisoformat(results[0]["retrieved_at"])
    mock_cache.set.assert_called_once()


@patch("app.utils.web_search.time.sleep")
@patch("app.utils.web_search._cache")
@patch("app.utils.web_search.DDGS")
def test_search_retries_provider_failure_once(mock_ddgs, mock_cache, mock_sleep):
    mock_cache.get.return_value = None
    successful_session = MagicMock()
    successful_session.__enter__.return_value.text.return_value = [
        {"title": "Valid", "href": "https://example.org/article", "body": "Snippet"}
    ]
    mock_ddgs.side_effect = [RuntimeError("temporary failure"), successful_session]

    with patch("app.utils.web_search.WEB_SEARCH_RETRIES", 1):
        results = search_web("a factual claim", k=4)

    assert len(results) == 1
    assert mock_ddgs.call_count == 2
    mock_sleep.assert_called_once()


@patch("app.utils.web_search.extract_webpage")
@patch("app.utils.web_search.search_web")
def test_unavailable_page_falls_back_to_search_snippet(mock_search, mock_extract):
    snippet = {
        "title": "Search title",
        "url": "https://example.org/article",
        "body": "Search-result excerpt.",
        "evidence_type": "SEARCH_RESULT_SNIPPET",
        "retrieved_at": "2026-11-09T12:00:00+00:00",
    }
    mock_search.return_value = [snippet]
    mock_extract.return_value = None

    import asyncio

    results = asyncio.run(search_web_async("a factual claim"))

    assert results == [snippet]
    mock_extract.assert_awaited_once_with("https://example.org/article")