"""
中间件 #14: 幂等性中间件
基于 X-Idempotency-Key 实现POST/PUT请求幂等，防重复提交
"""

import hashlib
import json
import time
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class IdempotencyStore:
    """幂等性存储 (内存版，生产环境用Redis)"""

    def __init__(self, ttl: int = 3600):
        self._store: dict[str, dict] = {}
        self._ttl = ttl

    def get(self, key: str) -> dict | None:
        entry = self._store.get(key)
        if entry and time.time() - entry["timestamp"] < self._ttl:
            return entry
        if entry:
            del self._store[key]
        return None

    def set(self, key: str, status_code: int, body: bytes, headers: dict):
        self._store[key] = {
            "status_code": status_code,
            "body": body,
            "headers": headers,
            "timestamp": time.time(),
        }

    def set_processing(self, key: str):
        self._store[key] = {"processing": True, "timestamp": time.time()}

    def is_processing(self, key: str) -> bool:
        entry = self._store.get(key)
        return bool(entry and entry.get("processing"))


_idempotency_store = IdempotencyStore()


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """请求幂等性保证"""

    IDEMPOTENT_METHODS = {"POST", "PUT", "PATCH"}

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method not in self.IDEMPOTENT_METHODS:
            return await call_next(request)

        idempotency_key = request.headers.get("X-Idempotency-Key")
        if not idempotency_key:
            return await call_next(request)

        # 构建复合幂等键
        user_id = getattr(request.state, "user_id", "anonymous")
        composite_key = f"{user_id}:{request.url.path}:{idempotency_key}"

        # 检查是否正在处理
        if _idempotency_store.is_processing(composite_key):
            return JSONResponse(
                status_code=409,
                content={"code": 409, "message": "请求正在处理中，请勿重复提交", "detail": "DUPLICATE_REQUEST"},
            )

        # 检查是否有缓存结果
        cached = _idempotency_store.get(composite_key)
        if cached and not cached.get("processing"):
            response = Response(
                content=cached["body"],
                status_code=cached["status_code"],
                headers=cached["headers"],
            )
            response.headers["X-Idempotency-Replay"] = "true"
            return response

        # 标记正在处理
        _idempotency_store.set_processing(composite_key)

        try:
            response = await call_next(request)

            # 缓存响应
            body = b""
            async for chunk in response.body_iterator:
                if isinstance(chunk, str):
                    chunk = chunk.encode()
                body += chunk

            _idempotency_store.set(
                composite_key,
                response.status_code,
                body,
                dict(response.headers),
            )

            return Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )
        except Exception:
            # 失败时清除处理标记
            _idempotency_store._store.pop(composite_key, None)
            raise
