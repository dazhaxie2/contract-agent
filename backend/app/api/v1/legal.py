"""Legal source sync endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.request_context import RequestContext, resolve_request_context
from app.schemas.legal import LegalSyncRequest, LegalSyncResponse
from app.services.legal_sync_service import legal_sync_service

router = APIRouter()


def get_request_context(request: Request) -> RequestContext:
    return resolve_request_context(request)


@router.post("/sync", response_model=LegalSyncResponse)
async def sync_legal_sources(
    req: LegalSyncRequest,
    ctx: RequestContext = Depends(get_request_context),
):
    tenant_id = req.tenant_id or ctx.tenant_id
    if tenant_id != ctx.tenant_id:
        raise HTTPException(status_code=403, detail="tenant mismatch")
    result = await legal_sync_service.run_sync_once(tenant_id=tenant_id, limit=req.limit)
    return LegalSyncResponse(**result.to_dict())

