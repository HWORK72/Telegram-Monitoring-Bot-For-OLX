import logging
from typing import AsyncGenerator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from core.config import get_settings
from database.models import Base

logger: logging.Logger = logging.getLogger("app.database")
settings = get_settings()

engine: AsyncEngine = create_async_engine(
    settings.database_url,
    echo=settings.DB_ECHO,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600,
)

async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def init_database() -> None:
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await conn.execute(
                text("ALTER TABLE seen_offers ALTER COLUMN price TYPE TEXT;")
            )
            await conn.execute(
                text("ALTER TABLE seen_offers ALTER COLUMN published_at TYPE TEXT;")
            )
            await conn.execute(
                text("ALTER TABLE seen_offers ADD COLUMN IF NOT EXISTS phone TEXT;")
            )
        logger.info("Database schema synchronized and phone column verified.")
    except Exception as exc:
        logger.error("Failed to initialize database schema: %s", exc, exc_info=True)
        raise exc


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
        except Exception as exc:
            await session.rollback()
            logger.error("Database session rolled back due to error: %s", exc, exc_info=True)
            raise exc
        finally:
            await session.close()