"""
中间件 #22: 智能重试中间件
对上游服务临时故障自动重试，指数退避策略
"""

import asyncio
import time
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from loguru import logger

from app.middleware.request_id import get_request_id


class RetryMiddleware(BaseHTTPMiddleware):
    """智能重试 (仅对可重试的上游调用生效)"""

    # 可重试的状态码
    RETRYABLE_STATUS_CODES = {502, 503, 504}
    # 可重试的路径 (上游服务调用)
    RETRYABLE_PATHS = {
        "/api/v1/agents/execute",
        "/api/v1/retrieval/search",
    }
    MAX_RETRIES = 2
    BASE_DELAY = 0.5  # 基础退避时间(秒)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # 只对特定路径启用重试
        if request.url.path not in self.RETRYABLE_PATHS:
            return await call_next(request)

        # 只对POST请求重试（幂等保证由幂等中间件提供）
        if request.method != "POST":
            return await call_next(request)

        request_id = get_request_id()
        last_response = None

        for attempt in range(self.MAX_RETRIES + 1):
            try:
                response = await call_next(request)

                if response.status_code not in self.RETRYABLE_STATUS_CODES:
                    if attempt > 0:
                        response.headers["X-Retry-Count"] = str(attempt)
                    return response

                last_response = response
                if attempt < self.MAX_RETRIES:
                    delay = self.BASE_DELAY * (2 ** attempt)
                    logger.warning(
                        f"Retry attempt {attempt + 1}/{self.MAX_RETRIES} "
                        f"for {request.url.path} | status={response.status_code} | "
                        f"delay={delay}s | request_id={request_id}"
                    )
                    await asyncio.sleep(delay)

            except Exception as exc:
                if attempt < self.MAX_RETRIES:
                    delay = self.BASE_DELAY * (2 ** attempt)
                    logger.warning(
                        f"Retry attempt {attempt + 1}/{self.MAX_RETRIES} "
                        f"for {request.url.path} | error={exc} | "
                        f"delay={delay}s | request_id={request_id}"
                    )
                    await asyncio.sleep(delay)
                else:
                    raise

        if last_response:
            last_response.headers["X-Retry-Count"] = str(self.MAX_RETRIES)
            last_response.headers["X-Retry-Exhausted"] = "true"
        return last_response
