"""
中间件 #19: API版本控制中间件
支持URL路径版本(v1/v2)和Header版本(Accept-Version)
"""

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class APIVersionMiddleware(BaseHTTPMiddleware):
    """API版本控制与路由"""

    SUPPORTED_VERSIONS = {"v1", "v2"}
    DEFAULT_VERSION = "v1"
    DEPRECATED_VERSIONS = {"v0"}

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path

        # 非API路径跳过
        if not path.startswith("/api/"):
            return await call_next(request)

        # 从URL提取版本
        parts = path.split("/")
        url_version = parts[2] if len(parts) > 2 else None

        # 从Header提取版本
        header_version = request.headers.get("Accept-Version", "")

        # 确定最终版本
        version = url_version or header_version or self.DEFAULT_VERSION

        # 版本校验
        if version in self.DEPRECATED_VERSIONS:
            return JSONResponse(
                status_code=410,
                content={
                    "code": 410,
                    "message": f"API版本 {version} 已废弃，请升级到 {self.DEFAULT_VERSION}",
                    "detail": "API_VERSION_DEPRECATED",
                    "supported_versions": list(self.SUPPORTED_VERSIONS),
                },
            )

        if version not in self.SUPPORTED_VERSIONS:
            return JSONResponse(
                status_code=400,
                content={
                    "code": 400,
                    "message": f"不支持的API版本: {version}",
                    "detail": "UNSUPPORTED_API_VERSION",
                    "supported_versions": list(self.SUPPORTED_VERSIONS),
                },
            )

        # 注入版本信息
        request.state.api_version = version

        response = await call_next(request)
        response.headers["X-API-Version"] = version
        response.headers["X-API-Deprecated"] = "false"
        return response
