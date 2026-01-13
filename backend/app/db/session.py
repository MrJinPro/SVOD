from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings


def create_engine(url: str) -> AsyncEngine:
    if url.lower().startswith("sqlite"):
        # SQLite is sensitive to concurrent writes; increase timeout and avoid pooling.
        return create_async_engine(
            url,
            pool_pre_ping=True,
            connect_args={"timeout": 60},
            poolclass=NullPool,
        )
    return create_async_engine(url, pool_pre_ping=True)


engine: AsyncEngine = create_engine(settings.database_url)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
