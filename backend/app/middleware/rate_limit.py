"""Rate limit middleware with Redis sliding-window support."""

from __future__ import annotations

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import settings
from app.core.redis_client import get_redis_client


class InMemorySlidingWindow:
    def __init__(self) -> None:
        self._windows: dict[str, list[float]] = {}

    def is_allowed(self, key: str, max_requests: int, window_seconds: int) -> tuple[bool, dict]:
        now = time.time()
        cutoff = now - window_seconds
        bucket = self._windows.setdefault(key, [])
        bucket[:] = [item for item in bucket if item > cutoff]
        current = len(bucket)

        if current >= max_requests:
            retry_after = int((bucket[0] + window_seconds) - now) + 1 if bucket else 1
            return False, {
                "X-RateLimit-Limit": str(max_requests),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(now + retry_after)),
                "Retry-After": str(max(1, retry_after)),
            }

        bucket.append(now)
        remaining = max_requests - len(bucket)
        return True, {
            "X-RateLimit-Limit": str(max_requests),
            "X-RateLimit-Remaining": str(max(0, remaining)),
            "X-RateLimit-Reset": str(int(now + window_seconds)),
        }


_memory_limiter = InMemorySlidingWindow()


async def _redis_is_allowed(key: str, max_requests: int, window_seconds: int) -> tuple[bool, dict] | None:
    redis = await get_redis_client()
    if redis is None:
        return None

    now = time.time()
    now_ms = int(now * 1000)
    window_start_ms = int((now - window_seconds) * 1000)
    member = f"{now_ms}-{uuid.uuid4().hex}"
    redis_key = f"ratelimit:{key}"

    pipe = redis.pipeline()
    pipe.zremrangebyscore(redis_key, 0, window_start_ms)
    pipe.zcard(redis_key)
    pipe.zadd(redis_key, {member: now_ms})
    pipe.expire(redis_key, window_seconds + 1)
    _removed, current, _added, _ = await pipe.execute()

    if int(current) >= max_requests:
        # Revert add when over quota.
        await redis.zrem(redis_key, member)
        reset_ts = int(now + window_seconds)
        return False, {
            "X-RateLimit-Limit": str(max_requests),
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": str(reset_ts),
            "Retry-After": str(window_seconds),
        }

    remaining = max_requests - int(current) - 1
    return True, {
        "X-RateLimit-Limit": str(max_requests),
        "X-RateLimit-Remaining": str(max(0, remaining)),
        "X-RateLimit-Reset": str(int(now + window_seconds)),
    }


class RateLimitMiddleware(BaseHTTPMiddleware):
    SKIP_PATHS = {"/health", "/ready", "/metrics"}

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not settings.rate_limit.enabled:
            return await call_next(request)
        if request.url.path in self.SKIP_PATHS or request.url.path.startswith(("/docs", "/redoc", "/openapi")):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        user_id = str(getattr(request.state, "user_id", ""))
        path = request.url.path

        for name, key, limit, period in [
            ("global", "global", settings.rate_limit.global_rate, settings.rate_limit.global_period),
            ("ip", f"ip:{client_ip}", settings.rate_limit.api_rate * 2, settings.rate_limit.api_period),
            ("user", f"user:{user_id}", settings.rate_limit.user_rate, settings.rate_limit.user_period),
        ]:
            if name == "user" and not user_id:
                continue
            allowed, headers = await self._check_limit(key, limit, period)
            if not allowed:
                return self._rate_limit_response("RATE_LIMIT_EXCEEDED", headers)

        if path.startswith("/api/v1/agents") and request.method == "POST":
            llm_key = f"llm:{user_id or client_ip}"
            allowed, headers = await self._check_limit(llm_key, settings.rate_limit.llm_rate, settings.rate_limit.llm_period)
            if not allowed:
                return self._rate_limit_response("LLM_RATE_LIMIT_EXCEEDED", headers)

        response = await call_next(request)
        return response

    async def _check_limit(self, key: str, max_requests: int, window_seconds: int) -> tuple[bool, dict]:
        redis_result = await _redis_is_allowed(key, max_requests, window_seconds)
        if redis_result is not None:
            return redis_result
        return _memory_limiter.is_allowed(key, max_requests, window_seconds)

    @staticmethod
    def _rate_limit_response(message: str, headers: dict) -> JSONResponse:
        response = JSONResponse(
            status_code=429,
            content={"code": 429, "message": message, "detail": "RATE_LIMIT_EXCEEDED"},
        )
        for k, v in headers.items():
            response.headers[k] = v
        return response
