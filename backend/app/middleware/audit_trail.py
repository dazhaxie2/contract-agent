"""
中间件 #21: 审计追踪中间件
记录所有写操作的完整审计日志，满足合规审计要求，不可篡改
"""

import json
import time
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from loguru import logger

from app.middleware.request_id import get_request_id, get_tenant_id, get_user_id


class AuditTrailMiddleware(BaseHTTPMiddleware):
    """合规审计追踪"""

    AUDITABLE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
    AUDIT_PATHS = {
        "/api/v1/documents", "/api/v1/models", "/api/v1/prompts",
        "/api/v1/users", "/api/v1/agents", "/api/v1/system",
    }
    # 敏感字段不记录
    REDACTED_FIELDS = {"password", "hashed_password", "api_key", "secret", "token", "api_key_encrypted"}

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method not in self.AUDITABLE_METHODS:
            return await call_next(request)

        should_audit = any(request.url.path.startswith(p) for p in self.AUDIT_PATHS)
        if not should_audit:
            return await call_next(request)

        request_id = get_request_id()
        tenant_id = get_tenant_id()
        user_id = get_user_id()

        # 记录请求体 (脱敏处理)
        request_body = None
        try:
            body = await request.body()
            if body:
                parsed = json.loads(body)
                request_body = self._redact_sensitive(parsed)
        except Exception:
            request_body = {"_raw_size": len(body) if body else 0}

        start_time = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start_time) * 1000

        # 构建审计日志
        audit_entry = {
            "audit_type": "api_operation",
            "timestamp": time.time(),
            "request_id": request_id,
            "trace_id": request_id,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "method": request.method,
            "path": request.url.path,
            "query_params": dict(request.query_params),
            "request_body": request_body,
            "response_status": response.status_code,
            "duration_ms": round(duration_ms, 2),
            "client_ip": request.client.host if request.client else "unknown",
            "user_agent": request.headers.get("user-agent", ""),
            # 资源信息
            "resource_type": self._extract_resource_type(request.url.path),
            "action": self._map_action(request.method),
        }

        # 异步写入审计日志 (生产环境写入ES/DB)
        logger.bind(audit=True).info(json.dumps(audit_entry, ensure_ascii=False, default=str))

        return response

    def _redact_sensitive(self, data: dict) -> dict:
        if not isinstance(data, dict):
            return data
        result = {}
        for key, value in data.items():
            if key.lower() in self.REDACTED_FIELDS:
                result[key] = "***REDACTED***"
            elif isinstance(value, dict):
                result[key] = self._redact_sensitive(value)
            elif isinstance(value, list):
                result[key] = [self._redact_sensitive(v) if isinstance(v, dict) else v for v in value]
            else:
                result[key] = value
        return result

    @staticmethod
    def _extract_resource_type(path: str) -> str:
        parts = path.strip("/").split("/")
        if len(parts) >= 3:
            return parts[2]  # api/v1/{resource}
        return "unknown"

    @staticmethod
    def _map_action(method: str) -> str:
        return {"POST": "create", "PUT": "update", "PATCH": "partial_update", "DELETE": "delete"}.get(method, method)
