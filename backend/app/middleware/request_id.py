"""
中间件 #1: 请求ID中间件
为每个请求生成唯一 Trace ID，贯穿全链路追踪
"""

import uuid
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from contextvars import ContextVar

# 全局请求ID上下文
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")
tenant_id_ctx: ContextVar[str] = ContextVar("tenant_id", default="")
user_id_ctx: ContextVar[str] = ContextVar("user_id", default="")


def get_request_id() -> str:
    return request_id_ctx.get("")


def get_tenant_id() -> str:
    return tenant_id_ctx.get("")


def get_user_id() -> str:
    return user_id_ctx.get("")


class RequestIDMiddleware(BaseHTTPMiddleware):
    """为每个HTTP请求注入唯一请求ID"""

    HEADER_NAME = "X-Request-ID"
    TRACE_HEADER = "X-Trace-ID"

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # 优先使用上游传入的请求ID (支持分布式追踪)
        req_id = (
            request.headers.get(self.HEADER_NAME)
            or request.headers.get(self.TRACE_HEADER)
            or str(uuid.uuid4())
        )

        # 设置上下文变量
        token = request_id_ctx.set(req_id)
        request.state.request_id = req_id

        try:
            response = await call_next(request)
            # 在响应头中注入请求ID
            response.headers[self.HEADER_NAME] = req_id
            response.headers[self.TRACE_HEADER] = req_id
            return response
        finally:
            request_id_ctx.reset(token)
