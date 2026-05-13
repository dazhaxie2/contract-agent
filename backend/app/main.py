"""Contract agent FastAPI application entrypoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from loguru import logger

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import check_database_health, close_db, get_database_switch_state, init_db
from app.middleware import register_middleware
from app.services.connectors_health_service import connectors_health_service
from app.services.ingestion_orchestrator import ingestion_orchestrator
from app.services.legal_sync_service import legal_sync_service


def _should_auto_create_schema() -> bool:
    configured = settings.database.auto_create_schema
    if configured is not None:
        return bool(configured)
    return settings.environment.lower() in {"development", "dev", "local", "test", "testing"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management."""
    db_switch = get_database_switch_state()
    auto_create_schema = _should_auto_create_schema()
    app.state.auto_create_schema = auto_create_schema
    app.state.db_startup_message = ""

    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Environment={settings.environment} model={settings.llm.generation_model}")
    logger.info(
        "DB switch state: "
        f"provider={db_switch['provider']} "
        f"write={db_switch['write_target']} "
        f"read={db_switch['read_target']} "
        f"dual_write={db_switch['dual_write_enabled']}"
    )
    logger.info(f"DB auto create schema={auto_create_schema}")

    try:
        await init_db(auto_create_schema=auto_create_schema)
        logger.info("Database startup initialization completed")
    except Exception as exc:
        logger.warning(f"Database initialization skipped/failed: {exc}")

    db_health = await check_database_health()
    if db_health["status"] != "healthy":
        if not auto_create_schema:
            app.state.db_startup_message = "Database schema is not ready. Run `alembic upgrade head`."
            logger.error(f"Database migration required before serving traffic: {db_health}")
        else:
            app.state.db_startup_message = "Database health check failed after startup auto-create."
            logger.warning(f"Database health check failed: {db_health}")
    else:
        app.state.db_startup_message = "Database ready"

    try:
        await ingestion_orchestrator.start()
    except Exception as exc:
        logger.warning(f"Failed to start ingestion orchestrator: {exc}")

    try:
        await legal_sync_service.start_scheduler()
    except Exception as exc:
        logger.warning(f"Failed to start legal source scheduler: {exc}")

    yield

    await legal_sync_service.stop_scheduler()
    await ingestion_orchestrator.stop()
    await close_db()
    logger.info("Application shutdown completed")


def create_app() -> FastAPI:
    """Create FastAPI application instance."""
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Contract compliance agent backend service.",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    register_middleware(app)
    app.include_router(api_router)

    @app.get("/health")
    async def health():
        db_health = await check_database_health()
        connectors = await connectors_health_service.collect()
        status = "healthy" if db_health["status"] == "healthy" and connectors["ok"] else "degraded"
        return {
            "status": status,
            "version": settings.app_version,
            "database": db_health,
            "connectors": connectors,
            "startup": {
                "auto_create_schema": getattr(app.state, "auto_create_schema", None),
                "message": getattr(app.state, "db_startup_message", ""),
            },
        }

    @app.get("/ready")
    async def ready():
        db_health = await check_database_health()
        connectors = await connectors_health_service.collect()
        is_ready = db_health["status"] == "healthy" and connectors["ok"]
        payload = {
            "ready": is_ready,
            "database": db_health,
            "connectors": connectors,
            "startup": {
                "auto_create_schema": getattr(app.state, "auto_create_schema", None),
                "message": getattr(app.state, "db_startup_message", ""),
            },
        }
        if is_ready:
            return payload

        if getattr(app.state, "auto_create_schema", True) is False:
            payload["error"] = "DATABASE_MIGRATION_REQUIRED"
            payload["hint"] = "Run `alembic upgrade head` and restart."
        return JSONResponse(status_code=503, content=payload)

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        workers=settings.workers,
        log_level=settings.log_level.lower(),
        reload=settings.debug,
    )
