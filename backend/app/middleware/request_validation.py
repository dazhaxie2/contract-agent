"""
中间件 #20: 请求体预校验中间件
Content-Type检查、请求体大小限制、恶意输入检测
"""

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from loguru import logger


class RequestValidationMiddleware(BaseHTTPMiddleware):
    """请求预校验"""

    MAX_BODY_SIZE = 100 * 1024 * 1024  # 100MB (文档上传)
    MAX_JSON_BODY_SIZE = 10 * 1024 * 1024  # 10MB (JSON请求)
    ALLOWED_CONTENT_TYPES = {
        "application/json",
        "multipart/form-data",
        "application/x-www-form-urlencoded",
        "application/octet-stream",
    }

    # SQL注入/XSS检测模式
    DANGEROUS_PATTERNS = [
        "DROP TABLE", "DELETE FROM", "INSERT INTO", "UPDATE SET",
        "UNION SELECT", "OR 1=1", "' OR '", "'; --",
        "<script>", "javascript:", "onerror=", "onload=",
    ]

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # GET/OPTIONS/HEAD 跳过
        if request.method in ("GET", "OPTIONS", "HEAD"):
            return await call_next(request)

        # Content-Type检查
        content_type = request.headers.get("Content-Type", "").split(";")[0].strip()
        if content_type and content_type not in self.ALLOWED_CONTENT_TYPES:
            return JSONResponse(
                status_code=415,
                content={
                    "code": 415,
                    "message": f"不支持的Content-Type: {content_type}",
                    "detail": "UNSUPPORTED_MEDIA_TYPE",
                },
            )

        # 请求体大小检查
        content_length = request.headers.get("Content-Length")
        if content_length:
            size = int(content_length)
            max_size = self.MAX_BODY_SIZE if "multipart" in content_type else self.MAX_JSON_BODY_SIZE
            if size > max_size:
                return JSONResponse(
                    status_code=413,
                    content={
                        "code": 413,
                        "message": f"请求体过大: {size} bytes，最大允许 {max_size} bytes",
                        "detail": "PAYLOAD_TOO_LARGE",
                    },
                )

        # JSON请求的恶意输入检测
        if content_type == "application/json":
            try:
                body = await request.body()
                body_str = body.decode("utf-8", errors="ignore").upper()
                for pattern in self.DANGEROUS_PATTERNS:
                    if pattern.upper() in body_str:
                        return JSONResponse(
                            status_code=400,
                            content={
                                "code": 400,
                                "message": "检测到潜在恶意输入",
                                "detail": "MALICIOUS_INPUT_DETECTED",
                            },
                        )
            except Exception as exc:
                logger.debug(f"request body validation skipped path={request.url.path}: {exc}")

        return await call_next(request)
