"""Redis-backed caching for embeddings, retrieval results, and conversation context."""

from __future__ import annotations

import hashlib
import json

from loguru import logger

from app.core.config import settings

try:
    import redis.asyncio as aioredis

    HAS_REDIS = True
except Exception:
    HAS_REDIS = False

_redis_client: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis | None:
    global _redis_client
    if not HAS_REDIS:
        return None
    if _redis_client is not None:
        return _redis_client
    try:
        _redis_client = aioredis.from_url(
            f"redis://{settings.redis.host}:{settings.redis.port}/{settings.redis.cache_db}",
            password=settings.redis.password or None,
            decode_responses=True,
            max_connections=settings.redis.max_connections,
            socket_timeout=settings.redis.socket_timeout,
        )
        await _redis_client.ping()
        return _redis_client
    except Exception as exc:
        logger.warning(f"Redis cache connection failed: {exc}")
        _redis_client = None
        return None


def _cache_key(prefix: str, *parts: str) -> str:
    raw = ":".join(parts)
    h = hashlib.md5(raw.encode()).hexdigest()[:12]
    return f"cache:{prefix}:{h}"


class EmbeddingCache:
    async def get(self, text: str, model: str = "") -> list[float] | None:
        client = await get_redis()
        if not client:
            return None
        key = _cache_key("emb", model, text)
        try:
            data = await client.get(key)
            if data:
                return json.loads(data)
        except Exception:
            pass
        return None

    async def set(self, text: str, model: str, embedding: list[float], ttl: int = 3600) -> None:
        client = await get_redis()
        if not client:
            return
        key = _cache_key("emb", model, text)
        try:
            await client.setex(key, ttl, json.dumps(embedding))
        except Exception:
            pass


class RetrievalCache:
    async def get(self, query: str, tenant_id: str, top_k: int = 10) -> list[dict] | None:
        client = await get_redis()
        if not client:
            return None
        key = _cache_key("rag", tenant_id, str(top_k), query)
        try:
            data = await client.get(key)
            if data:
                return json.loads(data)
        except Exception:
            pass
        return None

    async def set(self, query: str, tenant_id: str, top_k: int, results: list[dict], ttl: int = 300) -> None:
        client = await get_redis()
        if not client:
            return
        key = _cache_key("rag", tenant_id, str(top_k), query)
        try:
            await client.setex(key, ttl, json.dumps(results, ensure_ascii=False))
        except Exception:
            pass


class ContextCache:
    async def get(self, session_id: str, tenant_id: str) -> str | None:
        client = await get_redis()
        if not client:
            return None
        key = _cache_key("ctx", tenant_id, session_id)
        try:
            return await client.get(key)
        except Exception:
            return None

    async def set(self, session_id: str, tenant_id: str, context: str, ttl: int = 300) -> None:
        client = await get_redis()
        if not client:
            return
        key = _cache_key("ctx", tenant_id, session_id)
        try:
            await client.setex(key, ttl, context)
        except Exception:
            pass


embedding_cache = EmbeddingCache()
retrieval_cache = RetrievalCache()
context_cache = ContextCache()
