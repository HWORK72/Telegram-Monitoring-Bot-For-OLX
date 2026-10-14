import logging
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from database.models.link import MonitoredLink

logger: logging.Logger = logging.getLogger("app.repository.links")


async def create_link(
    session: AsyncSession,
    user_id: int,
    title: str,
    url: str,
) -> MonitoredLink:
    try:
        link: MonitoredLink = MonitoredLink(
            user_id=user_id,
            title=title,
            url=url,
            is_active=True,
        )
        session.add(link)
        await session.commit()
        await session.refresh(link)
        logger.info("Link created successfully (id: %d, user: %d)", link.id, user_id)
        return link
    except Exception as exc:
        await session.rollback()
        logger.error("Error creating link for user %d: %s", user_id, exc, exc_info=True)
        raise exc


async def get_link_by_id(
    session: AsyncSession,
    link_id: int,
    user_id: Optional[int] = None,
) -> Optional[MonitoredLink]:
    try:
        query = select(MonitoredLink).where(MonitoredLink.id == link_id)
        if user_id is not None:
            query = query.where(MonitoredLink.user_id == user_id)
        result = await session.execute(query)
        return result.scalar_one_or_none()
    except Exception as exc:
        logger.error("Error fetching link %d: %s", link_id, exc, exc_info=True)
        raise exc


async def get_user_links_paginated(
    session: AsyncSession,
    user_id: int,
    limit: int = 5,
    offset: int = 0,
) -> List[MonitoredLink]:
    try:
        query = (
            select(MonitoredLink)
            .where(MonitoredLink.user_id == user_id)
            .order_by(MonitoredLink.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await session.execute(query)
        return list(result.scalars().all())
    except Exception as exc:
        logger.error("Error fetching paginated links for user %d: %s", user_id, exc, exc_info=True)
        raise exc


async def count_user_links(session: AsyncSession, user_id: int) -> int:
    try:
        query = (
            select(func.count(MonitoredLink.id))
            .where(MonitoredLink.user_id == user_id)
        )
        result = await session.execute(query)
        count: Optional[int] = result.scalar()
        return count or 0
    except Exception as exc:
        logger.error("Error counting links for user %d: %s", user_id, exc, exc_info=True)
        raise exc


async def toggle_link_status(
    session: AsyncSession,
    link_id: int,
    user_id: int,
) -> Optional[bool]:
    try:
        link: Optional[MonitoredLink] = await get_link_by_id(
            session=session,
            link_id=link_id,
            user_id=user_id,
        )
        if link is None:
            return None

        new_status: bool = not link.is_active
        link.is_active = new_status
        await session.commit()
        await session.refresh(link)
        logger.info("Link %d status changed to %s", link_id, new_status)
        return new_status
    except Exception as exc:
        await session.rollback()
        logger.error("Error toggling status for link %d: %s", link_id, exc, exc_info=True)
        raise exc


async def delete_link(session: AsyncSession, link_id: int, user_id: int) -> bool:
    try:
        query = delete(MonitoredLink).where(
            MonitoredLink.id == link_id,
            MonitoredLink.user_id == user_id,
        )
        result = await session.execute(query)
        await session.commit()
        deleted: bool = result.rowcount > 0
        if deleted:
            logger.info("Link %d deleted by user %d", link_id, user_id)
        return deleted
    except Exception as exc:
        await session.rollback()
        logger.error("Error deleting link %d: %s", link_id, exc, exc_info=True)
        raise exc


async def get_all_active_links(session: AsyncSession) -> List[MonitoredLink]:
    try:
        query = (
            select(MonitoredLink)
            .where(MonitoredLink.is_active.is_(True))
            .order_by(MonitoredLink.id.asc())
        )
        result = await session.execute(query)
        return list(result.scalars().all())
    except Exception as exc:
        logger.error("Error fetching active links: %s", exc, exc_info=True)
        raise exc


async def update_last_check_timestamp(session: AsyncSession, link_id: int) -> None:
    try:
        query = (
            update(MonitoredLink)
            .where(MonitoredLink.id == link_id)
            .values(last_check_at=datetime.now(timezone.utc))
        )
        await session.execute(query)
        await session.commit()
    except Exception as exc:
        await session.rollback()
        logger.error("Error updating timestamp for link %d: %s", link_id, exc, exc_info=True)
        raise exc