"""API v1 router registry."""

from fastapi import APIRouter

from app.api.v1 import (
    agents,
    auth,
    citations,
    dashboard,
    documents,
    legal,
    memory,
    models,
    prompts,
    retrieval,
    sessions,
    system,
)

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(models.router, prefix="/models", tags=["models"])
api_router.include_router(prompts.router, prefix="/prompts", tags=["prompts"])
api_router.include_router(agents.router, prefix="/agents", tags=["agents"])
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_router.include_router(legal.router, prefix="/legal", tags=["legal"])
api_router.include_router(sessions.router, prefix="/sessions", tags=["sessions"])
api_router.include_router(memory.router, prefix="/memory", tags=["memory"])
api_router.include_router(retrieval.router, prefix="/retrieval", tags=["retrieval"])
api_router.include_router(citations.router, prefix="/citations", tags=["citations"])
api_router.include_router(system.router, prefix="/system", tags=["system"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
