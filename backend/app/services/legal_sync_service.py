"""Official legal source synchronization service."""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from loguru import logger

from app.core.config import settings
from app.core.database import WriteSessionLocal
from app.models.ingestion import IngestionJob
from app.services.connectors import legal_source_connector
from app.services.ingestion_orchestrator import ingestion_orchestrator
from app.services.ingestion_service import ingestion_service


@dataclass
class LegalSyncResult:
    tenant_id: str
    total: int
    enqueued: int
    skipped: int
    failed: int
    jobs: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "total": self.total,
            "enqueued": self.enqueued,
            "skipped": self.skipped,
            "failed": self.failed,
            "job_ids": self.jobs,
        }


class LegalSyncService:
    def __init__(self) -> None:
        self._scheduler_task: asyncio.Task | None = None
        self._stopped = False

    def is_tenant_allowed(self, tenant_id: str) -> bool:
        allow = settings.legal_source.tenant_allowlist_values
        return (not allow) or (tenant_id in allow)

    async def run_sync_once(self, *, tenant_id: str, limit: int | None = None) -> LegalSyncResult:
        if not settings.legal_source.enabled:
            return LegalSyncResult(tenant_id=tenant_id, total=0, enqueued=0, skipped=0, failed=0, jobs=[])
        if not self.is_tenant_allowed(tenant_id):
            return LegalSyncResult(tenant_id=tenant_id, total=0, enqueued=0, skipped=0, failed=0, jobs=[])

        docs = await legal_source_connector.fetch_documents(limit=limit)
        enqueued = 0
        skipped = 0
        failed = 0
        jobs: list[str] = []

        for item in docs:
            content = item.content.strip()
            if len(content) < 120:
                skipped += 1
                continue

            file_name = f"legal-{hashlib.sha1(item.source_url.encode('utf-8')).hexdigest()[:16]}.txt"
            payload = {
                "source_type": "official_legal_source",
                "source_url": item.source_url,
                "authority": item.authority,
                "published_at": item.published_at.isoformat(),
            }

            try:
                async with WriteSessionLocal() as db:
                    row = await ingestion_service.create_job(
                        db=db,
                        tenant_id=tenant_id,
                        user_id=None,
                        file_name=file_name,
                        doc_type="law",
                        title=item.title,
                        payload=payload,
                    )
                    await db.commit()
                    job_id = row.id
                ok = await ingestion_orchestrator.enqueue_document_job(
                    job_id=job_id,
                    tenant_id=tenant_id,
                    user_id=None,
                    file_name=file_name,
                    content_type="text/plain; charset=utf-8",
                    raw_bytes=content.encode("utf-8"),
                    doc_type="law",
                    title=item.title,
                    source_type="official_legal_source",
                    source_url=item.source_url,
                )
                if ok:
                    enqueued += 1
                    jobs.append(str(job_id))
                else:
                    failed += 1
            except Exception as exc:
                logger.warning(f"Legal sync enqueue failed url={item.source_url}: {exc}")
                failed += 1

        return LegalSyncResult(
            tenant_id=tenant_id,
            total=len(docs),
            enqueued=enqueued,
            skipped=skipped,
            failed=failed,
            jobs=jobs,
        )

    async def start_scheduler(self) -> None:
        if self._scheduler_task is not None:
            return
        if not settings.legal_source.enabled:
            return

        async def _loop() -> None:
            interval = max(60, settings.legal_source.sync_interval_minutes * 60)
            while not self._stopped:
                try:
                    for tenant_id in sorted(settings.legal_source.tenant_allowlist_values or {"default"}):
                        result = await self.run_sync_once(tenant_id=tenant_id)
                        logger.info(f"Legal source scheduled sync: {result.to_dict()}")
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    logger.warning(f"Legal source scheduled sync failed: {exc}")
                await asyncio.sleep(interval)

        self._stopped = False
        self._scheduler_task = asyncio.create_task(_loop(), name="legal-source-sync")

    async def stop_scheduler(self) -> None:
        self._stopped = True
        task = self._scheduler_task
        self._scheduler_task = None
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


legal_sync_service = LegalSyncService()

