"""
中间件 #7: 多维度限流中间件
支持全局/用户/API/LLM调用四级限流，基于Redis滑动窗口算法
"""

import time
import hashlib
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import settings
from app.middleware.request_id import get_request_id


class SlidingWindowRateLimiter:
    """滑动窗口限流器 (内存版，生产环境用Redis)"""

    def __init__(self):
        self._windows: dict[str, list[float]] = {}

    def is_allowed(self, key: str, max_requests: int, window_seconds: int) -> tuple[bool, dict]:
        now = time.time()
        window_start = now - window_seconds

        if key not in self._windows:
            self._windows[key] = []

        # 清理过期记录
        self._windows[key] = [t for t in self._windows[key] if t > window_start]

        current_count = len(self._windows[key])
        remaining = max(0, max_requests - current_count)

        if current_count >= max_requests:
            # 计算重试时间
            retry_after = int(self._windows[key][0] + window_seconds - now) + 1
            return False, {
                "X-RateLimit-Limit": str(max_requests),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(now + retry_after)),
                "Retry-After": str(retry_after),
            }

        self._windows[key].append(now)
        reset_time = int(now + window_seconds)
        return True, {
            "X-RateLimit-Limit": str(max_requests),
            "X-RateLimit-Remaining": str(remaining - 1),
            "X-RateLimit-Reset": str(reset_time),
        }


_limiter = SlidingWindowRateLimiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """四级限流: 全局 -> IP -> 用户 -> API"""

    SKIP_PATHS = {"/health", "/ready", "/metrics"}

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not settings.rate_limit.enabled or request.url.path in self.SKIP_PATHS:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        user_id = getattr(request.state, "user_id", None)
        path = request.url.path

        # Level 1: 全局限流
        allowed, headers = _limiter.is_allowed(
            "global", settings.rate_limit.global_rate, settings.rate_limit.global_period
        )
        if not allowed:
            return self._rate_limit_response("全局请求过于频繁", headers)

        # Level 2: IP限流
        ip_key = f"ip:{client_ip}"
        allowed, headers = _limiter.is_allowed(
            ip_key, settings.rate_limit.api_rate * 2, settings.rate_limit.api_period
        )
        if not allowed:
            return self._rate_limit_response("当前IP请求过于频繁", headers)

        # Level 3: 用户限流
        if user_id:
            user_key = f"user:{user_id}"
            allowed, headers = _limiter.is_allowed(
                user_key, settings.rate_limit.user_rate, settings.rate_limit.user_period
            )
            if not allowed:
                return self._rate_limit_response("用户请求过于频繁", headers)

        # Level 4: LLM专项限流
        if path.startswith("/api/v1/agents") and request.method == "POST":
            llm_key = f"llm:{user_id or client_ip}"
            allowed, headers = _limiter.is_allowed(
                llm_key, settings.rate_limit.llm_rate, settings.rate_limit.llm_period
            )
            if not allowed:
                return self._rate_limit_response("大模型调用频率超限", headers)

        response = await call_next(request)
        # 注入限流信息到响应头
        for k, v in headers.items():
            response.headers[k] = v
        return response

    @staticmethod
    def _rate_limit_response(message: str, headers: dict) -> JSONResponse:
        resp = JSONResponse(
            status_code=429,
            content={
                "code": 429,
                "message": message,
                "detail": "RATE_LIMIT_EXCEEDED",
            },
        )
        for k, v in headers.items():
            resp.headers[k] = v
        return resp
