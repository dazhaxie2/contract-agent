"""
中间件 #16: 敏感数据脱敏中间件
自动识别并脱敏身份证、手机号、银行卡、邮箱等PII信息
"""

import re
import json
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


class DataMaskingMiddleware(BaseHTTPMiddleware):
    """敏感信息自动脱敏"""

    # 正则模式 -> 脱敏函数
    PATTERNS = {
        # 身份证号 (18位)
        "id_card": (
            re.compile(r'\b(\d{6})\d{8}(\d{4})\b'),
            lambda m: f"{m.group(1)}********{m.group(2)}"
        ),
        # 手机号
        "phone": (
            re.compile(r'\b(1[3-9]\d)\d{4}(\d{4})\b'),
            lambda m: f"{m.group(1)}****{m.group(2)}"
        ),
        # 银行卡号 (16-19位)
        "bank_card": (
            re.compile(r'\b(\d{4})\d{8,12}(\d{4})\b'),
            lambda m: f"{m.group(1)}{'*' * 8}{m.group(2)}"
        ),
        # 邮箱
        "email": (
            re.compile(r'\b([a-zA-Z0-9._%+-]{1,3})[a-zA-Z0-9._%+-]*@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b'),
            lambda m: f"{m.group(1)}***@{m.group(2)}"
        ),
        # 姓名 (简单中文姓名)
        "name_cn": (
            re.compile(r'(?<="name"|"姓名"|"甲方"|"乙方")\s*:\s*"([\u4e00-\u9fa5])[\u4e00-\u9fa5]{1,3}"'),
            lambda m: f': "{m.group(1)}**"'
        ),
    }

    # 需要脱敏的响应路径
    MASKING_PATHS = {"/api/v1/documents", "/api/v1/agents", "/api/v1/retrieval"}

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)

        # 只对特定路径的JSON响应做脱敏
        content_type = response.headers.get("Content-Type", "")
        if "application/json" not in content_type:
            return response

        should_mask = any(request.url.path.startswith(p) for p in self.MASKING_PATHS)
        if not should_mask:
            return response

        # 读取响应体
        body = b""
        async for chunk in response.body_iterator:
            if isinstance(chunk, str):
                chunk = chunk.encode()
            body += chunk

        try:
            text = body.decode("utf-8")
            masked_text = self._mask_sensitive_data(text)
            masked_body = masked_text.encode("utf-8")
        except (UnicodeDecodeError, json.JSONDecodeError):
            masked_body = body

        return Response(
            content=masked_body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )

    def _mask_sensitive_data(self, text: str) -> str:
        for name, (pattern, replacer) in self.PATTERNS.items():
            text = pattern.sub(replacer, text)
        return text
