from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import delete

from app.core.database import WriteSessionLocal
from app.core.security import Roles, create_access_token, get_password_hash
from app.models.user import User


def _data(resp) -> dict:
    payload = resp.json()
    if isinstance(payload, dict) and "data" in payload and "code" in payload:
        return payload["data"]
    return payload


async def _create_user(*, role: str = Roles.VIEWER, tenant_id: str = "default", active: bool = True) -> User:
    user = User(
        id=uuid.uuid4(),
        username=f"user_{uuid.uuid4().hex[:8]}",
        email=f"{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=get_password_hash("password123"),
        role=role,
        tenant_id=tenant_id,
        is_active=active,
        is_superuser=role == Roles.ADMIN,
        preferences={},
    )
    async with WriteSessionLocal() as session:
        session.add(user)
        await session.commit()
    return user


def _token_for(user: User, *, role: str | None = None, tenant_id: str | None = None) -> str:
    return create_access_token(
        {
            "sub": str(user.id),
            "username": user.username,
            "role": role or user.role,
            "tenant_id": tenant_id or user.tenant_id,
        }
    )


@pytest.mark.asyncio
async def test_deleted_user_token_is_rejected(app_client: AsyncClient) -> None:
    user = await _create_user(role=Roles.ADMIN)
    token = _token_for(user)
    async with WriteSessionLocal() as session:
        await session.execute(delete(User).where(User.id == user.id))
        await session.commit()

    resp = await app_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_public_register_never_bootstraps_admin(app_client: AsyncClient) -> None:
    resp = await app_client.post(
        "/api/v1/auth/register",
        json={
            "username": "first_public_user",
            "email": "first-public-user@example.com",
            "password": "password123",
            "tenant_id": "default",
        },
    )
    assert resp.status_code == 200, resp.text
    payload = _data(resp)
    assert payload["role"] == Roles.VIEWER


@pytest.mark.asyncio
async def test_token_role_cannot_override_database_role(app_client: AsyncClient) -> None:
    user = await _create_user(role=Roles.VIEWER)
    forged_admin_token = _token_for(user, role=Roles.ADMIN)

    resp = await app_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {forged_admin_token}"})
    assert resp.status_code == 200
    payload = _data(resp)
    assert payload["role"] == Roles.VIEWER
    assert "model:write" not in payload["permissions"]


@pytest.mark.asyncio
async def test_token_tenant_mismatch_is_rejected(app_client: AsyncClient) -> None:
    user = await _create_user(role=Roles.ADMIN, tenant_id="default")
    wrong_tenant_token = _token_for(user, tenant_id="other")

    resp = await app_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {wrong_tenant_token}"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_api_key_path_sets_api_client_context(app_client: AsyncClient) -> None:
    resp = await app_client.get(
        "/api/v1/auth/me",
        headers={"X-API-Key": "test-api-key", "X-Tenant-ID": "default", "X-User-ID": "api_user"},
    )
    assert resp.status_code == 200
    payload = _data(resp)
    assert payload["tenant_id"] == "default"
    assert payload["role"] == "api_client"
