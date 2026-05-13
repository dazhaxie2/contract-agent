"""MinIO object storage connector."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from loguru import logger

from app.core.config import settings
from app.services.connectors.types import ConnectorHealth

try:
    from minio import Minio
    from minio.error import S3Error

    HAS_MINIO = True
except Exception:  # pragma: no cover - optional runtime dependency failures.
    Minio = Any  # type: ignore[assignment]
    S3Error = Exception  # type: ignore[assignment]
    HAS_MINIO = False


class MinioConnector:
    def __init__(self) -> None:
        self._client: Minio | None = None
        self._bucket_ready = False

    def _build_client(self) -> Minio | None:
        if not HAS_MINIO:
            return None
        return Minio(
            endpoint=settings.minio.endpoint,
            access_key=settings.minio.access_key,
            secret_key=settings.minio.secret_key,
            secure=settings.minio.secure,
        )

    async def _client_or_none(self) -> Minio | None:
        if self._client is None:
            self._client = await asyncio.to_thread(self._build_client)
        return self._client

    async def ensure_bucket(self) -> bool:
        if self._bucket_ready:
            return True
        client = await self._client_or_none()
        if not client:
            return False

        bucket = settings.minio.bucket
        try:
            exists = await asyncio.to_thread(client.bucket_exists, bucket)
            if not exists:
                await asyncio.to_thread(client.make_bucket, bucket)
            self._bucket_ready = True
            return True
        except Exception as exc:
            logger.warning(f"MinIO ensure bucket failed: {exc}")
            return False

    async def upload_bytes(self, object_name: str, payload: bytes, content_type: str) -> str | None:
        client = await self._client_or_none()
        if not client:
            return None
        if not await self.ensure_bucket():
            return None

        try:
            import io

            stream = io.BytesIO(payload)
            await asyncio.to_thread(
                client.put_object,
                settings.minio.bucket,
                object_name,
                stream,
                len(payload),
                content_type=content_type,
            )
            return f"s3://{settings.minio.bucket}/{object_name}"
        except Exception as exc:
            logger.warning(f"MinIO upload failed for {object_name}: {exc}")
            return None

    async def health(self) -> ConnectorHealth:
        started = time.perf_counter()
        client = await self._client_or_none()
        if not client:
            return ConnectorHealth(name="minio", ok=False, detail="client unavailable")

        try:
            await self.ensure_bucket()
            ok = await asyncio.to_thread(client.bucket_exists, settings.minio.bucket)
            latency_ms = (time.perf_counter() - started) * 1000
            return ConnectorHealth(
                name="minio",
                ok=bool(ok),
                latency_ms=latency_ms,
                detail=f"bucket={settings.minio.bucket}",
            )
        except Exception as exc:
            latency_ms = (time.perf_counter() - started) * 1000
            return ConnectorHealth(name="minio", ok=False, latency_ms=latency_ms, detail=str(exc))


minio_connector = MinioConnector()

