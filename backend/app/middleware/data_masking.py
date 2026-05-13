"""Response-layer sensitive data masking middleware."""

from __future__ import annotations

import re

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


class DataMaskingMiddleware(BaseHTTPMiddleware):
    """Mask common PII patterns in JSON responses for selected endpoints."""

    PATTERNS = {
        "id_card": (
            re.compile(r"\b(\d{6})\d{8}(\d{4})\b"),
            lambda m: f"{m.group(1)}********{m.group(2)}",
        ),
        "phone": (
            re.compile(r"\b(1[3-9]\d)\d{4}(\d{4})\b"),
            lambda m: f"{m.group(1)}****{m.group(2)}",
        ),
        "bank_card": (
            re.compile(r"\b(\d{4})\d{8,12}(\d{4})\b"),
            lambda m: f"{m.group(1)}********{m.group(2)}",
        ),
        "email": (
            re.compile(r"\b([a-zA-Z0-9._%+-]{1,3})[a-zA-Z0-9._%+-]*@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b"),
            lambda m: f"{m.group(1)}***@{m.group(2)}",
        ),
        # Matches JSON fields like "name": "张三"
        "name_cn": (
            re.compile(r'("(?:name|姓名|甲方|乙方)"\s*:\s*")([\u4e00-\u9fa5])[\u4e00-\u9fa5]{1,3}(")'),
            lambda m: f"{m.group(1)}{m.group(2)}**{m.group(3)}",
        ),
    }

    MASKING_PATHS = {"/api/v1/documents", "/api/v1/agents", "/api/v1/retrieval"}

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)

        content_type = response.headers.get("Content-Type", "")
        if "application/json" not in content_type:
            return response

        if not any(request.url.path.startswith(path) for path in self.MASKING_PATHS):
            return response

        body = b""
        async for chunk in response.body_iterator:
            if isinstance(chunk, str):
                chunk = chunk.encode("utf-8")
            body += chunk

        try:
            text = body.decode("utf-8")
            masked_text = self._mask_sensitive_data(text)
            masked_body = masked_text.encode("utf-8")
        except UnicodeDecodeError:
            masked_body = body

        return Response(
            content=masked_body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )

    def _mask_sensitive_data(self, text: str) -> str:
        masked = text
        for _name, (pattern, replacer) in self.PATTERNS.items():
            masked = pattern.sub(replacer, masked)
        return masked
