"""Asynchronous document ingestion service with multi-store indexing."""

from __future__ import annotations

import asyncio
import io
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from loguru import logger
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import WriteSessionLocal
from app.core.tracing_utils import start_span
from app.models.document import Document, DocumentChunk
from app.models.ingestion import IngestionJob, IngestionStageEvent
from app.rag.chunker import document_chunker
from app.rag.document_processor import document_processor
from app.services.connectors import kafka_connector, milvus_connector, minio_connector, nebula_connector
from app.services.connectors.nebula_connector import extract_entities
from app.services.llm_service import llm_service


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_datetime(value: object) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def _normalize_search_text(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text.lower()).strip()
    return cleaned[:12000]


class IngestionService:
    async def create_job(
        self,
        db: AsyncSession,
        *,
        tenant_id: str,
        user_id: uuid.UUID | None,
        file_name: str,
        doc_type: str,
        title: str,
        payload: dict | None = None,
    ) -> IngestionJob:
        now = _utcnow()
        row = IngestionJob(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            doc_id=None,
            file_name=file_name,
            file_hash=None,
            doc_type=doc_type,
            title=title or None,
            status="queued",
            stage="uploaded",
            attempt_count=0,
            payload=payload or {},
            result={},
            error_message=None,
            created_by=user_id,
            created_at=now,
            started_at=None,
            completed_at=None,
            updated_at=now,
        )
        db.add(row)
        await db.flush()
        return row

    async def get_job(self, db: AsyncSession, job_id: uuid.UUID, tenant_id: str) -> IngestionJob | None:
        return await db.scalar(
            select(IngestionJob).where(IngestionJob.id == job_id, IngestionJob.tenant_id == tenant_id)
        )

    def launch_job(
        self,
        *,
        job_id: uuid.UUID,
        tenant_id: str,
        user_id: uuid.UUID | None,
        file_name: str,
        content_type: str | None,
        raw_bytes: bytes,
        doc_type: str,
        title: str,
        source_type: str = "upload",
        source_url: str | None = None,
    ) -> None:
        asyncio.create_task(
            self.run_job_sync(
                job_id=job_id,
                tenant_id=tenant_id,
                user_id=user_id,
                file_name=file_name,
                content_type=content_type or "application/octet-stream",
                raw_bytes=raw_bytes,
                doc_type=doc_type,
                title=title,
                source_type=source_type,
                source_url=source_url,
            )
        )

    async def run_job_sync(
        self,
        *,
        job_id: uuid.UUID,
        tenant_id: str,
        user_id: uuid.UUID | None,
        file_name: str,
        content_type: str | None,
        raw_bytes: bytes,
        doc_type: str,
        title: str,
        source_type: str = "upload",
        source_url: str | None = None,
    ) -> None:
        await self._run_job(
            job_id=job_id,
            tenant_id=tenant_id,
            user_id=user_id,
            file_name=file_name,
            content_type=content_type or "application/octet-stream",
            raw_bytes=raw_bytes,
            doc_type=doc_type,
            title=title,
            source_type=source_type,
            source_url=source_url,
        )

    async def _run_job(
        self,
        *,
        job_id: uuid.UUID,
        tenant_id: str,
        user_id: uuid.UUID | None,
        file_name: str,
        content_type: str,
        raw_bytes: bytes,
        doc_type: str,
        title: str,
        source_type: str,
        source_url: str | None,
    ) -> None:
        max_retries = settings.ingestion_runtime.max_retries

        for attempt in range(1, max_retries + 1):
            try:
                await self._mark_processing(job_id=job_id, tenant_id=tenant_id, attempt=attempt)
                await self._process_once(
                    job_id=job_id,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    file_name=file_name,
                    content_type=content_type,
                    raw_bytes=raw_bytes,
                    doc_type=doc_type,
                    title=title,
                    source_type=source_type,
                    source_url=source_url,
                )
                return
            except Exception as exc:
                logger.warning(f"Ingestion attempt failed job={job_id} attempt={attempt}: {exc}")
                if attempt < max_retries:
                    await self._mark_retrying(job_id=job_id, tenant_id=tenant_id, attempt=attempt, error=str(exc))
                    continue
                await self._mark_failed(job_id=job_id, tenant_id=tenant_id, error=str(exc), dead_letter=True)
                await self._send_dead_letter(
                    {
                        "event_type": "ingestion.dead_letter",
                        "job_id": str(job_id),
                        "tenant_id": tenant_id,
                        "error": str(exc),
                        "attempts": attempt,
                    }
                )

    async def _process_once(
        self,
        *,
        job_id: uuid.UUID,
        tenant_id: str,
        user_id: uuid.UUID | None,
        file_name: str,
        content_type: str,
        raw_bytes: bytes,
        doc_type: str,
        title: str,
        source_type: str,
        source_url: str | None,
    ) -> None:
        object_key = f"{tenant_id}/{job_id}/{file_name}"
        with start_span("ingestion.archive", {"tenant.id": tenant_id, "job.id": str(job_id)}):
            minio_path = await minio_connector.upload_bytes(object_key, raw_bytes, content_type)
        await self._mark_stage(
            job_id=job_id,
            tenant_id=tenant_id,
            stage="uploaded",
            extra={"object_path": minio_path or "", "source_type": source_type, "source_url": source_url or ""},
        )

        with start_span("ingestion.preprocess", {"tenant.id": tenant_id, "job.id": str(job_id)}):
            processed = await document_processor.process(
                file=io.BytesIO(raw_bytes),
                filename=file_name,
                tenant_id=tenant_id,
            )
        await self._mark_stage(
            job_id=job_id,
            tenant_id=tenant_id,
            stage="preprocess",
            extra={"file_hash": processed["file_hash"], "file_size": processed["file_size"]},
        )

        actual_type = doc_type if doc_type != "auto" else processed["metadata"].get("doc_type", "guide")
        with start_span("ingestion.chunk", {"tenant.id": tenant_id, "job.id": str(job_id), "doc.type": actual_type}):
            chunks = document_chunker.chunk(processed["cleaned_text"], doc_type=actual_type)
        doc_id, chunk_rows = await self._upsert_document_and_chunks(
            job_id=job_id,
            tenant_id=tenant_id,
            user_id=user_id,
            file_name=file_name,
            content_type=content_type,
            title=title,
            actual_type=actual_type,
            processed=processed,
            chunks=chunks,
            object_path=minio_path,
            source_type=source_type,
            source_url=source_url,
        )

        with start_span("ingestion.vectorize", {"tenant.id": tenant_id, "job.id": str(job_id)}):
            await self._vectorize_chunks(
                job_id=job_id,
                tenant_id=tenant_id,
                doc_id=doc_id,
                chunk_rows=chunk_rows,
            )
        with start_span("ingestion.graph", {"tenant.id": tenant_id, "job.id": str(job_id)}):
            await self._graph_index_chunks(
                job_id=job_id,
                tenant_id=tenant_id,
                doc_id=doc_id,
                chunk_rows=chunk_rows,
                doc_type=actual_type,
            )
        await self._mark_completed(job_id=job_id, tenant_id=tenant_id, doc_id=doc_id, chunk_count=len(chunk_rows))

    async def _upsert_document_and_chunks(
        self,
        *,
        job_id: uuid.UUID,
        tenant_id: str,
        user_id: uuid.UUID | None,
        file_name: str,
        content_type: str,
        title: str,
        actual_type: str,
        processed: dict,
        chunks: list,
        object_path: str | None,
        source_type: str,
        source_url: str | None,
    ) -> tuple[uuid.UUID, list[DocumentChunk]]:
        now = _utcnow()
        metadata = processed.get("metadata", {})
        async with WriteSessionLocal() as db:
            job = await self.get_job(db, job_id, tenant_id)
            if not job:
                raise RuntimeError(f"ingestion job not found: {job_id}")

            doc_id = job.doc_id or uuid.uuid4()
            row = await db.scalar(select(Document).where(Document.id == doc_id, Document.tenant_id == tenant_id))
            extra = dict(metadata or {})
            extra["source_type"] = source_type
            if source_url:
                extra["source_url"] = source_url

            if row is None:
                row = Document(
                    id=doc_id,
                    tenant_id=tenant_id,
                    title=title or metadata.get("title", file_name),
                    doc_type=actual_type,
                    file_name=file_name,
                    file_path=object_path or f"uploads/{doc_id}/{file_name}",
                    file_size=processed["file_size"],
                    file_hash=processed["file_hash"],
                    mime_type=content_type,
                    issuing_authority=metadata.get("issuing_authority"),
                    effective_date=_parse_datetime(metadata.get("effective_date")),
                    expiry_date=_parse_datetime(metadata.get("expiry_date")),
                    applicable_industry=metadata.get("applicable_industry", []),
                    applicable_region=metadata.get("applicable_region", []),
                    version=metadata.get("version"),
                    keywords=metadata.get("keywords", []),
                    metadata_extra=extra,
                    status="processed",
                    is_effective=True,
                    chunk_count=len(chunks),
                    process_error=None,
                    uploaded_by=user_id,
                    created_at=now,
                    updated_at=now,
                )
                db.add(row)
            else:
                row.title = title or metadata.get("title", file_name)
                row.doc_type = actual_type
                row.file_name = file_name
                row.file_path = object_path or row.file_path
                row.file_size = processed["file_size"]
                row.file_hash = processed["file_hash"]
                row.mime_type = content_type
                row.issuing_authority = metadata.get("issuing_authority")
                row.effective_date = _parse_datetime(metadata.get("effective_date"))
                row.expiry_date = _parse_datetime(metadata.get("expiry_date"))
                row.applicable_industry = metadata.get("applicable_industry", [])
                row.applicable_region = metadata.get("applicable_region", [])
                row.version = metadata.get("version")
                row.keywords = metadata.get("keywords", [])
                row.metadata_extra = extra
                row.chunk_count = len(chunks)
                row.updated_at = now

            id_map: dict[str, uuid.UUID] = {}
            for idx, chunk in enumerate(chunks):
                id_map[str(chunk.id)] = uuid.uuid5(uuid.NAMESPACE_URL, f"{doc_id}:{idx}")

            new_chunk_ids = {item for item in id_map.values()}
            existing_rows = (
                await db.scalars(
                    select(DocumentChunk).where(DocumentChunk.doc_id == doc_id, DocumentChunk.tenant_id == tenant_id)
                )
            ).all()
            existing_by_id = {row.id: row for row in existing_rows}
            existing_ids = set(existing_by_id.keys())

            for idx, chunk in enumerate(chunks):
                chunk_id = id_map[str(chunk.id)]
                parent_chunk_id = id_map.get(str(chunk.parent_id)) if chunk.parent_id else None
                payload = {
                    "content": chunk.content,
                    "summary": chunk.summary or None,
                    "chunk_type": chunk.chunk_type,
                    "parent_chunk_id": parent_chunk_id,
                    "hierarchy_path": chunk.hierarchy_path or None,
                    "hierarchy_level": chunk.hierarchy_level,
                    "chunk_index": idx,
                    "token_count": chunk.token_count,
                    "legal_priority": 0,
                    "entity_tags": [],
                    "metadata_extra": {**(chunk.metadata or {}), "doc_type": actual_type},
                    "search_text": _normalize_search_text(chunk.content),
                }
                existing = existing_by_id.get(chunk_id)
                if existing is None:
                    db.add(
                        DocumentChunk(
                            id=chunk_id,
                            doc_id=doc_id,
                            tenant_id=tenant_id,
                            vector_status="pending",
                            graph_status="pending",
                            created_at=now,
                            **payload,
                        )
                    )
                else:
                    for key, value in payload.items():
                        setattr(existing, key, value)
                    existing.vector_status = "pending"
                    existing.graph_status = "pending"

            stale_ids = existing_ids - new_chunk_ids
            if stale_ids:
                await db.execute(
                    delete(DocumentChunk).where(
                        DocumentChunk.doc_id == doc_id,
                        DocumentChunk.tenant_id == tenant_id,
                        DocumentChunk.id.in_(list(stale_ids)),
                    )
                )

            job.doc_id = doc_id
            job.file_hash = processed["file_hash"]
            await db.commit()

            fresh_chunks = (
                await db.scalars(
                    select(DocumentChunk)
                    .where(DocumentChunk.doc_id == doc_id, DocumentChunk.tenant_id == tenant_id)
                    .order_by(DocumentChunk.chunk_index.asc())
                )
            ).all()

        await self._mark_stage(
            job_id=job_id,
            tenant_id=tenant_id,
            stage="chunked",
            extra={"doc_id": str(doc_id), "chunks_created": len(fresh_chunks)},
        )
        return doc_id, list(fresh_chunks)

    async def _vectorize_chunks(
        self,
        *,
        job_id: uuid.UUID,
        tenant_id: str,
        doc_id: uuid.UUID,
        chunk_rows: list[DocumentChunk],
    ) -> None:
        if not chunk_rows:
            await self._mark_stage(job_id=job_id, tenant_id=tenant_id, stage="vectorized", extra={"indexed": 0})
            return

        texts = [row.content for row in chunk_rows]
        vectors = await llm_service.embed(texts=texts)
        upsert_rows = []
        for row, emb in zip(chunk_rows, vectors):
            upsert_rows.append(
                {
                    "id": f"{tenant_id}:{row.id}",
                    "tenant_id": tenant_id,
                    "doc_id": str(doc_id),
                    "chunk_id": str(row.id),
                    "doc_type": row.metadata_extra.get("doc_type", ""),
                    "content": row.content[:8000],
                    "embedding": emb,
                }
            )
        ok = await milvus_connector.upsert_chunks(upsert_rows)
        if not ok and settings.ingestion_runtime.strict_connector:
            raise RuntimeError("milvus upsert failed")

        async with WriteSessionLocal() as db:
            rows = (
                await db.scalars(
                    select(DocumentChunk).where(
                        DocumentChunk.doc_id == doc_id,
                        DocumentChunk.tenant_id == tenant_id,
                    )
                )
            ).all()
            for row in rows:
                row.vector_status = "ready" if ok else "failed"
            await db.commit()

        await self._mark_stage(
            job_id=job_id,
            tenant_id=tenant_id,
            stage="vectorized",
            extra={"indexed": len(chunk_rows), "ok": ok},
        )

    async def _graph_index_chunks(
        self,
        *,
        job_id: uuid.UUID,
        tenant_id: str,
        doc_id: uuid.UUID,
        chunk_rows: list[DocumentChunk],
        doc_type: str,
    ) -> None:
        indexed = 0
        failed = 0
        for row in chunk_rows:
            entities = extract_entities(row.content)
            ok = await nebula_connector.upsert_chunk_entities(
                tenant_id=tenant_id,
                doc_id=str(doc_id),
                chunk_id=str(row.id),
                doc_type=doc_type,
                entities=entities,
            )
            if ok:
                indexed += 1
            else:
                failed += 1

        if failed > 0 and settings.ingestion_runtime.strict_connector:
            raise RuntimeError(f"nebula indexing failed chunks={failed}")

        async with WriteSessionLocal() as db:
            rows = (
                await db.scalars(
                    select(DocumentChunk).where(
                        DocumentChunk.doc_id == doc_id,
                        DocumentChunk.tenant_id == tenant_id,
                    )
                )
            ).all()
            for row in rows:
                row.graph_status = "ready" if failed == 0 else ("failed" if extract_entities(row.content) else "ready")
            await db.commit()

        await self._mark_stage(
            job_id=job_id,
            tenant_id=tenant_id,
            stage="graphed",
            extra={"indexed": indexed, "failed": failed},
        )

    async def _mark_processing(self, *, job_id: uuid.UUID, tenant_id: str, attempt: int) -> None:
        async with WriteSessionLocal() as db:
            job = await self.get_job(db, job_id, tenant_id)
            if not job:
                raise RuntimeError(f"job not found: {job_id}")
            if job.status == "completed":
                return
            now = _utcnow()
            job.status = "processing"
            job.stage = "uploaded"
            job.attempt_count = max(int(job.attempt_count or 0), attempt)
            if job.started_at is None:
                job.started_at = now
            job.updated_at = now
            result = dict(job.result or {})
            result["last_attempt"] = attempt
            job.result = result
            await db.commit()

    async def _mark_stage(self, *, job_id: uuid.UUID, tenant_id: str, stage: str, extra: dict[str, Any] | None = None) -> None:
        async with WriteSessionLocal() as db:
            job = await self.get_job(db, job_id, tenant_id)
            if not job:
                return
            now = _utcnow()
            job.stage = stage
            job.updated_at = now
            result = dict(job.result or {})
            stages = dict(result.get("stages") or {})
            stage_payload = dict(stages.get(stage) or {})
            stage_payload["at"] = now.isoformat()
            if extra:
                stage_payload.update(extra)
            stages[stage] = stage_payload
            result["stages"] = stages
            result["current_stage"] = stage
            job.result = result
            db.add(
                IngestionStageEvent(
                    id=uuid.uuid4(),
                    job_id=job_id,
                    tenant_id=tenant_id,
                    stage=stage,
                    status="ok",
                    detail=extra or {},
                    created_at=now,
                )
            )
            await db.commit()

    async def _mark_retrying(self, *, job_id: uuid.UUID, tenant_id: str, attempt: int, error: str) -> None:
        async with WriteSessionLocal() as db:
            job = await self.get_job(db, job_id, tenant_id)
            if not job:
                return
            now = _utcnow()
            job.status = "processing"
            job.stage = "retrying"
            job.error_message = error[:4000]
            job.updated_at = now
            result = dict(job.result or {})
            retries = list(result.get("retries") or [])
            retries.append({"attempt": attempt, "error": error[:500], "at": now.isoformat()})
            result["retries"] = retries
            job.result = result
            db.add(
                IngestionStageEvent(
                    id=uuid.uuid4(),
                    job_id=job_id,
                    tenant_id=tenant_id,
                    stage="retrying",
                    status="retrying",
                    detail={"attempt": attempt, "error": error[:500]},
                    created_at=now,
                )
            )
            await db.commit()

    async def _mark_completed(self, *, job_id: uuid.UUID, tenant_id: str, doc_id: uuid.UUID, chunk_count: int) -> None:
        async with WriteSessionLocal() as db:
            job = await self.get_job(db, job_id, tenant_id)
            if not job:
                return
            now = _utcnow()
            job.doc_id = doc_id
            job.status = "completed"
            job.stage = "completed"
            job.error_message = None
            job.completed_at = now
            job.updated_at = now
            result = dict(job.result or {})
            result["chunks_created"] = chunk_count
            result["dead_letter"] = False
            job.result = result
            await db.commit()

    async def _mark_failed(self, *, job_id: uuid.UUID, tenant_id: str, error: str, dead_letter: bool) -> None:
        async with WriteSessionLocal() as db:
            job = await self.get_job(db, job_id, tenant_id)
            if not job:
                return
            now = _utcnow()
            job.status = "failed"
            job.stage = "failed"
            job.error_message = error[:4000]
            job.completed_at = now
            job.updated_at = now
            result = dict(job.result or {})
            result["dead_letter"] = dead_letter
            result["failed_at"] = now.isoformat()
            job.result = result
            db.add(
                IngestionStageEvent(
                    id=uuid.uuid4(),
                    job_id=job_id,
                    tenant_id=tenant_id,
                    stage="failed",
                    status="error",
                    detail={"error": error[:1000], "dead_letter": dead_letter},
                    created_at=now,
                )
            )
            await db.commit()

    async def _send_dead_letter(self, payload: dict[str, Any]) -> None:
        topic = settings.ingestion_runtime.dead_letter_topic or settings.kafka.topic_dead_letter
        await kafka_connector.publish(topic, payload, key=payload.get("job_id"))


ingestion_service = IngestionService()
