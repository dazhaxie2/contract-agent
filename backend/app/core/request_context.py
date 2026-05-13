"""Request-scoped tenant/user context helpers."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi import Request

from app.middleware.request_id import get_tenant_id as get_tenant_id_ctx
from app.middleware.request_id import get_user_id as get_user_id_ctx

DEFAULT_TENANT_ID = "default"
DEFAULT_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


@dataclass(frozen=True)
class RequestContext:
    tenant_id: str
    user_id: str
    user_uuid: uuid.UUID


def _coalesce(*values: object) -> str:
    for value in values:
        if isinstance(value, str):
            stripped = value.strip()
            if stripped:
                return stripped
    return ""


def _normalize_user_uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except (TypeError, ValueError):
        return DEFAULT_USER_ID


def resolve_request_context(request: Request) -> RequestContext:
    tenant_id = _coalesce(
        getattr(request.state, "tenant_id", None),
        get_tenant_id_ctx(),
        request.headers.get("X-Tenant-ID"),
        DEFAULT_TENANT_ID,
    )
    user_id = _coalesce(
        getattr(request.state, "user_id", None),
        get_user_id_ctx(),
        request.headers.get("X-User-ID"),
        str(DEFAULT_USER_ID),
    )
    return RequestContext(
        tenant_id=tenant_id,
        user_id=user_id,
        user_uuid=_normalize_user_uuid(user_id),
    )

