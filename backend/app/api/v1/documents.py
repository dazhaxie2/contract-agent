"""Document APIs with async ingestion job support."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_read_db, get_write_db
from app.core.request_context import RequestContext, resolve_request_context
from app.models.document import Document, DocumentChunk
from app.models.ingestion import IngestionJob, IngestionStageEvent
from app.services.ingestion_orchestrator import ingestion_orchestrator
from app.services.ingestion_service import ingestion_service

router = APIRouter()


def get_request_context(request: Request) -> RequestContext:
    return resolve_request_context(request)


def _parse_uuid(value: str, field_name: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"invalid {field_name}") from exc


def _serialize_document(doc: Document) -> dict:
    return {
        "id": str(doc.id),
        "tenant_id": doc.tenant_id,
        "title": doc.title,
        "doc_type": doc.doc_type,
        "file_name": doc.file_name,
        "file_path": doc.file_path,
        "file_size": doc.file_size,
        "file_hash": doc.file_hash,
        "mime_type": doc.mime_type,
        "issuing_authority": doc.issuing_authority,
        "effective_date": doc.effective_date,
        "expiry_date": doc.expiry_date,
        "applicable_industry": doc.applicable_industry or [],
        "applicable_region": doc.applicable_region or [],
        "version": doc.version,
        "keywords": doc.keywords or [],
        "metadata": doc.metadata_extra or {},
        "status": doc.status,
        "is_effective": doc.is_effective,
        "chunk_count": doc.chunk_count,
        "process_error": doc.process_error,
        "uploaded_by": str(doc.uploaded_by) if doc.uploaded_by else None,
        "created_at": doc.created_at,
        "updated_at": doc.updated_at,
    }


def _serialize_chunk(chunk: DocumentChunk) -> dict:
    text = chunk.content or ""
    return {
        "id": str(chunk.id),
        "doc_id": str(chunk.doc_id),
        "tenant_id": chunk.tenant_id,
        "content": text[:200] + "..." if len(text) > 200 else text,
        "summary": chunk.summary,
        "chunk_type": chunk.chunk_type,
        "hierarchy_path": chunk.hierarchy_path,
        "hierarchy_level": chunk.hierarchy_level,
        "chunk_index": chunk.chunk_index,
        "token_count": chunk.token_count,
        "parent_chunk_id": str(chunk.parent_chunk_id) if chunk.parent_chunk_id else None,
        "legal_priority": chunk.legal_priority,
        "entity_tags": chunk.entity_tags or [],
        "metadata": chunk.metadata_extra or {},
        "vector_status": chunk.vector_status,
        "graph_status": chunk.graph_status,
        "created_at": chunk.created_at,
    }


def _serialize_job(job: IngestionJob) -> dict:
    result = dict(job.result or {})
    retries = list(result.get("retries") or [])
    stages = dict(result.get("stages") or {})
    return {
        "job_id": str(job.id),
        "tenant_id": job.tenant_id,
        "status": job.status,
        "stage": job.stage,
        "file_name": job.file_name,
        "doc_id": str(job.doc_id) if job.doc_id else None,
        "doc_type": job.doc_type,
        "title": job.title,
        "attempt_count": job.attempt_count,
        "error_message": job.error_message,
        "result": result,
        "stage_details": stages,
        "retry_count": len(retries),
        "dead_letter": bool(result.get("dead_letter", False)),
        "created_at": job.created_at,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "updated_at": job.updated_at,
    }


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    doc_type: str = Form(default="auto"),
    title: str = Form(default=""),
    sync: bool = Form(default=False),
    db: AsyncSession = Depends(get_write_db),
    ctx: RequestContext = Depends(get_request_context),
):
    """Upload one file and enqueue ingestion job."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="file name is required")
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="file is empty")

    job = await ingestion_service.create_job(
        db=db,
        tenant_id=ctx.tenant_id,
        user_id=ctx.user_uuid,
        file_name=file.filename,
        doc_type=doc_type,
        title=title,
        payload={
            "content_type": file.content_type or "application/octet-stream",
            "source_type": "upload",
        },
    )
    await db.flush()
    await db.commit()

    if sync:
        await ingestion_service.run_job_sync(
            job_id=job.id,
            tenant_id=ctx.tenant_id,
            user_id=ctx.user_uuid,
            file_name=file.filename,
            content_type=file.content_type or "application/octet-stream",
            raw_bytes=raw,
            doc_type=doc_type,
            title=title,
            source_type="upload",
            source_url=None,
        )
        fresh = await db.scalar(
            select(IngestionJob)
            .where(IngestionJob.id == job.id, IngestionJob.tenant_id == ctx.tenant_id)
            .execution_options(populate_existing=True)
        )
        return _serialize_job(fresh or job)

    await ingestion_orchestrator.enqueue_document_job(
        job_id=job.id,
        tenant_id=ctx.tenant_id,
        user_id=ctx.user_uuid,
        file_name=file.filename,
        content_type=file.content_type,
        raw_bytes=raw,
        doc_type=doc_type,
        title=title,
        source_type="upload",
        source_url=None,
    )
    return _serialize_job(job)


