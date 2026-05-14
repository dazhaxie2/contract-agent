"""Nebula graph connector."""

from __future__ import annotations

import asyncio
import re
import time
from typing import Any

from loguru import logger

from app.core.config import settings
from app.services.connectors.types import ConnectorHealth

try:
    from nebula3.Config import Config as NebulaConfig
    from nebula3.gclient.net import ConnectionPool

    HAS_NEBULA = True
except Exception:  # pragma: no cover - optional runtime dependency failures.
    NebulaConfig = Any  # type: ignore[assignment]
    ConnectionPool = Any  # type: ignore[assignment]
    HAS_NEBULA = False


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


class NebulaConnector:
    def __init__(self) -> None:
        self._pool: ConnectionPool | None = None
        self._ready = False

    async def _connect(self) -> bool:
        if self._pool is not None:
            return True
        if not HAS_NEBULA:
            return False

        def _run() -> ConnectionPool:
            config = NebulaConfig()
            config.max_connection_pool_size = settings.nebula.max_connection_pool_size
            pool = ConnectionPool()
            ok = pool.init([(settings.nebula.host, settings.nebula.port)], config)
            if not ok:
                raise RuntimeError("nebula pool init failed")
            return pool

        try:
            self._pool = await asyncio.to_thread(_run)
            return True
        except Exception as exc:
            logger.warning(f"Nebula connect failed: {exc}")
            self._pool = None
            return False

    async def _execute(self, statement: str):
        if not await self._connect():
            raise RuntimeError("nebula unavailable")

        def _run(sql: str):
            assert self._pool is not None
            session = self._pool.get_session(settings.nebula.user, settings.nebula.password)
            try:
                resp = session.execute(sql)
                if not resp.is_succeeded():
                    raise RuntimeError(resp.error_msg())
                return resp
            finally:
                session.release()

        return await asyncio.to_thread(_run, statement)

    async def ensure_schema(self) -> bool:
        if self._ready:
            return True
        if not await self._connect():
            return False

        statements = [
            f'CREATE SPACE IF NOT EXISTS `{settings.nebula.space}`(partition_num=10, replica_factor=1, vid_type=FIXED_STRING(64));',
            f"USE `{settings.nebula.space}`;",
            'CREATE TAG IF NOT EXISTS `chunk`(tenant_id string, doc_id string, chunk_id string, doc_type string);',
            'CREATE TAG IF NOT EXISTS `entity`(name string);',
            "CREATE EDGE IF NOT EXISTS `mentions`(weight double);",
        ]

        def _run_all() -> None:
            assert self._pool is not None
            session = self._pool.get_session(settings.nebula.user, settings.nebula.password)
            try:
                for sql in statements:
                    resp = session.execute(sql)
                    if not resp.is_succeeded():
                        raise RuntimeError(resp.error_msg())
            finally:
                session.release()

        try:
            await asyncio.to_thread(_run_all)
            self._ready = True
            return True
        except Exception as exc:
            logger.warning(f"Nebula ensure schema failed: {exc}")
            return False

    async def upsert_chunk_entities(
        self,
        *,
        tenant_id: str,
        doc_id: str,
        chunk_id: str,
        doc_type: str,
        entities: list[str],
    ) -> bool:
        if not entities:
            return True
        if not await self.ensure_schema():
            return False

        try:
            await self._execute(f"USE `{settings.nebula.space}`;")
            chunk_vid = _escape(f"chunk:{tenant_id}:{chunk_id}")
            await self._execute(
                f'UPSERT VERTEX ON `chunk` "{chunk_vid}" '
                f'SET tenant_id="{_escape(tenant_id)}", doc_id="{_escape(doc_id)}", '
                f'chunk_id="{_escape(chunk_id)}", doc_type="{_escape(doc_type)}";'
            )

            dedup = sorted({item.strip() for item in entities if item and len(item.strip()) >= 2})
            for ent in dedup[:32]:
                ent_vid = _escape(f"entity:{tenant_id}:{ent.lower()[:48]}")
                await self._execute(
                    f'UPSERT VERTEX ON `entity` "{ent_vid}" SET name="{_escape(ent[:128])}";'
                )
                await self._execute(
                    f'UPSERT EDGE ON `mentions` "{ent_vid}"->"{chunk_vid}" '
                    f"SET weight=1.0;"
                )
            return True
        except Exception as exc:
            logger.warning(f"Nebula upsert chunk entities failed: {exc}")
            return False

    async def search_chunks_by_entities(self, *, tenant_id: str, entities: list[str], limit: int = 20) -> list[dict]:
        if not entities:
            return []
        if not await self.ensure_schema():
            return []

        terms = sorted({item.strip() for item in entities if item and len(item.strip()) >= 2})[:12]
        if not terms:
            return []

        try:
            await self._execute(f"USE `{settings.nebula.space}`;")
            hits: dict[str, dict] = {}
            for term in terms:
                ent_vid = _escape(f"entity:{tenant_id}:{term.lower()[:48]}")
                resp = await self._execute(
                    'GO FROM "{ent_vid}" OVER `mentions` YIELD dst(edge) AS chunk_vid;'.format(ent_vid=ent_vid)
                )
                rows = resp.rows() or []
                for row in rows:
                    raw = row.values[0].get_sVal().decode("utf-8")
                    chunk_id = raw.split(":")[-1]
                    entry = hits.setdefault(chunk_id, {"chunk_id": chunk_id, "matched_entities": [], "score": 0.0})
                    entry["matched_entities"].append(term)
                    entry["score"] = float(entry["score"]) + 1.0
            ranked = sorted(hits.values(), key=lambda x: x["score"], reverse=True)
            for item in ranked:
                item["matched_entities"] = sorted(set(item["matched_entities"]))
            return ranked[:limit]
        except Exception as exc:
            logger.warning(f"Nebula graph search failed: {exc}")
            return []

    async def health(self) -> ConnectorHealth:
        started = time.perf_counter()
        ok = await self.ensure_schema()
        latency_ms = (time.perf_counter() - started) * 1000
        return ConnectorHealth(
            name="nebula",
            ok=ok,
            latency_ms=latency_ms,
            detail=f"space={settings.nebula.space}",
        )


def extract_entities(text: str, max_terms: int = 24) -> list[str]:
    """Rule-based entity extraction fallback for graph indexing."""
    if not text:
        return []
    candidates = re.findall(r"[A-Za-z0-9\u4e00-\u9fff]{2,24}", text)
    dedup: list[str] = []
    seen: set[str] = set()
    for token in candidates:
        normalized = token.strip()
        lower = normalized.lower()
        if lower in seen:
            continue
        seen.add(lower)
        dedup.append(normalized)
        if len(dedup) >= max_terms:
            break
    return dedup


nebula_connector = NebulaConnector()

