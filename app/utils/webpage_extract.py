"""Bounded webpage text extraction for untrusted search result URLs."""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import socket
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx

from app.utils.cache import TTLCache

from app.config import (
    WEB_PAGE_MAX_BYTES,
    WEB_PAGE_MAX_REDIRECTS,
    WEB_PAGE_MAX_TEXT_CHARS,
    WEB_PAGE_TIMEOUT_SECONDS,
)

logger = logging.getLogger(__name__)

_SKIP_TAGS = {
    "aside", "footer", "form", "nav", "noscript", "script", "style", "svg",
}
_REDIRECT_STATUSES = {301, 302, 303, 307, 308}
_USER_AGENT = "HallucinationDetector/1.0 (+evidence retrieval)"
_ROBOTS_CACHE = TTLCache(maxsize=256, ttl=3600)
_ROBOTS_MAX_BYTES = 65536


class _ReadableTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.title_parts: list[str] = []
        self.published_at: str | None = None
        self.author: str | None = None
        self._skip_depth = 0
        self._title_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key.lower(): value for key, value in attrs if value is not None}
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
            return
        if tag == "title":
            self._title_depth += 1
        if tag in {"article", "h1", "h2", "h3", "h4", "p", "li", "blockquote", "br"}:
            self.parts.append("\n")

        metadata_key = " ".join(
            str(attributes.get(key, ""))
            for key in ("property", "name", "itemprop")
        ).casefold()
        if any(
            marker in metadata_key
            for marker in ("published_time", "datepublished", "pubdate", "datecreated")
        ):
            value = attributes.get("content") or attributes.get("datetime")
            if value and not self.published_at:
                self.published_at = value.strip()
        if "author" in metadata_key:
            value = attributes.get("content") or attributes.get("href")
            if value and not self.author:
                self.author = value.strip()

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if tag == "title":
            self._title_depth = max(0, self._title_depth - 1)
        if tag in {"article", "h1", "h2", "h3", "h4", "p", "li", "blockquote"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0 and data.strip():
            if self._title_depth:
                self.title_parts.append(data.strip())
            self.parts.append(data.strip())
            self.parts.append(" ")


def _is_public_http_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        if (
            parsed.scheme.lower() not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or (parsed.port is not None and parsed.port not in {80, 443})
        ):
            return False
        try:
            addresses = [ipaddress.ip_address(parsed.hostname)]
        except ValueError:
            addresses = [
                ipaddress.ip_address(result[4][0])
                for result in socket.getaddrinfo(
                    parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80),
                    type=socket.SOCK_STREAM,
                )
            ]
        return bool(addresses) and all(address.is_global for address in addresses)
    except (OSError, TypeError, ValueError):
        return False


def _robots_allowed(client: httpx.Client, page_url: str) -> bool:
    parsed = urlparse(page_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    policy = _ROBOTS_CACHE.get(origin)
    if policy is None:
        robots_url = urljoin(origin, "/robots.txt")
        current_url = robots_url
        policy = False
        try:
            for redirect_count in range(WEB_PAGE_MAX_REDIRECTS + 1):
                if not _is_public_http_url(current_url):
                    break
                with client.stream("GET", current_url) as response:
                    if response.status_code in _REDIRECT_STATUSES:
                        location = response.headers.get("location")
                        if not location or redirect_count >= WEB_PAGE_MAX_REDIRECTS:
                            break
                        current_url = urljoin(current_url, location)
                        continue
                    if response.status_code == 404:
                        parser = RobotFileParser(robots_url)
                        parser.parse([])
                        policy = parser
                        break
                    if response.status_code != 200:
                        break
                    content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
                    if content_type not in {"text/plain", "text/html"}:
                        break
                    length = response.headers.get("content-length")
                    if length:
                        try:
                            if int(length) > _ROBOTS_MAX_BYTES:
                                break
                        except ValueError:
                            break
                    content = bytearray()
                    for chunk in response.iter_bytes():
                        content.extend(chunk)
                        if len(content) > _ROBOTS_MAX_BYTES:
                            content.clear()
                            break
                    else:
                        parser = RobotFileParser(robots_url)
                        parser.parse(bytes(content).decode("utf-8", errors="replace").splitlines())
                        policy = parser
                    break
        except (httpx.HTTPError, OSError, TypeError, ValueError):
            policy = False
        _ROBOTS_CACHE.set(origin, policy)

    return policy is not False and policy.can_fetch(_USER_AGENT, page_url)


def _read_page(url: str) -> dict | None:
    current_url = url
    headers = {"User-Agent": _USER_AGENT}
    try:
        with httpx.Client(
            follow_redirects=False,
            timeout=WEB_PAGE_TIMEOUT_SECONDS,
            headers=headers,
            trust_env=False,
        ) as client:
            for redirect_count in range(WEB_PAGE_MAX_REDIRECTS + 1):
                if not _is_public_http_url(current_url):
                    return None
                if not _robots_allowed(client, current_url):
                    return None
                with client.stream("GET", current_url) as response:
                    if response.status_code in _REDIRECT_STATUSES:
                        location = response.headers.get("location")
                        if not location or redirect_count >= WEB_PAGE_MAX_REDIRECTS:
                            return None
                        current_url = urljoin(current_url, location)
                        continue
                    if response.status_code != 200:
                        return None
                    content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
                    if content_type not in {"text/html", "application/xhtml+xml"}:
                        return None
                    length = response.headers.get("content-length")
                    if length:
                        try:
                            if int(length) > WEB_PAGE_MAX_BYTES:
                                return None
                        except ValueError:
                            return None
                    content = bytearray()
                    for chunk in response.iter_bytes():
                        content.extend(chunk)
                        if len(content) > WEB_PAGE_MAX_BYTES:
                            return None
                    encoding = response.encoding or "utf-8"
                    parser = _ReadableTextParser()
                    parser.feed(bytes(content).decode(encoding, errors="replace"))
                    text = " ".join(" ".join(parser.parts).split())
                    if not text:
                        return None
                    return {
                        "body": text[:WEB_PAGE_MAX_TEXT_CHARS],
                        "evidence_type": "FULL_WEBPAGE",
                        "title": " ".join(parser.title_parts).strip(),
                        "author": parser.author,
                        "publisher": urlparse(str(response.url)).hostname,
                        "published_at": parser.published_at,
                        "retrieved_at": datetime.now(timezone.utc).isoformat(),
                        "url": str(response.url),
                    }
    except (httpx.HTTPError, OSError, UnicodeError, ValueError) as error:
        logger.info("Webpage extraction failed (%s)", type(error).__name__)
        return None
    return None


async def extract_webpage(url: str) -> dict | None:
    """Fetch one public HTML page, bounded by timeout and response size."""
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_read_page, url),
            timeout=WEB_PAGE_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        logger.info("Webpage extraction timed out")
        return None