"""认证API"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_read_db, get_write_db
from app.core.security import (
    create_access_token, create_refresh_token,
    verify_password, get_password_hash, decode_token,
    Roles,
)
from app.models.user import User

router = APIRouter()


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=6)


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    email: str
    password: str = Field(..., min_length=8)
    full_name: str = ""
    tenant_id: str = "default"


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_write_db)):
    """用户登录"""
    user = await db.scalar(select(User).where(User.username == req.username))
    if not user or not user.is_active or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    user.last_login_at = datetime.now(timezone.utc)

    token_data = {
        "sub": str(user.id),
        "username": user.username,
        "role": user.role,
        "tenant_id": user.tenant_id,
    }
    await db.flush()
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )


@router.post("/register")
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_write_db)):
    """用户注册"""
    existing = await db.scalar(select(User).where(or_(User.username == req.username, User.email == req.email)))
    if existing:
        raise HTTPException(status_code=409, detail="用户名或邮箱已存在")

    hashed = get_password_hash(req.password)
    role = Roles.VIEWER
    now = datetime.now(timezone.utc)
    user = User(
        username=req.username,
        email=req.email,
        hashed_password=hashed,
        full_name=req.full_name or None,
        role=role,
        tenant_id=req.tenant_id,
        is_active=True,
        is_superuser=role == Roles.ADMIN,
        preferences={},
        created_at=now,
        updated_at=now,
    )
    db.add(user)
    await db.flush()
    return {
        "message": "注册成功",
        "user_id": str(user.id),
        "username": user.username,
        "tenant_id": user.tenant_id,
        "role": user.role,
    }


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(refresh_token: str, db: AsyncSession = Depends(get_read_db)):
    """刷新Token"""
    payload = decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(401, "无效的刷新令牌")

    try:
        user_uuid = uuid.UUID(str(payload.get("sub", "")))
    except (TypeError, ValueError):
        raise HTTPException(401, "无效的刷新令牌") from None

    tenant_id = payload.get("tenant_id") or "default"
    user = await db.scalar(select(User).where(User.id == user_uuid, User.tenant_id == tenant_id))
    if not user:
        raise HTTPException(401, "用户不存在")
    if not user.is_active:
        raise HTTPException(403, "用户已停用")

    token_data = {
        "sub": str(user.id),
        "username": user.username,
        "role": user.role,
        "tenant_id": user.tenant_id,
    }
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )


@router.get("/me")
async def current_user(request: Request, db: AsyncSession = Depends(get_read_db)):
    user_id = getattr(request.state, "user_id", "")
    user = None
    if user_id:
        try:
            user = await db.scalar(select(User).where(User.id == uuid.UUID(user_id)))
        except (TypeError, ValueError):
            user = None

    if user and not user.is_active:
        raise HTTPException(status_code=403, detail="用户已停用")

    role = getattr(request.state, "user_role", "viewer")
    if user:
        role = user.role
    permissions = sorted(Roles.PERMISSIONS.get(role, set()))
    return {
        "user_id": str(user.id) if user else user_id,
        "username": user.username if user else getattr(request.state, "username", ""),
        "tenant_id": user.tenant_id if user else getattr(request.state, "tenant_id", "default"),
        "role": role,
        "permissions": permissions,
    }
