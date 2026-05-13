"""Database engines, sessions, cutover state and health checks."""

from __future__ import annotations

import math
import random
import time
from collections import deque
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncGenerator

from loguru import logger
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    pass


def _create_engine(url: str, is_hidb: bool) -> AsyncEngine:
    return create_async_engine(url, **settings.database.pool_config(is_hidb=is_hidb))


PRIMARY_IS_HIDB = settings.database.db_provider == "hidb_pg"

write_engine = _create_engine(settings.database.write_url, is_hidb=PRIMARY_IS_HIDB)
read_engine = _create_engine(settings.database.read_url, is_hidb=PRIMARY_IS_HIDB)

legacy_write_engine: AsyncEngine | None = None
legacy_read_engine: AsyncEngine | None = None
if settings.database.legacy_dsn_write:
    legacy_write_engine = _create_engine(settings.database.legacy_dsn_write, is_hidb=False)
if settings.database.legacy_dsn_read:
    legacy_read_engine = _create_engine(settings.database.legacy_dsn_read, is_hidb=False)

WriteSessionLocal = async_sessionmaker(bind=write_engine, class_=AsyncSession, expire_on_commit=False)
ReadSessionLocal = async_sessionmaker(bind=read_engine, class_=AsyncSession, expire_on_commit=False)
LegacyWriteSessionLocal: async_sessionmaker[AsyncSession] | None = (
    async_sessionmaker(bind=legacy_write_engine, class_=AsyncSession, expire_on_commit=False)
    if legacy_write_engine
    else None
)
LegacyReadSessionLocal: async_sessionmaker[AsyncSession] | None = (
    async_sessionmaker(bind=legacy_read_engine, class_=AsyncSession, expire_on_commit=False)
    if legacy_read_engine
    else None
)


class MigrationMetrics:
    """Migration period metrics."""

    def __init__(self) -> None:
        self.dual_write_total = 0
        self.dual_write_success = 0
        self.dual_write_failed = 0
        self.dual_write_latency_total_ms = 0.0
        self.diff_detected = 0
        self._hidb_read_latency_samples_ms: deque[float] = deque(maxlen=500)

    def record_dual_write(self, success: bool, latency_ms: float) -> None:
        self.dual_write_total += 1
        self.dual_write_latency_total_ms += latency_ms
        if success:
            self.dual_write_success += 1
        else:
            self.dual_write_failed += 1

    def record_diff(self, count: int = 1) -> None:
        self.diff_detected += count

    def record_hidb_read_latency(self, latency_ms: float) -> None:
        if latency_ms >= 0:
            self._hidb_read_latency_samples_ms.append(latency_ms)

    def _read_latency_p95_ms(self) -> float:
        if not self._hidb_read_latency_samples_ms:
            return 0.0
        ordered = sorted(self._hidb_read_latency_samples_ms)
        idx = max(0, min(len(ordered) - 1, math.ceil(len(ordered) * 0.95) - 1))
        return ordered[idx]

    def snapshot(self) -> dict:
        avg_latency = self.dual_write_latency_total_ms / self.dual_write_total if self.dual_write_total else 0.0
        success_rate = self.dual_write_success / self.dual_write_total if self.dual_write_total else 1.0
        return {
            "dual_write_total": self.dual_write_total,
            "dual_write_success": self.dual_write_success,
            "dual_write_failed": self.dual_write_failed,
            "dual_write_success_rate": round(success_rate, 4),
            "dual_write_avg_latency_ms": round(avg_latency, 2),
            "diff_detected": self.diff_detected,
            "hidb_read_latency_p95_ms": round(self._read_latency_p95_ms(), 2),
        }


migration_metrics = MigrationMetrics()


@dataclass
class CapturedChange:
    kind: str  # upsert|delete
    model: type[Any]
    data: dict[str, Any]
    identity: tuple[Any, ...] | Any | None


