"""Idempotency middleware with Redis-first storage."""

from __future__ import annotations

import base64
import json
import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.redis_client import get_redis_client


class InMemoryIdempotencyStore:
    def __init__(self, ttl: int = 3600):
        self._responses: dict[str, dict] = {}
        self._processing: dict[str, float] = {}
        self._ttl = ttl

    def get_response(self, key: str) -> dict | None:
        entry = self._responses.get(key)
        if not entry:
            return None
        if time.time() - entry["timestamp"] > self._ttl:
            self._responses.pop(key, None)
            return None
        return entry

    def set_response(self, key: str, value: dict) -> None:
        value["timestamp"] = time.time()
        self._responses[key] = value

    def try_start_processing(self, key: str) -> bool:
        ts = self._processing.get(key)
        if ts and time.time() - ts < self._ttl:
            return False
        self._processing[key] = time.time()
        return True

    def stop_processing(self, key: str) -> None:
        self._processing.pop(key, None)

    def is_processing(self, key: str) -> bool:
        ts = self._processing.get(key)
        if not ts:
            return False
        if time.time() - ts > self._ttl:
            self._processing.pop(key, None)
            return False
        return True


_memory_store = InMemoryIdempotencyStore()


def _safe_headers(headers) -> dict:
    copied = dict(headers)
    copied.pop("content-length", None)
    copied.pop("Content-Length", None)
    return copied


class IdempotencyMiddleware(BaseHTTPMiddleware):
    IDEMPOTENT_METHODS = {"POST", "PUT", "PATCH"}
    TTL_SECONDS = 3600

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method not in self.IDEMPOTENT_METHODS:
            return await call_next(request)

        key = request.headers.get("X-Idempotency-Key")
        if not key:
            return await call_next(request)

        user_id = getattr(request.state, "user_id", "anonymous")
        composite_key = f"{user_id}:{request.url.path}:{key}"
        redis = await get_redis_client()

        replay = await self._load_cached_response(redis, composite_key)
        if replay:
            response = Response(
                content=replay["body"],
                status_code=int(replay["status_code"]),
                headers=_safe_headers(replay["headers"]),
            )
            response.headers["X-Idempotency-Replay"] = "true"
            return response

        started = await self._try_mark_processing(redis, composite_key)
        if not started:
            return JSONResponse(
                status_code=409,
                content={
                    "code": 409,
                    "message": "Request is already being processed",
                    "detail": "DUPLICATE_REQUEST",
                },
            )

        try:
            response = await call_next(request)
            if response.media_type == "text/event-stream":
                await self._clear_processing(redis, composite_key)
                return response

            body = b""
            async for chunk in response.body_iterator:
                if isinstance(chunk, str):
                    chunk = chunk.encode("utf-8")
                body += chunk
            headers = _safe_headers(response.headers)

            await self._store_response(
                redis,
                composite_key,
                {
                    "status_code": response.status_code,
                    "body": body,
                    "headers": headers,
                },
            )
            await self._clear_processing(redis, composite_key)
            return Response(
                content=body,
                status_code=response.status_code,
                headers=headers,
                media_type=response.media_type,
            )
        except Exception:
            await self._clear_processing(redis, composite_key)
            raise

    async def _load_cached_response(self, redis, key: str) -> dict | None:
        if redis:
            raw = await redis.get(f"idem:resp:{key}")
            if raw:
                parsed = json.loads(raw.decode("utf-8"))
                return {
                    "status_code": parsed["status_code"],
                    "body": base64.b64decode(parsed["body"]),
                    "headers": parsed["headers"],
                }
            if await redis.exists(f"idem:proc:{key}"):
                return None

        entry = _memory_store.get_response(key)
        if entry:
            return entry
        if _memory_store.is_processing(key):
            return None
        return None

    async def _try_mark_processing(self, redis, key: str) -> bool:
        if redis:
            return bool(await redis.set(f"idem:proc:{key}", b"1", nx=True, ex=self.TTL_SECONDS))
        return _memory_store.try_start_processing(key)

    async def _store_response(self, redis, key: str, payload: dict) -> None:
        if redis:
            serialized = json.dumps(
                {
                    "status_code": payload["status_code"],
                    "body": base64.b64encode(payload["body"]).decode("utf-8"),
                    "headers": payload["headers"],
                }
            ).encode("utf-8")
            await redis.set(f"idem:resp:{key}", serialized, ex=self.TTL_SECONDS)
            await redis.delete(f"idem:proc:{key}")
            return
        _memory_store.set_response(key, payload)
        _memory_store.stop_processing(key)

    async def _clear_processing(self, redis, key: str) -> None:
        if redis:
            await redis.delete(f"idem:proc:{key}")
            return
        _memory_store.stop_processing(key)
