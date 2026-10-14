import logging
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database.models.user import User

logger: logging.Logger = logging.getLogger("app.repository.users")


async def get_or_create_user(
    session: AsyncSession,
    telegram_id: int,
    username: Optional[str] = None,
    first_name: Optional[str] = None,
) -> User:
    try:
        query = select(User).where(User.telegram_id == telegram_id)
        result = await session.execute(query)
        user: Optional[User] = result.scalar_one_or_none()

        if user is None:
            user = User(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                is_active=True,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            logger.info("New user registered: %s (id: %d)", username, telegram_id)
        else:
            updated: bool = False
            if user.username != username:
                user.username = username
                updated = True
            if user.first_name != first_name:
                user.first_name = first_name
                updated = True
            if updated:
                await session.commit()
                await session.refresh(user)

        return user
    except Exception as exc:
        await session.rollback()
        logger.error("Error in get_or_create_user for id %d: %s", telegram_id, exc, exc_info=True)
        raise exc


async def get_user_by_id(session: AsyncSession, telegram_id: int) -> Optional[User]:
    try:
        query = select(User).where(User.telegram_id == telegram_id)
        result = await session.execute(query)
        return result.scalar_one_or_none()
    except Exception as exc:
        logger.error("Error fetching user %d: %s", telegram_id, exc, exc_info=True)
        raise exc