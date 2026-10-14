import asyncio
import logging
import random
from typing import List, Set
from aiogram import Bot
from bot.keyboards.inline import offer_notification_keyboard
from core.config import get_settings
from database.connection import async_session_factory
from database.models.link import MonitoredLink
from database.repository import (
    bulk_save_offers,
    get_all_active_links,
    get_existing_offer_ids,
    get_user_blacklist,
    get_user_stopwords,
    update_last_check_timestamp,
)
from parser.client import OLXClient
from parser.schemas import OfferDTO
from scheduler.balancer import balance_and_filter_leads

logger: logging.Logger = logging.getLogger("app.scheduler.poller")
settings = get_settings()


class PollerService:
    def __init__(self, bot: Bot) -> None:
        self.bot: Bot = bot
        self.client: OLXClient = OLXClient()
        self._is_running: bool = False
        self._semaphore: asyncio.Semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_CHECKS)

    async def start(self) -> None:
        self._is_running = True
        logger.info(
            "Background 24/7 OLX Poller started with concurrency limit: %d",
            settings.MAX_CONCURRENT_CHECKS,
        )
        while self._is_running:
            try:
                await self._poll_cycle()
            except Exception as exc:
                logger.error("Unhandled error during polling cycle: %s", exc, exc_info=True)

            await self.client.close()

            jitter: int = random.randint(-settings.POLL_JITTER_SECONDS, settings.POLL_JITTER_SECONDS)
            sleep_duration: int = max(10, settings.POLL_INTERVAL_SECONDS + jitter)
            logger.info("Cycle completed. Next check in %d seconds.", sleep_duration)
            await asyncio.sleep(sleep_duration)

    async def stop(self) -> None:
        self._is_running = False
        await self.client.close()
        logger.info("Background OLX Poller stopped.")

    async def _poll_cycle(self) -> None:
        async with async_session_factory() as session:
            active_links: List[MonitoredLink] = await get_all_active_links(session)

        if not active_links:
            logger.info("No active links to monitor at the moment.")
            return

        logger.info("Processing %d active links concurrently...", len(active_links))

        tasks = [self._bounded_process_link(link) for link in active_links]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _bounded_process_link(self, link: MonitoredLink) -> None:
        if not self._is_running:
            return
        async with self._semaphore:
            await self._process_link(link)

    async def _process_link(self, link: MonitoredLink) -> None:
        try:
            logger.info("Checking link #%d ('%s')...", link.id, link.title)
            offers: List[OfferDTO] = await self.client.get_offers(link.url)
            if not offers:
                return

            candidate_ids: List[str] = [item.olx_offer_id for item in offers]

            async with async_session_factory() as session:
                existing_ids: Set[str] = await get_existing_offer_ids(
                    session=session,
                    link_id=link.id,
                    candidate_ids=candidate_ids,
                )

                new_offers: List[OfferDTO] = [
                    item for item in offers if item.olx_offer_id not in existing_ids
                ]

                if new_offers:
                    logger.info("Found %d unseen offers for link #%d", len(new_offers), link.id)
                    save_payload = [
                        {
                            "olx_offer_id": item.olx_offer_id,
                            "title": item.title,
                            "price": item.price,
                            "url": item.url,
                            "published_at": item.published_at,
                        }
                        for item in new_offers
                    ]
                    await bulk_save_offers(session=session, link_id=link.id, offers_data=save_payload)

                    valid_fresh_offers: List[OfferDTO] = []
                    for item in new_offers:
                        if settings.IGNORE_PROMOTED_OFFERS and item.is_promoted:
                            logger.info("Filtered out PROMOTED (TOP) offer #%s: %s", item.olx_offer_id, item.title)
                            continue
                        if settings.IGNORE_BUMPED_OFFERS and item.is_bumped:
                            logger.info("Filtered out BUMPED (refresh delta) offer #%s: %s", item.olx_offer_id, item.title)
                            continue
                        if item.is_too_old:
                            logger.info("Filtered out STALE (older than %d min) offer #%s: %s", settings.MAX_OFFER_AGE_MINUTES, item.olx_offer_id, item.title)
                            continue
                        valid_fresh_offers.append(item)

                    if valid_fresh_offers:
                        user_blacklist: Set[str] = await get_user_blacklist(session, link.user_id)
                        user_stopwords: Set[str] = await get_user_stopwords(session, link.user_id)

                        balanced_leads, summary_card = balance_and_filter_leads(
                            offers=valid_fresh_offers,
                            batch_limit=settings.BATCH_OUTPUT_LIMIT,
                            max_per_category=settings.MAX_PER_CATEGORY_PER_BATCH,
                            blacklist=user_blacklist,
                            stopwords=user_stopwords,
                        )

                        if balanced_leads:
                            try:
                                await self.bot.send_message(
                                    chat_id=link.user_id,
                                    text=summary_card,
                                    parse_mode="HTML",
                                )
                            except Exception as card_exc:
                                logger.error("Error sending summary stats card: %s", card_exc)

                            await self._notify_user(link.user_id, link.title, balanced_leads)
                    else:
                        logger.info("All %d unseen items were filtered as bumped, promoted, or stale.", len(new_offers))

                await update_last_check_timestamp(session, link.id)

        except Exception as exc:
            logger.error("Error processing link #%d: %s", link.id, exc, exc_info=True)

    async def _notify_user(self, user_id: int, link_title: str, offers: List[OfferDTO]) -> None:
        for item in offers:
            caption: str = (
                f"🚨 <b>New OLX Listing Found!</b>\n\n"
                f"🏷 <b>Filter:</b> {link_title}\n"
                f"📌 <b>Title:</b> {item.title}\n"
                f"💰 <b>Price:</b> {item.price or 'Not specified'}\n"
                f"📍 <b>Location:</b> {item.location or 'Not specified'}"
            )

            is_valid_photo = (
                item.photo_url
                and isinstance(item.photo_url, str)
                and (item.photo_url.startswith("http://") or item.photo_url.startswith("https://"))
            )

            keyboard = offer_notification_keyboard(item.olx_offer_id, item.url)

            try:
                if is_valid_photo:
                    try:
                        await self.bot.send_photo(
                            chat_id=user_id,
                            photo=item.photo_url,
                            caption=caption,
                            reply_markup=keyboard,
                            parse_mode="HTML",
                        )
                    except Exception as photo_exc:
                        logger.warning(
                            "Telegram failed to download photo for offer %s (%s). Falling back to text message.",
                            item.olx_offer_id,
                            photo_exc,
                        )
                        await self.bot.send_message(
                            chat_id=user_id,
                            text=caption,
                            reply_markup=keyboard,
                            parse_mode="HTML",
                            disable_web_page_preview=False,
                        )
                else:
                    await self.bot.send_message(
                        chat_id=user_id,
                        text=caption,
                        reply_markup=keyboard,
                        parse_mode="HTML",
                        disable_web_page_preview=False,
                    )
                await asyncio.sleep(0.3)
            except Exception as exc:
                if "chat not found" in str(exc).lower() or "blocked" in str(exc).lower():
                    logger.warning("User %d is unreachable in Telegram (chat not found or bot blocked).", user_id)
                    break
                logger.error("Failed to send notification for offer %s to user %d: %s", item.olx_offer_id, user_id, exc)