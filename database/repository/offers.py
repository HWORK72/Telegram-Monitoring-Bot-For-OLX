import logging
from typing import Dict, List, Optional, Set
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from database.models.offer import SeenOffer

logger: logging.Logger = logging.getLogger("app.repository.offers")


async def get_existing_offer_ids(
    session: AsyncSession,
    link_id: int,
    candidate_ids: List[str],
) -> Set[str]:
    if not candidate_ids:
        return set()
    try:
        query = select(SeenOffer.olx_offer_id).where(
            SeenOffer.link_id == link_id,
            SeenOffer.olx_offer_id.in_(candidate_ids),
        )
        result = await session.execute(query)
        existing: Set[str] = set(result.scalars().all())
        return existing
    except Exception as exc:
        logger.error("Error fetching existing offer IDs for link %d: %s", link_id, exc, exc_info=True)
        raise exc


async def get_offer_by_olx_id(
    session: AsyncSession,
    olx_offer_id: str,
) -> Optional[SeenOffer]:
    try:
        query = select(SeenOffer).where(SeenOffer.olx_offer_id == olx_offer_id).limit(1)
        result = await session.execute(query)
        return result.scalar_one_or_none()
    except Exception as exc:
        logger.error("Error fetching offer %s by OLX ID: %s", olx_offer_id, exc, exc_info=True)
        raise exc


async def update_offer_phone(
    session: AsyncSession,
    olx_offer_id: str,
    phone: str,
) -> None:
    try:
        query = (
            update(SeenOffer)
            .where(SeenOffer.olx_offer_id == olx_offer_id)
            .values(phone=phone)
        )
        await session.execute(query)
        await session.commit()
        logger.info("Cached phone number for offer %s in DB", olx_offer_id)
    except Exception as exc:
        await session.rollback()
        logger.error("Error caching phone for offer %s: %s", olx_offer_id, exc, exc_info=True)
        raise exc


async def bulk_save_offers(
    session: AsyncSession,
    link_id: int,
    offers_data: List[Dict[str, str]],
) -> int:
    if not offers_data:
        return 0
    try:
        records: List[Dict[str, object]] = []
        for item in offers_data:
            records.append(
                {
                    "link_id": link_id,
                    "olx_offer_id": str(item["olx_offer_id"]),
                    "title": item["title"],
                    "price": item.get("price"),
                    "url": item["url"],
                    "published_at": item.get("published_at"),
                }
            )

        statement = (
            pg_insert(SeenOffer)
            .values(records)
            .on_conflict_do_nothing(
                index_elements=["link_id", "olx_offer_id"]
            )
        )
        result = await session.execute(statement)
        await session.commit()
        inserted_count: int = result.rowcount or 0
        logger.info("Saved %d new offers for link %d", inserted_count, link_id)
        return inserted_count
    except Exception as exc:
        await session.rollback()
        logger.error("Error bulk saving offers for link %d: %s", link_id, exc, exc_info=True)
        raise exc


async def count_seen_offers_for_link(session: AsyncSession, link_id: int) -> int:
    try:
        query = select(func.count(SeenOffer.id)).where(SeenOffer.link_id == link_id)
        result = await session.execute(query)
        total: int = result.scalar() or 0
        return total
    except Exception as exc:
        logger.error("Error counting seen offers for link %d: %s", link_id, exc, exc_info=True)
        raise exc