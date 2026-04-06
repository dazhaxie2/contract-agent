"""
中间件 #10: CORS跨域配置中间件
支持动态白名单、预检缓存、凭证传递
"""

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings


class CORSConfigMiddleware(BaseHTTPMiddleware):
    """增强型CORS跨域处理"""

    def __init__(self, app):
        super().__init__(app)
        self.allowed_origins = set(
            origin.strip() for origin in settings.security.cors_origins.split(",") if origin.strip()
        )
        self.allowed_methods = {"GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"}
        self.allowed_headers = {
            "Authorization", "Content-Type", "X-Request-ID", "X-Tenant-ID",
            "X-API-Key", "X-Trace-ID", "Accept", "Accept-Language",
            "Cache-Control", "X-Idempotency-Key",
        }
        self.expose_headers = {
            "X-Request-ID", "X-Trace-ID", "X-Span-ID", "X-RateLimit-Limit",
            "X-RateLimit-Remaining", "X-RateLimit-Reset", "X-Tenant-ID",
        }

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        origin = request.headers.get("Origin", "")

        # 预检请求
        if request.method == "OPTIONS":
            response = Response(status_code=204)
            self._set_cors_headers(response, origin)
            response.headers["Access-Control-Max-Age"] = "86400"  # 预检缓存24小时
            return response

        response = await call_next(request)
        self._set_cors_headers(response, origin)
        return response

    def _set_cors_headers(self, response: Response, origin: str):
        if origin in self.allowed_origins or "*" in self.allowed_origins:
            response.headers["Access-Control-Allow-Origin"] = origin or "*"
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Methods"] = ", ".join(self.allowed_methods)
            response.headers["Access-Control-Allow-Headers"] = ", ".join(self.allowed_headers)
            response.headers["Access-Control-Expose-Headers"] = ", ".join(self.expose_headers)
            response.headers["Vary"] = "Origin"
