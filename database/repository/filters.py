import logging
from typing import Set
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession
from database.models.filter import BlacklistRecord, StopwordRecord

logger: logging.Logger = logging.getLogger("app.repository.filters")


async def get_user_blacklist(session: AsyncSession, user_id: int) -> Set[str]:
    try:
        query = select(BlacklistRecord.target_value).where(BlacklistRecord.user_id == user_id)
        result = await session.execute(query)
        return set(result.scalars().all())
    except Exception as exc:
        logger.error("Error fetching blacklist for user %d: %s", user_id, exc, exc_info=True)
        return set()


async def add_to_blacklist(session: AsyncSession, user_id: int, value: str) -> bool:
    try:
        stmt = (
            sqlite_insert(BlacklistRecord)
            .values(user_id=user_id, target_value=value.strip())
            .on_conflict_do_nothing(index_elements=["user_id", "target_value"])
        )
        await session.execute(stmt)
        await session.commit()
        return True
    except Exception as exc:
        await session.rollback()
        logger.error("Error adding to blacklist for user %d: %s", user_id, exc, exc_info=True)
        return False


async def get_user_stopwords(session: AsyncSession, user_id: int) -> Set[str]:
    try:
        query = select(StopwordRecord.word).where(StopwordRecord.user_id == user_id)
        result = await session.execute(query)
        return {w.lower() for w in result.scalars().all()}
    except Exception as exc:
        logger.error("Error fetching stopwords for user %d: %s", user_id, exc, exc_info=True)
        return set()


async def add_stopword(session: AsyncSession, user_id: int, word: str) -> bool:
    try:
        stmt = (
            sqlite_insert(StopwordRecord)
            .values(user_id=user_id, word=word.strip().lower())
            .on_conflict_do_nothing(index_elements=["user_id", "word"])
        )
        await session.execute(stmt)
        await session.commit()
        return True
    except Exception as exc:
        await session.rollback()
        logger.error("Error adding stopword for user %d: %s", user_id, exc, exc_info=True)
        return False