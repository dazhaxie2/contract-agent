"""Audit trail middleware with persistent hash-chain storage."""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from datetime import datetime, timezone

from loguru import logger
from sqlalchemy import select
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.database import WriteSessionLocal
from app.middleware.request_id import get_request_id, get_tenant_id, get_user_id
from app.models.audit import AuditLog


def _parse_uuid(value: str | None) -> uuid.UUID | None:
    if not value:
        return None
    try:
        return uuid.UUID(value)
    except (ValueError, TypeError):
        return None


class AuditTrailMiddleware(BaseHTTPMiddleware):
    AUDITABLE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
    AUDIT_PATHS = {
        "/api/v1/documents",
        "/api/v1/models",
        "/api/v1/prompts",
        "/api/v1/users",
        "/api/v1/agents",
        "/api/v1/system",
        "/api/v1/sessions",
        "/api/v1/memory",
        "/api/v1/retrieval",
        "/api/v1/citations",
    }
    REDACTED_FIELDS = {"password", "hashed_password", "api_key", "secret", "token", "api_key_encrypted"}

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method not in self.AUDITABLE_METHODS:
            return await call_next(request)
        if not any(request.url.path.startswith(path) for path in self.AUDIT_PATHS):
            return await call_next(request)

        request_id = get_request_id()
        tenant_id = get_tenant_id() or getattr(request.state, "tenant_id", "default")
        user_id = get_user_id() or getattr(request.state, "user_id", "")
        started = time.perf_counter()
        request_body = None
        body = await request.body()
        if body:
            try:
                request_body = self._redact_sensitive(json.loads(body))
            except Exception:
                request_body = {"_raw_size": len(body)}

        response = await call_next(request)
        duration_ms = (time.perf_counter() - started) * 1000

        entry = {
            "request_id": request_id,
            "trace_id": request.headers.get("X-Trace-ID", request_id),
            "tenant_id": tenant_id or "default",
            "user_id": user_id,
            "method": request.method,
            "path": request.url.path,
            "query_params": dict(request.query_params),
            "request_body": request_body,
            "response_status": response.status_code,
            "duration_ms": round(duration_ms, 2),
            "client_ip": request.client.host if request.client else "unknown",
            "user_agent": request.headers.get("user-agent", ""),
            "resource_type": self._extract_resource_type(request.url.path),
            "action": self._map_action(request.method),
        }

        await self._persist(entry)
        logger.bind(audit=True).info(json.dumps(entry, ensure_ascii=False, default=str))
        return response

    async def _persist(self, entry: dict) -> None:
        tenant_id = str(entry.get("tenant_id") or "default")
        user_uuid = _parse_uuid(entry.get("user_id"))
        record_payload = {
            "trace_id": entry.get("trace_id"),
            "tenant_id": tenant_id,
            "user_id": str(user_uuid) if user_uuid else None,
            "action": entry.get("action"),
            "resource_type": entry.get("resource_type"),
            "resource_id": self._extract_resource_id(entry.get("path", "")),
            "request_method": entry.get("method"),
            "request_path": entry.get("path"),
            "request_body": entry.get("request_body"),
            "response_status": entry.get("response_status"),
            "ip_address": entry.get("client_ip"),
            "user_agent": entry.get("user_agent"),
            "description": f"duration_ms={entry.get('duration_ms')}",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        payload_text = json.dumps(record_payload, ensure_ascii=False, sort_keys=True, default=str)

        try:
            async with WriteSessionLocal() as db:
                previous = await db.scalar(
                    select(AuditLog)
                    .where(AuditLog.tenant_id == tenant_id)
                    .order_by(AuditLog.created_at.desc())
                    .limit(1)
                )
                prev_hash = previous.record_hash if previous else ""
                chain_value = f"{prev_hash}|{payload_text}"
                record_hash = hashlib.sha256(chain_value.encode("utf-8")).hexdigest()

                row = AuditLog(
                    id=uuid.uuid4(),
                    trace_id=str(entry.get("trace_id") or ""),
                    user_id=user_uuid,
                    tenant_id=tenant_id,
                    action=str(entry.get("action") or "unknown"),
                    resource_type=str(entry.get("resource_type") or "unknown"),
                    resource_id=self._extract_resource_id(str(entry.get("path") or "")),
                    request_method=str(entry.get("method") or ""),
                    request_path=str(entry.get("path") or ""),
                    request_body=entry.get("request_body"),
                    response_status=int(entry.get("response_status") or 0),
                    old_value=None,
                    new_value=None,
                    previous_hash=prev_hash,
                    record_hash=record_hash,
                    ip_address=str(entry.get("client_ip") or ""),
                    user_agent=str(entry.get("user_agent") or ""),
                    description=f"duration_ms={entry.get('duration_ms')}",
                    created_at=datetime.now(timezone.utc),
                )
                db.add(row)
                await db.commit()
        except Exception as exc:
            logger.warning(f"Audit persist failed: {exc}")

    def _redact_sensitive(self, data):
        if isinstance(data, dict):
            redacted = {}
            for key, value in data.items():
                if key.lower() in self.REDACTED_FIELDS:
                    redacted[key] = "***REDACTED***"
                else:
                    redacted[key] = self._redact_sensitive(value)
            return redacted
        if isinstance(data, list):
            return [self._redact_sensitive(item) for item in data]
        return data

    @staticmethod
    def _extract_resource_type(path: str) -> str:
        parts = path.strip("/").split("/")
        if len(parts) >= 3:
            return parts[2]
        return "unknown"

    @staticmethod
    def _extract_resource_id(path: str) -> str | None:
        parts = path.strip("/").split("/")
        if len(parts) >= 4:
            return parts[3]
        return None

    @staticmethod
    def _map_action(method: str) -> str:
        return {"POST": "create", "PUT": "update", "PATCH": "partial_update", "DELETE": "delete"}.get(method, method)
