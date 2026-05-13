"""Official public legal/regulatory source connector."""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape
from urllib.parse import urljoin, urlparse

import httpx
from loguru import logger

from app.core.config import settings
from app.services.connectors.types import ConnectorHealth


@dataclass
class LegalSourceDocument:
    source_url: str
    title: str
    content: str
    published_at: datetime
    authority: str = "gov.cn"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _strip_html(value: str) -> str:
    text = re.sub(r"(?is)<script.*?>.*?</script>", " ", value)
    text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


class LegalSourceConnector:
    async def _fetch_html(self, url: str) -> str:
        timeout = httpx.Timeout(settings.legal_source.request_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "contract-agent/1.0"})
            resp.raise_for_status()
            return resp.text

    def _seed_urls(self) -> list[str]:
        return settings.legal_source.seed_url_list

    def _extract_links(self, page_url: str, html: str) -> list[str]:
        hrefs = re.findall(r'(?i)href=["\']([^"\']+)["\']', html)
        links: list[str] = []
        for href in hrefs:
            abs_url = urljoin(page_url, href)
            parsed = urlparse(abs_url)
            if parsed.scheme not in {"http", "https"}:
                continue
            host = (parsed.netloc or "").lower()
            if not host.endswith("gov.cn"):
                continue
            if any(token in parsed.path for token in [".pdf", ".doc", ".docx"]):
                continue
            links.append(abs_url)
        dedup: list[str] = []
        seen: set[str] = set()
        for item in links:
            if item in seen:
                continue
            seen.add(item)
            dedup.append(item)
        return dedup

    async def _fetch_article(self, url: str) -> LegalSourceDocument | None:
        try:
            html = await self._fetch_html(url)
        except Exception as exc:
            logger.debug(f"legal source fetch failed url={url}: {exc}")
            return None

        title_match = re.search(r"(?is)<title>(.*?)</title>", html)
        title = _strip_html(title_match.group(1)) if title_match else url
        body = _strip_html(html)
        if len(body) < 120:
            return None

        return LegalSourceDocument(
            source_url=url,
            title=title[:300] or "Untitled",
            content=body[:100_000],
            published_at=_now(),
        )

    async def fetch_documents(self, *, limit: int | None = None) -> list[LegalSourceDocument]:
        if not settings.legal_source.enabled:
            return []
        hard_limit = limit or settings.legal_source.max_documents_per_sync
        if hard_limit <= 0:
            return []

        links: list[str] = []
        for seed in self._seed_urls():
            try:
                html = await self._fetch_html(seed)
                links.extend(self._extract_links(seed, html))
            except Exception as exc:
                logger.warning(f"legal source seed fetch failed seed={seed}: {exc}")

        dedup_links: list[str] = []
        seen: set[str] = set()
        for link in links:
            if link in seen:
                continue
            seen.add(link)
            dedup_links.append(link)
            if len(dedup_links) >= hard_limit * 4:
                break

        docs: list[LegalSourceDocument] = []
        for link in dedup_links:
            doc = await self._fetch_article(link)
            if not doc:
                continue
            docs.append(doc)
            if len(docs) >= hard_limit:
                break
        return docs

    async def health(self) -> ConnectorHealth:
        started = time.perf_counter()
        if not settings.legal_source.enabled:
            return ConnectorHealth(name="legal_source", ok=True, detail="disabled by config")
        seeds = self._seed_urls()
        if not seeds:
            return ConnectorHealth(name="legal_source", ok=False, detail="no seed urls configured")

        try:
            await self._fetch_html(seeds[0])
            latency_ms = (time.perf_counter() - started) * 1000
            return ConnectorHealth(
                name="legal_source",
                ok=True,
                latency_ms=latency_ms,
                detail=f"seed={seeds[0]}",
            )
        except Exception as exc:
            latency_ms = (time.perf_counter() - started) * 1000
            return ConnectorHealth(name="legal_source", ok=False, latency_ms=latency_ms, detail=str(exc))


legal_source_connector = LegalSourceConnector()

