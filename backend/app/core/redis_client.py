"""Shared Redis client with graceful fallback."""

from __future__ import annotations

from typing import Optional

from loguru import logger

from app.core.config import settings

try:
    from redis.asyncio import Redis

    HAS_REDIS = True
except Exception:  # pragma: no cover - import fallback
    Redis = object  # type: ignore[assignment]
    HAS_REDIS = False


_redis_client: Optional[Redis] = None
_redis_unavailable = False


async def get_redis_client() -> Redis | None:
    global _redis_client
    global _redis_unavailable

    if _redis_unavailable or not HAS_REDIS:
        return None
    if _redis_client is not None:
        return _redis_client

    try:
        _redis_client = Redis(
            host=settings.redis.host,
            port=settings.redis.port,
            password=settings.redis.password or None,
            db=settings.redis.db,
            socket_timeout=settings.redis.socket_timeout,
            decode_responses=False,
            max_connections=settings.redis.max_connections,
        )
        await _redis_client.ping()
        return _redis_client
    except Exception as exc:
        logger.warning(f"Redis unavailable, using in-memory fallback: {exc}")
        _redis_unavailable = True
        _redis_client = None
        return None