def _capture_session_changes(session: AsyncSession) -> list[CapturedChange]:
    """Capture inserts/updates/deletes currently staged in one session."""
    changes: list[CapturedChange] = []

    for obj in session.new:
        insp = sa_inspect(obj)
        data = {attr.key: getattr(obj, attr.key) for attr in insp.mapper.column_attrs}
        identity = tuple(data.get(col.key) for col in insp.mapper.primary_key)
        changes.append(CapturedChange(kind="upsert", model=insp.mapper.class_, data=data, identity=identity))

    for obj in session.dirty:
        if not session.is_modified(obj, include_collections=False):
            continue
        insp = sa_inspect(obj)
        data = {attr.key: getattr(obj, attr.key) for attr in insp.mapper.column_attrs}
        identity = tuple(data.get(col.key) for col in insp.mapper.primary_key)
        changes.append(CapturedChange(kind="upsert", model=insp.mapper.class_, data=data, identity=identity))

    for obj in session.deleted:
        insp = sa_inspect(obj)
        identity = insp.identity
        data = {attr.key: getattr(obj, attr.key) for attr in insp.mapper.column_attrs}
        changes.append(CapturedChange(kind="delete", model=insp.mapper.class_, data=data, identity=identity))

    return changes


async def _apply_dual_write_changes(changes: list[CapturedChange]) -> bool:
    if not changes or not settings.database.dual_write_enabled or not LegacyWriteSessionLocal:
        return True

    start = time.perf_counter()
    success = True
    try:
        async with LegacyWriteSessionLocal() as legacy_session:
            for change in changes:
                if change.kind == "upsert":
                    await legacy_session.merge(change.model(**change.data))
                elif change.kind == "delete" and change.identity:
                    identity = (
                        change.identity[0]
                        if isinstance(change.identity, tuple) and len(change.identity) == 1
                        else change.identity
                    )
                    existing = await legacy_session.get(change.model, identity)
                    if existing is not None:
                        await legacy_session.delete(existing)
            await legacy_session.commit()
    except Exception as exc:
        success = False
        migration_metrics.record_diff(len(changes))
        logger.error(f"Dual-write replay failed: {exc}")
    finally:
        latency_ms = (time.perf_counter() - start) * 1000
        migration_metrics.record_dual_write(success=success, latency_ms=latency_ms)
    return success


def _select_read_sessionmaker() -> tuple[async_sessionmaker[AsyncSession], str]:
    target = (settings.database.read_target or "hidb").lower()
    primary_target = "hidb" if PRIMARY_IS_HIDB else "postgres"

    if target == "postgres" and LegacyReadSessionLocal:
        return LegacyReadSessionLocal, "postgres"
    if target == "canary" and LegacyReadSessionLocal:
        bucket = random.randint(1, 100)
        hidb_session = ReadSessionLocal if PRIMARY_IS_HIDB else LegacyReadSessionLocal
        pg_session = LegacyReadSessionLocal if PRIMARY_IS_HIDB else ReadSessionLocal
        if bucket <= settings.database.cutover_percent:
            return hidb_session, "hidb"
        return pg_session, "postgres"
    return ReadSessionLocal, primary_target


def get_database_switch_state() -> dict:
    return {
        "provider": settings.database.db_provider,
        "write_target": "hidb" if PRIMARY_IS_HIDB else "postgres",
        "read_target": settings.database.read_target,
        "cutover_percent": settings.database.cutover_percent,
        "dual_write_enabled": settings.database.dual_write_enabled,
        "legacy_write_enabled": bool(LegacyWriteSessionLocal),
        "legacy_read_enabled": bool(LegacyReadSessionLocal),
    }


def get_migration_metrics() -> dict:
    return migration_metrics.snapshot()


async def get_write_db() -> AsyncGenerator[AsyncSession, None]:
    async with WriteSessionLocal() as session:
        try:
            yield session
            changes = _capture_session_changes(session)
            await session.commit()
            await _apply_dual_write_changes(changes)
        except Exception:
            await session.rollback()
            raise


async def get_read_db() -> AsyncGenerator[AsyncSession, None]:
    sessionmaker, selected_target = _select_read_sessionmaker()
    start = time.perf_counter()
    async with sessionmaker() as session:
        yield session
    if selected_target == "hidb":
        latency_ms = (time.perf_counter() - start) * 1000
        migration_metrics.record_hidb_read_latency(latency_ms)


@asynccontextmanager
async def get_write_session() -> AsyncGenerator[AsyncSession, None]:
    async with WriteSessionLocal() as session:
        try:
            yield session
            changes = _capture_session_changes(session)
            await session.commit()
            await _apply_dual_write_changes(changes)
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def get_read_session() -> AsyncGenerator[AsyncSession, None]:
    sessionmaker, selected_target = _select_read_sessionmaker()
    start = time.perf_counter()
    async with sessionmaker() as session:
        yield session
    if selected_target == "hidb":
        latency_ms = (time.perf_counter() - start) * 1000
        migration_metrics.record_hidb_read_latency(latency_ms)


