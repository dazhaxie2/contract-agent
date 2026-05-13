"""Ingestion queue orchestration (Kafka-first with local fallback)."""

from __future__ import annotations

import asyncio
import base64
from typing import Any
from uuid import UUID

from loguru import logger

from app.core.config import settings
from app.services.connectors import kafka_connector
from app.services.ingestion_service import ingestion_service


class IngestionOrchestrator:
    def __init__(self) -> None:
        self._consumer_started = False

    async def start(self) -> None:
        if self._consumer_started:
            return
        if not settings.ingestion_runtime.consumer_enabled:
            return
        if not settings.ingestion_runtime.use_kafka:
            return

        topic = settings.ingestion_runtime.consumer_topic or settings.kafka.topic_document_upload
        started = await kafka_connector.start_consumer(topic, self._handle_ingestion_message)
        if started:
            self._consumer_started = True
            logger.info(f"Ingestion Kafka consumer started topic={topic}")
        else:
            logger.warning("Ingestion Kafka consumer not started, using local async fallback")

    async def stop(self) -> None:
        await kafka_connector.stop()
        self._consumer_started = False

    async def enqueue_document_job(
        self,
        *,
        job_id: UUID,
        tenant_id: str,
        user_id: UUID | None,
        file_name: str,
        content_type: str | None,
        raw_bytes: bytes,
        doc_type: str,
        title: str,
        source_type: str = "upload",
        source_url: str | None = None,
    ) -> bool:
        payload = {
            "event_type": "ingestion.document.uploaded",
            "job_id": str(job_id),
            "tenant_id": tenant_id,
            "user_id": str(user_id) if user_id else "",
            "file_name": file_name,
            "content_type": content_type or "application/octet-stream",
            "raw_base64": base64.b64encode(raw_bytes).decode("ascii"),
            "doc_type": doc_type,
            "title": title,
            "source_type": source_type,
            "source_url": source_url or "",
        }

        use_kafka = settings.ingestion_runtime.use_kafka
        topic = settings.ingestion_runtime.consumer_topic or settings.kafka.topic_document_upload
        if use_kafka:
            published = await kafka_connector.publish(topic, payload, key=str(job_id))
            if published:
                return True
            logger.warning("Kafka publish failed; fallback to local async ingestion")

        asyncio.create_task(
            ingestion_service.run_job_sync(
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
        return True

    async def _handle_ingestion_message(self, payload: dict[str, Any]) -> None:
        if payload.get("event_type") != "ingestion.document.uploaded":
            return
        raw_b64 = str(payload.get("raw_base64") or "")
        if not raw_b64:
            return
        raw_bytes = base64.b64decode(raw_b64.encode("ascii"))

        user_id_raw = str(payload.get("user_id") or "").strip()
        user_uuid = None
        if user_id_raw:
            try:
                user_uuid = UUID(user_id_raw)
            except ValueError:
                user_uuid = None

        await ingestion_service.run_job_sync(
            job_id=UUID(str(payload["job_id"])),
            tenant_id=str(payload["tenant_id"]),
            user_id=user_uuid,
            file_name=str(payload.get("file_name") or "document.txt"),
            content_type=str(payload.get("content_type") or "application/octet-stream"),
            raw_bytes=raw_bytes,
            doc_type=str(payload.get("doc_type") or "auto"),
            title=str(payload.get("title") or ""),
            source_type=str(payload.get("source_type") or "upload"),
            source_url=str(payload.get("source_url") or "") or None,
        )


ingestion_orchestrator = IngestionOrchestrator()

