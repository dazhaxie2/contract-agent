"""
中间件 #4: JWT认证中间件
支持Bearer Token、API Key双模式认证
"""

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.security import decode_token
from app.middleware.request_id import user_id_ctx


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """JWT + API Key 双模式认证"""

    # 不需要认证的路径
    PUBLIC_PATHS = {
        "/", "/health", "/ready", "/metrics", "/docs", "/redoc",
        "/openapi.json", "/api/v1/auth/login", "/api/v1/auth/register",
        "/api/v1/auth/refresh",
    }
    PUBLIC_PREFIXES = ("/docs", "/redoc", "/static")

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path

        # 跳过公开路径
        if path in self.PUBLIC_PATHS or path.startswith(self.PUBLIC_PREFIXES):
            return await call_next(request)

        # 尝试Bearer Token认证
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            payload = decode_token(token)
            if payload and payload.get("type") == "access":
                request.state.user_id = payload.get("sub")
                request.state.user_role = payload.get("role", "viewer")
                request.state.tenant_id = payload.get("tenant_id", "default")
                token = user_id_ctx.set(payload.get("sub", ""))
                try:
                    return await call_next(request)
                finally:
                    user_id_ctx.reset(token)
            return JSONResponse(
                status_code=401,
                content={"code": 401, "message": "Token无效或已过期", "detail": "INVALID_TOKEN"},
            )

        # 尝试API Key认证
        api_key = request.headers.get("X-API-Key", "")
        if api_key:
            # API Key验证逻辑(查Redis/DB)
            # 简化示例：从请求头获取
            request.state.user_id = "api_user"
            request.state.user_role = "api_client"
            request.state.tenant_id = request.headers.get("X-Tenant-ID", "default")
            return await call_next(request)

        return JSONResponse(
            status_code=401,
            content={"code": 401, "message": "未提供认证凭据", "detail": "MISSING_CREDENTIALS"},
        )
