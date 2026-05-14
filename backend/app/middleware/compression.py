"""
中间件 #11: 响应压缩中间件
支持Gzip/Brotli双压缩，根据Accept-Encoding自动选择
"""

import gzip
import io
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse

try:
    import brotli
    HAS_BROTLI = True
except ImportError:
    HAS_BROTLI = False


def _safe_headers(headers) -> dict:
    copied = dict(headers)
    copied.pop("content-length", None)
    copied.pop("Content-Length", None)
    return copied


class CompressionMiddleware(BaseHTTPMiddleware):
    """Gzip + Brotli 双压缩"""

    MIN_SIZE = 1024  # 最小压缩阈值 1KB
    COMPRESSIBLE_TYPES = {
        "application/json", "text/html", "text/plain", "text/css",
        "application/javascript", "text/javascript", "application/xml",
        "text/xml", "application/xhtml+xml",
    }

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        accept_encoding = request.headers.get("Accept-Encoding", "")
        response = await call_next(request)

        # 检查是否需要压缩
        content_type = response.headers.get("Content-Type", "").split(";")[0]
        if content_type not in self.COMPRESSIBLE_TYPES:
            return response

        # 已压缩的跳过
        if "Content-Encoding" in response.headers:
            return response

        # 读取响应体
        body = b""
        async for chunk in response.body_iterator:
            if isinstance(chunk, str):
                chunk = chunk.encode()
            body += chunk

        if len(body) < self.MIN_SIZE:
            return Response(
                content=body,
                status_code=response.status_code,
                headers=_safe_headers(response.headers),
                media_type=response.media_type,
            )

        # Brotli优先
        if HAS_BROTLI and "br" in accept_encoding:
            compressed = brotli.compress(body, quality=4)
            return Response(
                content=compressed,
                status_code=response.status_code,
                headers={**_safe_headers(response.headers), "Content-Encoding": "br", "Content-Length": str(len(compressed))},
                media_type=response.media_type,
            )

        # Gzip
        if "gzip" in accept_encoding:
            buf = io.BytesIO()
            with gzip.GzipFile(fileobj=buf, mode="wb", compresslevel=6) as f:
                f.write(body)
            compressed = buf.getvalue()
            return Response(
                content=compressed,
                status_code=response.status_code,
                headers={
                    **_safe_headers(response.headers),
                    "Content-Encoding": "gzip",
                    "Content-Length": str(len(compressed)),
                },
                media_type=response.media_type,
            )

        return Response(
            content=body,
            status_code=response.status_code,
            headers=_safe_headers(response.headers),
            media_type=response.media_type,
        )
