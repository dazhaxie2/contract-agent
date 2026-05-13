"""Milvus vector connector."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from loguru import logger

from app.core.config import settings
from app.services.connectors.types import ConnectorHealth

try:
    from pymilvus import Collection, CollectionSchema, DataType, FieldSchema, connections, utility

    HAS_MILVUS = True
except Exception:  # pragma: no cover - optional runtime dependency failures.
    Collection = Any  # type: ignore[assignment]
    CollectionSchema = Any  # type: ignore[assignment]
    DataType = Any  # type: ignore[assignment]
    FieldSchema = Any  # type: ignore[assignment]
    connections = Any  # type: ignore[assignment]
    utility = Any  # type: ignore[assignment]
    HAS_MILVUS = False


class MilvusConnector:
    def __init__(self) -> None:
        self._connected = False
        self._collection_ready = False

    @property
    def collection_name(self) -> str:
        return settings.milvus.collection_name

    async def _connect(self) -> bool:
        if self._connected:
            return True
        if not HAS_MILVUS:
            return False

        def _run() -> bool:
            connections.connect(
                alias="default",
                host=settings.milvus.host,
                port=settings.milvus.port,
                user=settings.milvus.user or None,
                password=settings.milvus.password or None,
            )
            return True

        try:
            await asyncio.to_thread(_run)
            self._connected = True
            return True
        except Exception as exc:
            logger.warning(f"Milvus connect failed: {exc}")
            return False

    async def ensure_collection(self) -> bool:
        if self._collection_ready:
            return True
        if not await self._connect():
            return False

        def _run() -> bool:
            if utility.has_collection(self.collection_name):
                collection = Collection(self.collection_name)
                if not collection.has_index():
                    collection.create_index(
                        field_name="embedding",
                        index_params={
                            "index_type": settings.milvus.index_type,
                            "metric_type": settings.milvus.metric_type,
                            "params": {"M": settings.milvus.hnsw_m, "efConstruction": settings.milvus.hnsw_ef_construction},
                        },
                    )
                collection.load()
                return True

            schema = CollectionSchema(
                fields=[
                    FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=96, is_primary=True, auto_id=False),
                    FieldSchema(name="tenant_id", dtype=DataType.VARCHAR, max_length=64),
                    FieldSchema(name="doc_id", dtype=DataType.VARCHAR, max_length=64),
                    FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=64),
                    FieldSchema(name="doc_type", dtype=DataType.VARCHAR, max_length=32),
                    FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=8192),
                    FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=settings.milvus.dimension),
                ],
                description="Contract chunk vectors",
            )
            collection = Collection(name=self.collection_name, schema=schema)
            collection.create_index(
                field_name="embedding",
                index_params={
                    "index_type": settings.milvus.index_type,
                    "metric_type": settings.milvus.metric_type,
                    "params": {"M": settings.milvus.hnsw_m, "efConstruction": settings.milvus.hnsw_ef_construction},
                },
            )
            collection.load()
            return True

        try:
            self._collection_ready = await asyncio.to_thread(_run)
            return self._collection_ready
        except Exception as exc:
            logger.warning(f"Milvus ensure collection failed: {exc}")
            return False

    async def upsert_chunks(self, rows: list[dict[str, Any]]) -> bool:
        if not rows:
            return True
        if not await self.ensure_collection():
            return False

        def _run() -> bool:
            collection = Collection(self.collection_name)
            payload = [
                [str(item["id"]) for item in rows],
                [str(item["tenant_id"]) for item in rows],
                [str(item["doc_id"]) for item in rows],
                [str(item["chunk_id"]) for item in rows],
                [str(item.get("doc_type", ""))[:32] for item in rows],
                [str(item.get("content", ""))[:8192] for item in rows],
                [item["embedding"] for item in rows],
            ]
            collection.upsert(payload)
            collection.flush()
            return True

        try:
            return await asyncio.to_thread(_run)
        except Exception as exc:
            logger.warning(f"Milvus upsert failed: {exc}")
            return False

    async def search(self, *, tenant_id: str, query_vector: list[float], top_k: int) -> list[dict]:
        if not await self.ensure_collection():
            return []

        def _run() -> list[dict]:
            collection = Collection(self.collection_name)
            search_params = {"metric_type": settings.milvus.metric_type, "params": {"ef": settings.milvus.hnsw_ef_search}}
            expr = f'tenant_id == "{tenant_id}"'
            results = collection.search(
                data=[query_vector],
                anns_field="embedding",
                param=search_params,
                limit=max(top_k, 1),
                expr=expr,
                output_fields=["tenant_id", "doc_id", "chunk_id", "doc_type", "content"],
            )
            hits: list[dict] = []
            if not results:
                return hits
            for item in results[0]:
                fields = item.fields or {}
                hits.append(
                    {
                        "chunk_id": str(fields.get("chunk_id") or ""),
                        "doc_id": str(fields.get("doc_id") or ""),
                        "doc_type": str(fields.get("doc_type") or ""),
                        "content": str(fields.get("content") or ""),
                        "score": float(getattr(item, "distance", 0.0)),
                    }
                )
            return hits

        try:
            return await asyncio.to_thread(_run)
        except Exception as exc:
            logger.warning(f"Milvus search failed: {exc}")
            return []

    async def health(self) -> ConnectorHealth:
        started = time.perf_counter()
        if not await self._connect():
            return ConnectorHealth(name="milvus", ok=False, detail="connect failed")
        ok = await self.ensure_collection()
        latency_ms = (time.perf_counter() - started) * 1000
        return ConnectorHealth(
            name="milvus",
            ok=ok,
            latency_ms=latency_ms,
            detail=f"collection={self.collection_name}",
        )


milvus_connector = MilvusConnector()

