"""认证API"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.core.security import (
    create_access_token, create_refresh_token,
    verify_password, get_password_hash, decode_token,
    Roles,
)

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
async def login(req: LoginRequest):
    """用户登录"""
    # 简化示例：生产环境查询数据库
    # user = await db.get_user_by_username(req.username)
    # if not user or not verify_password(req.password, user.hashed_password):
    #     raise HTTPException(401, "用户名或密码错误")

    token_data = {
        "sub": "00000000-0000-0000-0000-000000000001",
        "username": req.username,
        "role": "admin",
        "tenant_id": "default",
    }
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )


@router.post("/register")
async def register(req: RegisterRequest):
    """用户注册"""
    hashed = get_password_hash(req.password)
    return {"message": "注册成功", "username": req.username}


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(refresh_token: str):
    """刷新Token"""
    payload = decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(401, "无效的刷新令牌")

    token_data = {k: v for k, v in payload.items() if k not in ("exp", "type")}
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )


@router.get("/me")
async def current_user(request: Request):
    role = getattr(request.state, "user_role", "viewer")
    permissions = sorted(Roles.PERMISSIONS.get(role, set()))
    return {
        "user_id": getattr(request.state, "user_id", ""),
        "tenant_id": getattr(request.state, "tenant_id", "default"),
        "role": role,
        "permissions": permissions,
    }
