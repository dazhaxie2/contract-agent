"""Tenant isolation middleware."""

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.middleware.request_id import tenant_id_ctx


class TenantIsolationMiddleware(BaseHTTPMiddleware):
    """Inject tenant scope into request context."""

    SKIP_PATHS = {"/health", "/ready", "/metrics", "/docs", "/openapi.json"}

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path in self.SKIP_PATHS or request.url.path.startswith(("/docs", "/redoc", "/static")):
            return await call_next(request)

        tenant_id = getattr(request.state, "tenant_id", None)
        if not tenant_id:
            tenant_id = request.headers.get("X-Tenant-ID", "")
        if not tenant_id:
            tenant_id = "default"

        if not self._validate_tenant_id(tenant_id):
            return JSONResponse(
                status_code=400,
                content={"code": 400, "message": "Invalid tenant id", "detail": "INVALID_TENANT_ID"},
            )

        token = tenant_id_ctx.set(tenant_id)
        request.state.tenant_id = tenant_id

        try:
            response = await call_next(request)
            response.headers["X-Tenant-ID"] = tenant_id
            return response
        finally:
            tenant_id_ctx.reset(token)

    @staticmethod
    def _validate_tenant_id(tenant_id: str) -> bool:
        if not tenant_id or len(tenant_id) > 64:
            return False
        return all(c.isalnum() or c in ("-", "_") for c in tenant_id)
