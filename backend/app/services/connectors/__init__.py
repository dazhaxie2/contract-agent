"""Connector singletons for external systems used by ingestion/retrieval."""

from app.services.connectors.kafka_connector import kafka_connector
from app.services.connectors.legal_source_connector import legal_source_connector
from app.services.connectors.milvus_connector import milvus_connector
from app.services.connectors.minio_connector import minio_connector
from app.services.connectors.nebula_connector import nebula_connector

__all__ = [
    "minio_connector",
    "milvus_connector",
    "nebula_connector",
    "kafka_connector",
    "legal_source_connector",
]

