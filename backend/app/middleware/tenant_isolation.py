"""
中间件 #6: 多租户隔离中间件
实现企业级数据物理+逻辑双隔离，杜绝跨租户数据访问
"""

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.middleware.request_id import tenant_id_ctx


class TenantIsolationMiddleware(BaseHTTPMiddleware):
    """多租户数据隔离"""

    SKIP_PATHS = {"/health", "/ready", "/metrics", "/docs", "/openapi.json"}

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path in self.SKIP_PATHS or request.url.path.startswith(("/docs", "/redoc", "/static")):
            return await call_next(request)

        # 从认证信息获取租户ID
        tenant_id = getattr(request.state, "tenant_id", None)
        if not tenant_id:
            tenant_id = request.headers.get("X-Tenant-ID", "")

        if not tenant_id:
            # 公开路径不需要租户ID
            if request.url.path.startswith("/api/v1/auth"):
                return await call_next(request)
            return JSONResponse(
                status_code=400,
                content={"code": 400, "message": "缺少租户标识", "detail": "MISSING_TENANT_ID"},
            )

        # 租户ID合法性校验
        if not self._validate_tenant_id(tenant_id):
            return JSONResponse(
                status_code=400,
                content={"code": 400, "message": "无效的租户标识", "detail": "INVALID_TENANT_ID"},
            )

        # 设置租户上下文
        token = tenant_id_ctx.set(tenant_id)
        request.state.tenant_id = tenant_id

        try:
            response = await call_next(request)
            # 确保响应中包含租户标识
            response.headers["X-Tenant-ID"] = tenant_id
            return response
        finally:
            tenant_id_ctx.reset(token)

    @staticmethod
    def _validate_tenant_id(tenant_id: str) -> bool:
        """校验租户ID合法性"""
        if not tenant_id or len(tenant_id) > 64:
            return False
        # 只允许字母、数字、下划线、短横线
        return all(c.isalnum() or c in ("-", "_") for c in tenant_id)
