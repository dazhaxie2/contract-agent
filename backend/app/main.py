"""
合同合规Agent系统 - FastAPI主应用
集成23层中间件、RAG管线、Agent框架、阿里云大模型
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from loguru import logger

from app.core.config import settings
from app.core.database import init_db, close_db
from app.middleware import register_middleware
from app.api.v1.router import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info(f"🚀 {settings.app_name} v{settings.app_version} 启动中...")
    logger.info(f"环境: {settings.environment} | 模型: {settings.llm.generation_model}")

    # 初始化数据库
    try:
        await init_db()
        logger.info("数据库初始化完成")
    except Exception as e:
        logger.warning(f"数据库初始化跳过(开发模式): {e}")

    yield

    # 清理资源
    await close_db()
    logger.info("应用已关闭")


def create_app() -> FastAPI:
    """创建FastAPI应用实例"""
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "合同合规Agent系统 - 基于Agentic RAG架构\n\n"
            "融合Graph RAG、Self-RAG、CRAG，支持多Agent协同、阿里云通义千问大模型、\n"
            "多路混合检索、全链路追踪、模型配置可视化、提示词管理可视化"
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # 注册23层中间件
    register_middleware(app)

    # 注册API路由
    app.include_router(api_router)

    # 健康检查端点(不经过中间件)
    @app.get("/health")
    async def health():
        return {"status": "healthy", "version": settings.app_version}

    @app.get("/ready")
    async def ready():
        return {"ready": True}

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
