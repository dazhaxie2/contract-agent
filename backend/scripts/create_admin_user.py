"""Create or promote an admin user during deployment initialization.

Usage:
    ADMIN_USERNAME=admin ADMIN_EMAIL=admin@example.com ADMIN_PASSWORD=... python scripts/create_admin_user.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timezone

from sqlalchemy import select

import app.models  # noqa: F401
from app.core.database import WriteSessionLocal
from app.core.security import Roles, get_password_hash
from app.models.user import User


async def main() -> int:
    username = os.getenv("ADMIN_USERNAME", "admin").strip()
    email = os.getenv("ADMIN_EMAIL", "admin@example.com").strip()
    password = os.getenv("ADMIN_PASSWORD", "").strip()
    tenant_id = os.getenv("ADMIN_TENANT_ID", "default").strip()

    if not password:
        print("ADMIN_PASSWORD is required", file=sys.stderr)
        return 2

    now = datetime.now(timezone.utc)
    async with WriteSessionLocal() as session:
        user = await session.scalar(
            select(User).where(
                User.tenant_id == tenant_id,
                User.username == username,
            )
        )
        if user:
            user.email = email
            user.hashed_password = get_password_hash(password)
            user.role = Roles.ADMIN
            user.is_active = True
            user.is_superuser = True
            user.updated_at = now
            action = "updated"
        else:
            user = User(
                username=username,
                email=email,
                hashed_password=get_password_hash(password),
                full_name=username,
                role=Roles.ADMIN,
                tenant_id=tenant_id,
                is_active=True,
                is_superuser=True,
                preferences={},
                created_at=now,
                updated_at=now,
            )
            session.add(user)
            action = "created"

        await session.commit()
        print(f"admin user {action}: tenant={tenant_id} username={username}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
