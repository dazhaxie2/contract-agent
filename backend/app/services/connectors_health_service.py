"""Connector health aggregation service."""

from __future__ import annotations

import asyncio

from app.services.connectors import (
    kafka_connector,
    legal_source_connector,
    milvus_connector,
    minio_connector,
    nebula_connector,
)


class ConnectorsHealthService:
    async def collect(self) -> dict:
        checks = await asyncio.gather(
            minio_connector.health(),
            milvus_connector.health(),
            nebula_connector.health(),
            kafka_connector.health(),
            legal_source_connector.health(),
            return_exceptions=True,
        )
        services: dict[str, dict] = {}
        healthy = True
        for item in checks:
            if isinstance(item, Exception):
                healthy = False
                name = f"connector_{len(services) + 1}"
                services[name] = {"name": name, "ok": False, "detail": str(item), "latency_ms": 0.0}
                continue
            services[item.name] = item.to_dict()
            healthy = healthy and bool(item.ok)
        return {"ok": healthy, "services": services}


connectors_health_service = ConnectorsHealthService()