async def _inspect_engine(engine: AsyncEngine) -> dict:
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))

        def _run_inspector(sync_conn):
            inspector = sa_inspect(sync_conn)
            tables = set(inspector.get_table_names())
            indexes: dict[str, set[str]] = {}
            for table in tables:
                indexes[table] = {idx["name"] for idx in inspector.get_indexes(table)}
            return tables, indexes

        tables, indexes = await conn.run_sync(_run_inspector)
    return {"tables": tables, "indexes": indexes}


async def check_database_health(
    required_tables: list[str] | None = None,
    required_indexes: dict[str, list[str]] | None = None,
) -> dict:
    required_tables = required_tables or list(Base.metadata.tables.keys())
    required_indexes = required_indexes or {
        "documents": ["idx_doc_type_status", "idx_doc_tenant_type_date"],
        "document_chunks": ["idx_chunk_doc_index", "idx_chunk_hierarchy", "idx_chunk_tenant_search_text"],
        "agent_executions": ["idx_exec_tenant_status"],
        "sessions": ["idx_session_tenant_user_time"],
        "conversation_messages": ["idx_message_session_order"],
        "ingestion_jobs": ["idx_ingestion_tenant_status"],
        "ingestion_stage_events": ["idx_ingestion_event_job_stage"],
        "retrieval_logs": ["idx_retrieval_tenant_time"],
        "citation_records": ["idx_citation_tenant_code"],
    }

    result = {
        "write": {"ok": False, "missing_tables": [], "missing_indexes": {}},
        "read": {"ok": False, "missing_tables": [], "missing_indexes": {}},
        "legacy_write": {"ok": True},
        "legacy_read": {"ok": True},
        "status": "unhealthy",
    }

    try:
        write_catalog = await _inspect_engine(write_engine)
        missing_tables = sorted(set(required_tables) - write_catalog["tables"])
        missing_indexes: dict[str, list[str]] = {}
        for table, idx_names in required_indexes.items():
            existing = write_catalog["indexes"].get(table, set())
            missing = [idx for idx in idx_names if idx not in existing]
            if missing:
                missing_indexes[table] = missing
        result["write"] = {
            "ok": not missing_tables and not missing_indexes,
            "missing_tables": missing_tables,
            "missing_indexes": missing_indexes,
        }
    except Exception as exc:
        result["write"] = {"ok": False, "error": str(exc), "missing_tables": [], "missing_indexes": {}}

    try:
        read_catalog = await _inspect_engine(read_engine)
        missing_tables = sorted(set(required_tables) - read_catalog["tables"])
        missing_indexes: dict[str, list[str]] = {}
        for table, idx_names in required_indexes.items():
            existing = read_catalog["indexes"].get(table, set())
            missing = [idx for idx in idx_names if idx not in existing]
            if missing:
                missing_indexes[table] = missing
        result["read"] = {
            "ok": not missing_tables and not missing_indexes,
            "missing_tables": missing_tables,
            "missing_indexes": missing_indexes,
        }
    except Exception as exc:
        result["read"] = {"ok": False, "error": str(exc), "missing_tables": [], "missing_indexes": {}}

    if LegacyWriteSessionLocal and legacy_write_engine:
        try:
            await _inspect_engine(legacy_write_engine)
            result["legacy_write"] = {"ok": True}
        except Exception as exc:
            result["legacy_write"] = {"ok": False, "error": str(exc)}

    if LegacyReadSessionLocal and legacy_read_engine:
        try:
            await _inspect_engine(legacy_read_engine)
            result["legacy_read"] = {"ok": True}
        except Exception as exc:
            result["legacy_read"] = {"ok": False, "error": str(exc)}

    result["status"] = "healthy" if result["write"]["ok"] and result["read"]["ok"] else "unhealthy"
    return result


async def init_db(auto_create_schema: bool = True) -> None:
    """Initialize metadata tables when auto-create is enabled."""
    import app.models  # noqa: F401

    if not auto_create_schema:
        logger.info("DB auto create schema disabled; expecting Alembic migrations to be applied")
        return

    async with write_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    if LegacyWriteSessionLocal and legacy_write_engine:
        async with legacy_write_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    await write_engine.dispose()
    await read_engine.dispose()
    if legacy_write_engine:
        await legacy_write_engine.dispose()
    if legacy_read_engine:
        await legacy_read_engine.dispose()
