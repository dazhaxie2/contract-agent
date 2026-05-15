"""
中间件 #15: 多级缓存控制中间件
L1本地内存 -> L2 Redis分布式缓存，支持智能缓存策略
"""

import hashlib
import time
from collections import OrderedDict
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


class LRUCache:
    """L1 本地LRU内存缓存"""

    def __init__(self, maxsize: int = 1000, ttl: int = 300):
        self._cache: OrderedDict = OrderedDict()
        self._maxsize = maxsize
        self._ttl = ttl

    def get(self, key: str) -> dict | None:
        if key in self._cache:
            entry = self._cache[key]
            if time.time() - entry["time"] < self._ttl:
                self._cache.move_to_end(key)
                return entry
            del self._cache[key]
        return None

    def set(self, key: str, value: dict):
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = {**value, "time": time.time()}
        if len(self._cache) > self._maxsize:
            self._cache.popitem(last=False)

    def invalidate(self, pattern: str = ""):
        if not pattern:
            self._cache.clear()
        else:
            keys = [k for k in self._cache if pattern in k]
            for k in keys:
                del self._cache[k]


_l1_cache = LRUCache(maxsize=2000, ttl=300)


def _safe_headers(headers) -> dict:
    copied = dict(headers)
    copied.pop("content-length", None)
    copied.pop("Content-Length", None)
    return copied


class CacheControlMiddleware(BaseHTTPMiddleware):
    """多级缓存控制"""

    # 可缓存的GET路径及TTL配置
    CACHEABLE_ROUTES = {
        "/api/v1/models": 600,       # 模型配置10分钟
        "/api/v1/prompts": 300,      # 提示词5分钟
        "/api/v1/documents": 60,     # 文档列表1分钟
        "/api/v1/system/config": 300,
    }

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # 只缓存GET请求
        if request.method != "GET":
            # 写操作时失效相关缓存
            if request.method in ("POST", "PUT", "DELETE", "PATCH"):
                self._invalidate_related_cache(request.url.path)
            return await call_next(request)

        # 检查是否可缓存
        cache_ttl = self._get_cache_ttl(request.url.path)
        if not cache_ttl:
            return await call_next(request)

        # 客户端要求不缓存
        if request.headers.get("Cache-Control") == "no-cache":
            return await call_next(request)

        # 构建缓存键
        tenant_id = getattr(request.state, "tenant_id", "default")
        cache_key = self._build_cache_key(request, tenant_id)

        # L1 查找
        cached = _l1_cache.get(cache_key)
        if cached:
            response = Response(
                content=cached["body"],
                status_code=cached["status_code"],
                headers=_safe_headers(cached["headers"]),
                media_type="application/json",
            )
            response.headers["X-Cache"] = "HIT-L1"
            response.headers["X-Cache-Key"] = cache_key[:32]
            return response

        # 缓存未命中，执行请求
        response = await call_next(request)

        if response.status_code == 200:
            body = b""
            async for chunk in response.body_iterator:
                if isinstance(chunk, str):
                    chunk = chunk.encode()
                body += chunk

            _l1_cache.set(cache_key, {
                "body": body,
                "status_code": response.status_code,
                "headers": _safe_headers(response.headers),
            })

            new_response = Response(
                content=body,
                status_code=response.status_code,
                headers=_safe_headers(response.headers),
                media_type=response.media_type,
            )
            new_response.headers["X-Cache"] = "MISS"
            new_response.headers["Cache-Control"] = f"private, max-age={cache_ttl}"
            return new_response

        return response

    def _get_cache_ttl(self, path: str) -> int | None:
        for prefix, ttl in self.CACHEABLE_ROUTES.items():
            if path.startswith(prefix):
                return ttl
        return None

    @staticmethod
    def _build_cache_key(request: Request, tenant_id: str) -> str:
        raw = f"{tenant_id}:{request.url.path}:{request.url.query}"
        return hashlib.md5(raw.encode()).hexdigest()

    @staticmethod
    def _invalidate_related_cache(path: str):
        # 提取资源前缀，失效相关缓存
        parts = path.split("/")
        if len(parts) >= 4:
            resource = "/".join(parts[:4])
            _l1_cache.invalidate(resource)
