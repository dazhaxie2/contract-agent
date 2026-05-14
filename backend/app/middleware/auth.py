"""Authentication middleware with Bearer token and API key support."""

import uuid

from sqlalchemy import select
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.database import get_read_session
from app.core.security import decode_token
from app.middleware.request_id import tenant_id_ctx, user_id_ctx
from app.models.user import User


def _auth_error(status_code: int, message: str, detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"code": status_code, "message": message, "detail": detail},
    )


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """Authenticate request and inject user/tenant context."""

    PUBLIC_PATHS = {
        "/",
        "/health",
        "/ready",
        "/metrics",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/api/v1/auth/login",
        "/api/v1/auth/register",
        "/api/v1/auth/refresh",
    }
    PUBLIC_PREFIXES = ("/docs", "/redoc", "/static")

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        if path in self.PUBLIC_PATHS or path.startswith(self.PUBLIC_PREFIXES):
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            payload = decode_token(token)
            if payload and payload.get("type") == "access":
                tenant_id = payload.get("tenant_id") or request.headers.get("X-Tenant-ID") or "default"
                user_id = payload.get("sub") or ""
                try:
                    user_uuid = uuid.UUID(str(user_id))
                except (TypeError, ValueError):
                    return _auth_error(401, "Token invalid or expired", "INVALID_TOKEN_SUBJECT")

                async with get_read_session() as db:
                    user = await db.scalar(
                        select(User).where(
                            User.id == user_uuid,
                            User.tenant_id == tenant_id,
                        )
                    )
                if not user:
                    return _auth_error(401, "User no longer exists", "USER_NOT_FOUND")
                if not user.is_active:
                    return _auth_error(403, "User disabled", "USER_DISABLED")

                request.state.user_id = str(user.id)
                request.state.username = user.username
                request.state.user_role = user.role
                request.state.tenant_id = user.tenant_id

                user_token = user_id_ctx.set(str(user.id))
                tenant_token = tenant_id_ctx.set(user.tenant_id)
                try:
                    return await call_next(request)
                finally:
                    tenant_id_ctx.reset(tenant_token)
                    user_id_ctx.reset(user_token)
            return _auth_error(401, "Token invalid or expired", "INVALID_TOKEN")

        api_key = request.headers.get("X-API-Key", "")
        if api_key:
            tenant_id = request.headers.get("X-Tenant-ID", "default")
            user_id = request.headers.get("X-User-ID", "api_user")
            request.state.user_id = user_id
            request.state.user_role = "api_client"
            request.state.tenant_id = tenant_id

            user_token = user_id_ctx.set(user_id)
            tenant_token = tenant_id_ctx.set(tenant_id)
            try:
                return await call_next(request)
            finally:
                tenant_id_ctx.reset(tenant_token)
                user_id_ctx.reset(user_token)

        return _auth_error(401, "Missing credentials", "MISSING_CREDENTIALS")
