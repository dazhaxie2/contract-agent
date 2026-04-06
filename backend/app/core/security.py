"""
安全模块 - JWT认证、密码哈希、RBAC权限、数据加密
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from cryptography.fernet import Fernet

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.security.access_token_expire_minutes)
    )
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.security.secret_key, algorithm=settings.security.algorithm)


def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.security.refresh_token_expire_days)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.security.secret_key, algorithm=settings.security.algorithm)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.security.secret_key, algorithms=[settings.security.algorithm])
    except JWTError:
        return None


class DataEncryptor:
    """敏感数据加密器 (AES256)"""

    def __init__(self):
        key = settings.security.encryption_key
        if not key:
            key = Fernet.generate_key().decode()
        self._fernet = Fernet(key.encode() if isinstance(key, str) else key)

    def encrypt(self, data: str) -> str:
        return self._fernet.encrypt(data.encode()).decode()

    def decrypt(self, encrypted_data: str) -> str:
        return self._fernet.decrypt(encrypted_data.encode()).decode()


# RBAC角色定义
class Roles:
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    LEGAL_EXPERT = "legal_expert"
    COMPLIANCE_OFFICER = "compliance_officer"
    CONTRACT_MANAGER = "contract_manager"
    VIEWER = "viewer"

    # 权限矩阵
    PERMISSIONS = {
        SUPER_ADMIN: {"*"},
        ADMIN: {
            "user:read", "user:write", "user:delete",
            "model:read", "model:write", "model:deploy",
            "prompt:read", "prompt:write", "prompt:publish",
            "document:read", "document:write", "document:delete",
            "agent:read", "agent:execute",
            "system:read", "system:config",
        },
        LEGAL_EXPERT: {
            "document:read", "document:write",
            "agent:read", "agent:execute",
            "prompt:read",
            "model:read",
        },
        COMPLIANCE_OFFICER: {
            "document:read", "document:write",
            "agent:read", "agent:execute",
            "prompt:read", "prompt:write",
        },
        CONTRACT_MANAGER: {
            "document:read", "document:write",
            "agent:read", "agent:execute",
        },
        VIEWER: {
            "document:read", "agent:read", "prompt:read", "model:read",
        },
    }

    @classmethod
    def has_permission(cls, role: str, permission: str) -> bool:
        perms = cls.PERMISSIONS.get(role, set())
        return "*" in perms or permission in perms


encryptor = DataEncryptor()
