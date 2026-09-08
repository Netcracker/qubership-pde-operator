from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from pde_operator.config import Settings


class DBUtils:
    """Database connection helpers."""

    @staticmethod
    def create_engine(settings: Settings) -> AsyncEngine:
        # db connection pool
        return create_async_engine(settings.database_url, pool_pre_ping=True)

    @staticmethod
    def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
        return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

