"""
中间件 #3: 结构化请求/响应日志中间件
JSON格式日志，集成ELK，支持日志关联
"""

import time
import json
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from loguru import logger

from app.middleware.request_id import get_request_id, get_tenant_id


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """结构化请求/响应日志"""

    SKIP_PATHS = {"/health", "/ready", "/metrics", "/docs", "/openapi.json", "/favicon.ico"}
    SENSITIVE_HEADERS = {"authorization", "cookie", "x-api-key", "x-csrf-token"}

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path in self.SKIP_PATHS:
            return await call_next(request)

        request_id = get_request_id()
        tenant_id = get_tenant_id()
        start_time = time.perf_counter()

        # 安全过滤请求头
        safe_headers = {
            k: ("***" if k.lower() in self.SENSITIVE_HEADERS else v)
            for k, v in request.headers.items()
        }

        # 记录请求日志
        request_log = {
            "event": "request_start",
            "request_id": request_id,
            "tenant_id": tenant_id,
            "method": request.method,
            "path": request.url.path,
            "query_params": dict(request.query_params),
            "client_ip": request.client.host if request.client else "unknown",
            "user_agent": request.headers.get("user-agent", ""),
            "content_type": request.headers.get("content-type", ""),
            "content_length": request.headers.get("content-length", "0"),
        }
        logger.info(json.dumps(request_log, ensure_ascii=False))

        try:
            response = await call_next(request)
            duration_ms = (time.perf_counter() - start_time) * 1000

            # 记录响应日志
            response_log = {
                "event": "request_end",
                "request_id": request_id,
                "tenant_id": tenant_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 2),
                "response_content_type": response.headers.get("content-type", ""),
            }

            if response.status_code >= 500:
                logger.error(json.dumps(response_log, ensure_ascii=False))
            elif response.status_code >= 400:
                logger.warning(json.dumps(response_log, ensure_ascii=False))
            else:
                logger.info(json.dumps(response_log, ensure_ascii=False))

            # 慢请求告警
            if duration_ms > 5000:
                logger.warning(
                    json.dumps({
                        "event": "slow_request",
                        "request_id": request_id,
                        "path": request.url.path,
                        "duration_ms": round(duration_ms, 2),
                    }, ensure_ascii=False)
                )

            return response
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                json.dumps({
                    "event": "request_exception",
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                    "duration_ms": round(duration_ms, 2),
                }, ensure_ascii=False)
            )
            raise
