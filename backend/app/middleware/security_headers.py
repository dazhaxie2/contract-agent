"""
中间件 #12: 安全响应头中间件
注入OWASP推荐安全头，防XSS/点击劫持/MIME嗅探
"""

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """OWASP安全响应头"""

    SECURITY_HEADERS = {
        # 防XSS
        "X-Content-Type-Options": "nosniff",
        "X-XSS-Protection": "1; mode=block",
        # 防点击劫持
        "X-Frame-Options": "DENY",
        # 内容安全策略
        "Content-Security-Policy": (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; "
            "font-src 'self' data:; "
            "connect-src 'self' ws: wss:; "
            "frame-ancestors 'none'"
        ),
        # HTTPS强制
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
        # 引用策略
        "Referrer-Policy": "strict-origin-when-cross-origin",
        # 权限策略
        "Permissions-Policy": (
            "camera=(), microphone=(), geolocation=(), "
            "payment=(), usb=(), magnetometer=()"
        ),
        # 缓存控制
        "Cache-Control": "no-store, no-cache, must-revalidate",
        "Pragma": "no-cache",
    }

    SWAGGER_PATHS = ("/docs", "/redoc", "/openapi.json")

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        path = request.url.path
        is_swagger = any(path == p or path.startswith(p + "/") for p in self.SWAGGER_PATHS)
        for header, value in self.SECURITY_HEADERS.items():
            if header in response.headers:
                continue
            if is_swagger and header == "Content-Security-Policy":
                continue
            response.headers[header] = value
        return response
