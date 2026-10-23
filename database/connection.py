import logging
from typing import AsyncGenerator, List
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from core.config import get_settings
from database.models import Base, MonitoredLink, User

logger: logging.Logger = logging.getLogger("app.database")
settings = get_settings()

DEFAULT_ROMANIA_TITLE: str = "🇷🇴 Romania Global Feed"
DEFAULT_ROMANIA_URL: str = "https://www.olx.ro/oferte/?search%5Border%5D=created_at:desc"

engine: AsyncEngine = create_async_engine(
    settings.database_url,
    echo=settings.DB_ECHO,
)

async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def _seed_default_links() -> None:
    async with async_session_factory() as session:
        count_query = select(func.count(MonitoredLink.id))
        result = await session.execute(count_query)
        existing_count: int = result.scalar() or 0

        if existing_count > 0:
            return

        admin_ids: List[int] = (
            settings.ADMIN_IDS if isinstance(settings.ADMIN_IDS, list) and settings.ADMIN_IDS else [8074283327]
        )

        for admin_id in admin_ids:
            user_query = select(User).where(User.telegram_id == admin_id)
            user_res = await session.execute(user_query)
            user = user_res.scalar_one_or_none()

            if user is None:
                user = User(
                    telegram_id=admin_id,
                    username="admin",
                    first_name="Operator",
                    is_active=True,
                )
                session.add(user)

            default_link = MonitoredLink(
                user_id=admin_id,
                title=DEFAULT_ROMANIA_TITLE,
                url=DEFAULT_ROMANIA_URL,
                is_active=True,
            )
            session.add(default_link)

        await session.commit()
        logger.info("Default Romania Global Feed link seeded automatically.")


async def init_database() -> None:
    try:
        async with engine.begin() as conn:
            await conn.execute(text("PRAGMA journal_mode=WAL;"))
            await conn.execute(text("PRAGMA synchronous=NORMAL;"))
            await conn.execute(text("PRAGMA foreign_keys=ON;"))
            await conn.run_sync(Base.metadata.create_all)
        await _seed_default_links()
        logger.info("Standalone local database initialized successfully.")
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