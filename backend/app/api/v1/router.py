"""API v1 路由聚合"""

from fastapi import APIRouter

from app.api.v1 import auth, models, prompts, agents, documents, system

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router, prefix="/auth", tags=["认证"])
api_router.include_router(models.router, prefix="/models", tags=["模型配置"])
api_router.include_router(prompts.router, prefix="/prompts", tags=["提示词管理"])
api_router.include_router(agents.router, prefix="/agents", tags=["Agent执行"])
api_router.include_router(documents.router, prefix="/documents", tags=["文档管理"])
api_router.include_router(system.router, prefix="/system", tags=["系统管理"])
