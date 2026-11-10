from unittest.mock import MagicMock, patch

import httpx

from app.utils.webpage_extract import _is_public_http_url, _read_page, _robots_allowed


def _public_dns(*args, **kwargs):
    return [(None, None, None, None, ("8.8.8.8", 443))]


def test_rejects_non_http_and_private_urls():
    assert _is_public_http_url("file:///etc/passwd") is False
    assert _is_public_http_url("http://127.0.0.1/admin") is False
    assert _is_public_http_url("http://192.168.1.10/") is False


@patch("app.utils.webpage_extract._robots_allowed", return_value=True)
@patch("app.utils.webpage_extract.socket.getaddrinfo", side_effect=_public_dns)
@patch("app.utils.webpage_extract.httpx.Client")
def test_extracts_article_text_and_publication_date(mock_client, _mock_dns, _mock_robots):
    response = MagicMock()
    response.status_code = 200
    response.headers = {"content-type": "text/html; charset=utf-8"}
    response.encoding = "utf-8"
    response.url = "https://example.org/article"
    response.iter_bytes.return_value = [
        b'<html><head><meta property="article:published_time" content="2024-01-02">'
        b'<meta name="author" content="Researcher"></head>'
        b'<body><nav>Navigation</nav><article><h1>Research</h1><p>Useful finding.</p>'
        b'<script>Ignore this</script></article></body></html>'
    ]
    mock_client.return_value.__enter__.return_value.stream.return_value.__enter__.return_value = response

    result = _read_page("https://example.org/article")

    assert result["evidence_type"] == "FULL_WEBPAGE"
    assert result["published_at"] == "2024-01-02"
    assert result["author"] == "Researcher"
    assert result["publisher"] == "example.org"
    assert "Research" in result["body"]
    assert "Useful finding." in result["body"]
    assert "Navigation" not in result["body"]
    assert "Ignore this" not in result["body"]


@patch("app.utils.webpage_extract._robots_allowed", return_value=True)
@patch("app.utils.webpage_extract.socket.getaddrinfo", side_effect=_public_dns)
@patch("app.utils.webpage_extract.httpx.Client")
def test_rejects_oversized_content_by_header(mock_client, _mock_dns, _mock_robots):
    response = MagicMock()
    response.status_code = 200
    response.headers = {
        "content-type": "text/html",
        "content-length": "1000001",
    }
    mock_client.return_value.__enter__.return_value.stream.return_value.__enter__.return_value = response

    with patch("app.utils.webpage_extract.WEB_PAGE_MAX_BYTES", 1000000):
        assert _read_page("https://example.org/article") is None


@patch("app.utils.webpage_extract._robots_allowed", return_value=True)
@patch("app.utils.webpage_extract.socket.getaddrinfo", side_effect=_public_dns)
@patch("app.utils.webpage_extract.httpx.Client")
def test_rejects_oversized_stream_without_content_length(mock_client, _mock_dns, _mock_robots):
    response = MagicMock()
    response.status_code = 200
    response.headers = {"content-type": "text/html"}
    response.encoding = "utf-8"
    response.url = "https://example.org/article"
    response.iter_bytes.return_value = [b"x" * 80]
    mock_client.return_value.__enter__.return_value.stream.return_value.__enter__.return_value = response

    with patch("app.utils.webpage_extract.WEB_PAGE_MAX_BYTES", 50):
        assert _read_page("https://example.org/article") is None


@patch("app.utils.webpage_extract._robots_allowed", return_value=True)
@patch("app.utils.webpage_extract.socket.getaddrinfo", side_effect=_public_dns)
@patch("app.utils.webpage_extract.httpx.Client")
def test_rejects_non_html_content(mock_client, _mock_dns, _mock_robots):
    response = MagicMock()
    response.status_code = 200
    response.headers = {"content-type": "application/pdf"}
    mock_client.return_value.__enter__.return_value.stream.return_value.__enter__.return_value = response

    assert _read_page("https://example.org/article") is None


def test_extract_webpage_obeys_timeout():
    import asyncio
    from unittest.mock import AsyncMock

    from app.utils.webpage_extract import extract_webpage

    async def delayed_read(*_args):
        await asyncio.sleep(0.05)
        return {"body": "late"}

    with (
        patch("app.utils.webpage_extract.socket.getaddrinfo", side_effect=_public_dns),
        patch("app.utils.webpage_extract.WEB_PAGE_TIMEOUT_SECONDS", 0.001),
        patch("app.utils.webpage_extract.asyncio.to_thread", new_callable=AsyncMock, side_effect=delayed_read),
    ):
        assert asyncio.run(extract_webpage("https://example.org/article")) is None


@patch("app.utils.webpage_extract._robots_allowed", return_value=True)
@patch("app.utils.webpage_extract.socket.getaddrinfo", side_effect=_public_dns)
@patch("app.utils.webpage_extract.httpx.Client")
def test_revalidates_redirect_target_before_request(mock_client, mock_dns, _mock_robots):
    response = MagicMock()
    response.status_code = 302
    response.headers = {"location": "http://127.0.0.1/private"}
    mock_client.return_value.__enter__.return_value.stream.return_value.__enter__.return_value = response

    assert _read_page("https://example.org/article") is None
    assert mock_client.return_value.__enter__.return_value.stream.call_count == 1


def test_robots_rules_block_disallowed_pages_and_cache_policy():
    from app.utils.webpage_extract import _ROBOTS_CACHE

    _ROBOTS_CACHE.clear()
    response = MagicMock()
    response.status_code = 200
    response.headers = {"content-type": "text/plain"}
    response.iter_bytes.return_value = [
        b"User-agent: *\nDisallow: /private\nAllow: /public\n"
    ]
    client = MagicMock()
    client.stream.return_value.__enter__.return_value = response

    with patch("app.utils.webpage_extract._is_public_http_url", return_value=True):
        assert _robots_allowed(client, "https://example.org/private/report") is False
        assert _robots_allowed(client, "https://example.org/public/report") is True

    client.stream.assert_called_once()
    _ROBOTS_CACHE.clear()


def test_missing_robots_file_allows_webpage_fetch():
    from app.utils.webpage_extract import _ROBOTS_CACHE

    _ROBOTS_CACHE.clear()
    response = MagicMock()
    response.status_code = 404
    response.headers = {}
    client = MagicMock()
    client.stream.return_value.__enter__.return_value = response

    with patch("app.utils.webpage_extract._is_public_http_url", return_value=True):
        assert _robots_allowed(client, "https://example.org/article") is True

    _ROBOTS_CACHE.clear()