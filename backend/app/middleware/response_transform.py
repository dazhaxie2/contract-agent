"""
中间件 #23: 统一响应格式转换中间件
将所有API响应包装为统一的标准格式
"""

import json
import time
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.middleware.request_id import get_request_id


class ResponseTransformMiddleware(BaseHTTPMiddleware):
    """统一响应格式"""

    SKIP_PATHS = {"/health", "/ready", "/metrics", "/docs", "/redoc", "/openapi.json"}
    SKIP_PREFIXES = ("/docs", "/redoc", "/static")

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path

        if path in self.SKIP_PATHS or path.startswith(self.SKIP_PREFIXES):
            return await call_next(request)

        start_time = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # 只处理JSON响应
        content_type = response.headers.get("Content-Type", "")
        if "application/json" not in content_type:
            return response

        # 读取原始响应
        body = b""
        async for chunk in response.body_iterator:
            if isinstance(chunk, str):
                chunk = chunk.encode()
            body += chunk

        try:
            original_data = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )

        # 如果已经是标准格式则跳过
        if isinstance(original_data, dict) and "code" in original_data and "message" in original_data:
            return Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )

        request_id = get_request_id()
        is_success = 200 <= response.status_code < 300

        # 包装为标准格式
        wrapped = {
            "code": response.status_code,
            "message": "success" if is_success else "error",
            "data": original_data,
            "request_id": request_id,
            "duration_ms": duration_ms,
            "timestamp": time.time(),
        }

        wrapped_body = json.dumps(wrapped, ensure_ascii=False, default=str)
        return Response(
            content=wrapped_body,
            status_code=response.status_code,
            headers={
                **dict(response.headers),
                "Content-Length": str(len(wrapped_body.encode())),
            },
            media_type="application/json",
        )
