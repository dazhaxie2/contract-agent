from __future__ import annotations

import os
from collections.abc import AsyncIterator
from pathlib import Path

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

# Use isolated SQLite for local test runs.
TEST_DB_PATH = Path(__file__).resolve().parent / "test_local.db"
TEST_DB_DSN = f"sqlite+aiosqlite:///{TEST_DB_PATH.as_posix()}"

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DB_AUTO_CREATE_SCHEMA", "true")
os.environ.setdefault("DB_DSN_WRITE", TEST_DB_DSN)
os.environ.setdefault("DB_DSN_READ", TEST_DB_DSN)
os.environ.setdefault("DB_PROVIDER", "hidb_pg")
os.environ.setdefault("DB_DUAL_WRITE_ENABLED", "false")
os.environ.setdefault("INGESTION_USE_KAFKA", "false")
os.environ.setdefault("LEGAL_SOURCE_ENABLED", "false")
os.environ.setdefault("LLM_REQUIRE_EXTERNAL", "false")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

import app.models  # noqa: E402,F401
from app.core.database import Base, WriteSessionLocal, close_db, init_db  # noqa: E402
from app.main import create_app  # noqa: E402


@pytest_asyncio.fixture(scope="session")
async def app_client() -> AsyncIterator[AsyncClient]:
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()

    await init_db(auto_create_schema=True)
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
    await close_db()
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()


@pytest_asyncio.fixture()
async def auth_headers(app_client: AsyncClient) -> dict[str, str]:
    register_resp = await app_client.post(
        "/api/v1/auth/register",
        json={
            "username": "admin",
            "email": "admin@example.com",
            "password": "password123",
            "full_name": "Admin",
            "tenant_id": "default",
        },
    )
    assert register_resp.status_code in {200, 409}, register_resp.text
    resp = await app_client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "password123"},
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    data = payload.get("data", payload)
    token = data["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture(autouse=True)
async def cleanup_db() -> AsyncIterator[None]:
    async with WriteSessionLocal() as session:
        for table in reversed(Base.metadata.sorted_tables):
            await session.execute(delete(table))
        await session.commit()
    yield
