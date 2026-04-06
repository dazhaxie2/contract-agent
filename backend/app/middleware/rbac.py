"""
中间件 #5: RBAC权限控制中间件
基于角色的细粒度权限管控，最小权限原则
"""

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.security import Roles


# 路由 -> 所需权限映射
ROUTE_PERMISSIONS = {
    # 用户管理
    ("GET", "/api/v1/users"): "user:read",
    ("POST", "/api/v1/users"): "user:write",
    ("DELETE", "/api/v1/users"): "user:delete",
    # 模型配置
    ("GET", "/api/v1/models"): "model:read",
    ("POST", "/api/v1/models"): "model:write",
    ("PUT", "/api/v1/models"): "model:write",
    ("POST", "/api/v1/models/deploy"): "model:deploy",
    # 提示词管理
    ("GET", "/api/v1/prompts"): "prompt:read",
    ("POST", "/api/v1/prompts"): "prompt:write",
    ("PUT", "/api/v1/prompts"): "prompt:write",
    ("POST", "/api/v1/prompts/publish"): "prompt:publish",
    # 文档管理
    ("GET", "/api/v1/documents"): "document:read",
    ("POST", "/api/v1/documents"): "document:write",
    ("DELETE", "/api/v1/documents"): "document:delete",
    # Agent执行
    ("GET", "/api/v1/agents"): "agent:read",
    ("POST", "/api/v1/agents"): "agent:execute",
    # 系统管理
    ("GET", "/api/v1/system"): "system:read",
    ("PUT", "/api/v1/system"): "system:config",
}


class RBACMiddleware(BaseHTTPMiddleware):
    """RBAC权限校验"""

    SKIP_PATHS = {
        "/", "/health", "/ready", "/metrics", "/docs", "/redoc",
        "/openapi.json", "/api/v1/auth/login", "/api/v1/auth/register",
        "/api/v1/auth/refresh",
    }

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path in self.SKIP_PATHS or request.url.path.startswith(("/docs", "/redoc", "/static")):
            return await call_next(request)

        role = getattr(request.state, "user_role", None)
        if not role:
            return await call_next(request)

        # 查找匹配的权限规则
        required_permission = self._find_permission(request.method, request.url.path)
        if required_permission and not Roles.has_permission(role, required_permission):
            return JSONResponse(
                status_code=403,
                content={
                    "code": 403,
                    "message": f"权限不足: 需要 {required_permission} 权限",
                    "detail": "INSUFFICIENT_PERMISSIONS",
                    "required_permission": required_permission,
                    "current_role": role,
                },
            )

        return await call_next(request)

    def _find_permission(self, method: str, path: str) -> str | None:
        # 精确匹配
        key = (method, path)
        if key in ROUTE_PERMISSIONS:
            return ROUTE_PERMISSIONS[key]

        # 前缀匹配 (处理带ID的路径)
        for (route_method, route_path), permission in ROUTE_PERMISSIONS.items():
            if method == route_method and path.startswith(route_path):
                return permission

        return None
