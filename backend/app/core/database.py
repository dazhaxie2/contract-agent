"""
数据库引擎与会话管理 - 支持读写分离
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    pass


# 写库引擎
write_engine = create_async_engine(
    settings.database.write_url,
    pool_size=settings.database.pool_size,
    max_overflow=settings.database.max_overflow,
    pool_timeout=settings.database.pool_timeout,
    pool_recycle=settings.database.pool_recycle,
    echo=settings.database.echo,
)

# 读库引擎(读写分离)
read_engine = create_async_engine(
    settings.database.read_url,
    pool_size=settings.database.pool_size,
    max_overflow=settings.database.max_overflow,
    pool_timeout=settings.database.pool_timeout,
    pool_recycle=settings.database.pool_recycle,
    echo=settings.database.echo,
)

WriteSessionLocal = async_sessionmaker(
    bind=write_engine, class_=AsyncSession, expire_on_commit=False
)

ReadSessionLocal = async_sessionmaker(
    bind=read_engine, class_=AsyncSession, expire_on_commit=False
)


async def get_write_db() -> AsyncGenerator[AsyncSession, None]:
    async with WriteSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_read_db() -> AsyncGenerator[AsyncSession, None]:
    async with ReadSessionLocal() as session:
        yield session


@asynccontextmanager
async def get_write_session() -> AsyncGenerator[AsyncSession, None]:
    async with WriteSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def get_read_session() -> AsyncGenerator[AsyncSession, None]:
    async with ReadSessionLocal() as session:
        yield session


async def init_db():
    async with write_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    await write_engine.dispose()
    await read_engine.dispose()