@router.get("/jobs/{job_id}")
async def get_ingestion_job(
    job_id: str,
    db: AsyncSession = Depends(get_read_db),
    ctx: RequestContext = Depends(get_request_context),
):
    job_uuid = _parse_uuid(job_id, "job_id")
    row = await ingestion_service.get_job(db, job_uuid, ctx.tenant_id)
    if not row:
        raise HTTPException(status_code=404, detail="job not found")
    payload = _serialize_job(row)
    stage_events = (
        await db.scalars(
            select(IngestionStageEvent)
            .where(IngestionStageEvent.job_id == job_uuid, IngestionStageEvent.tenant_id == ctx.tenant_id)
            .order_by(IngestionStageEvent.created_at.asc())
        )
    ).all()
    payload["events"] = [
        {
            "stage": event.stage,
            "status": event.status,
            "detail": event.detail or {},
            "created_at": event.created_at,
        }
        for event in stage_events
    ]
    return payload


@router.get("")
async def list_documents(
    doc_type: str = Query(default=""),
    status: str = Query(default=""),
    search: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_read_db),
    ctx: RequestContext = Depends(get_request_context),
):
    query = select(Document).where(Document.tenant_id == ctx.tenant_id)
    if doc_type:
        query = query.where(Document.doc_type == doc_type)
    if status:
        query = query.where(Document.status == status)
    if search:
        query = query.where(Document.title.ilike(f"%{search}%"))

    total_stmt = select(func.count()).select_from(query.subquery())
    total = int((await db.scalar(total_stmt)) or 0)
    rows = (
        await db.scalars(
            query.order_by(Document.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        )
    ).all()

    return {
        "items": [_serialize_document(row) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.get("/{doc_id}")
async def get_document(
    doc_id: str,
    db: AsyncSession = Depends(get_read_db),
    ctx: RequestContext = Depends(get_request_context),
):
    doc_uuid = _parse_uuid(doc_id, "doc_id")
    row = await db.scalar(select(Document).where(Document.id == doc_uuid, Document.tenant_id == ctx.tenant_id))
    if not row:
        raise HTTPException(status_code=404, detail="document not found")
    return _serialize_document(row)


@router.get("/{doc_id}/chunks")
async def get_document_chunks(
    doc_id: str,
    db: AsyncSession = Depends(get_read_db),
    ctx: RequestContext = Depends(get_request_context),
):
    doc_uuid = _parse_uuid(doc_id, "doc_id")
    doc = await db.scalar(select(Document).where(Document.id == doc_uuid, Document.tenant_id == ctx.tenant_id))
    if not doc:
        raise HTTPException(status_code=404, detail="document not found")

    rows = (
        await db.scalars(
            select(DocumentChunk)
            .where(DocumentChunk.doc_id == doc_uuid, DocumentChunk.tenant_id == ctx.tenant_id)
            .order_by(DocumentChunk.chunk_index.asc())
        )
    ).all()
    return [_serialize_chunk(row) for row in rows]


@router.delete("/{doc_id}")
async def delete_document(
    doc_id: str,
    db: AsyncSession = Depends(get_write_db),
    ctx: RequestContext = Depends(get_request_context),
):
    doc_uuid = _parse_uuid(doc_id, "doc_id")
    row = await db.scalar(select(Document).where(Document.id == doc_uuid, Document.tenant_id == ctx.tenant_id))
    if not row:
        raise HTTPException(status_code=404, detail="document not found")

    await db.execute(
        delete(DocumentChunk).where(DocumentChunk.doc_id == doc_uuid, DocumentChunk.tenant_id == ctx.tenant_id)
    )
    await db.delete(row)
    await db.flush()
    return {"message": "deleted"}
