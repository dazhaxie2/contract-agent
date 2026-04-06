"""
中间件 #9: 请求超时控制中间件
防止长时间运行的请求阻塞服务，支持不同API路径差异化超时
"""

import asyncio
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class TimeoutMiddleware(BaseHTTPMiddleware):
    """请求超时控制"""

    # 路径 -> 超时时间(秒) 差异化配置
    TIMEOUT_MAP = {
        "/api/v1/agents/execute": 300,      # Agent执行最长5分钟
        "/api/v1/agents/chat": 120,          # 对话2分钟
        "/api/v1/documents/upload": 120,     # 文档上传2分钟
        "/api/v1/documents/process": 600,    # 文档处理10分钟
        "/api/v1/retrieval": 30,             # 检索30秒
    }
    DEFAULT_TIMEOUT = 60  # 默认60秒

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        timeout = self._get_timeout(request.url.path)

        try:
            response = await asyncio.wait_for(
                call_next(request),
                timeout=timeout,
            )
            return response
        except asyncio.TimeoutError:
            return JSONResponse(
                status_code=504,
                content={
                    "code": 504,
                    "message": f"请求处理超时 ({timeout}秒)",
                    "detail": "REQUEST_TIMEOUT",
                    "timeout_seconds": timeout,
                    "path": request.url.path,
                },
            )

    def _get_timeout(self, path: str) -> int:
        for prefix, timeout in self.TIMEOUT_MAP.items():
            if path.startswith(prefix):
                return timeout
        return self.DEFAULT_TIMEOUT
