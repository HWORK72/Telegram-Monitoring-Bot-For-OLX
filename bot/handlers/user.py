import logging
import time
from typing import List, Optional
from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from database.connection import async_session_factory
from database.models.link import MonitoredLink
from database.repository import (
    bulk_save_offers,
    count_seen_offers_for_link,
    count_user_links,
    create_link,
    delete_link,
    get_link_by_id,
    get_offer_by_olx_id,
    get_or_create_user,
    get_user_links_paginated,
    toggle_link_status,
    update_offer_phone,
)
from bot.keyboards.inline import (
    cancel_keyboard,
    link_control_keyboard,
    links_pagination_keyboard,
    main_menu_keyboard,
)
from bot.states.link_state import AddLinkState
from parser.client import OLXClient
from parser.normalizer import normalize_url
from parser.schemas import OfferDTO

logger: logging.Logger = logging.getLogger("app.bot.handlers")
router: Router = Router()


@router.message(CommandStart())
async def handle_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    async with async_session_factory() as session:
        await get_or_create_user(
            session=session,
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
        )
        user_links_count: int = await count_user_links(session, message.from_user.id)
        if user_links_count == 0:
            await create_link(
                session=session,
                user_id=message.from_user.id,
                title="🇷🇴 Romania Global Feed",
                url="https://www.olx.ro/oferte/?search%5Border%5D=created_at:desc",
            )

    greeting: str = (
        f"👋 Hello, <b>{message.from_user.first_name}</b>!\n\n"
        f"🤖 I am your high-performance 24/7 OLX monitoring assistant.\n"
        f"I continuously monitor your target searches and deliver immediate notifications "
        f"whenever a new listing appears."
    )
    await message.answer(greeting, reply_markup=main_menu_keyboard(), parse_mode="HTML")


@router.callback_query(F.data == "menu:main")
async def handle_menu_main(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(
        "🎛 <b>Main Control Panel:</b>",
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "action:cancel")
async def handle_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(
        "❌ Action canceled.",
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "menu:add_link")
async def handle_add_link_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AddLinkState.waiting_for_url)
    prompt: str = (
        "🔗 <b>Send me the OLX search URL:</b>\n\n"
        "Go to OLX, configure your desired filters (price range, 'newest first', city, condition) "
        "and copy the full page link here."
    )
    await callback.message.edit_text(prompt, reply_markup=cancel_keyboard(), parse_mode="HTML")
    await callback.answer()


@router.message(AddLinkState.waiting_for_url)
async def process_link_url(message: Message, state: FSMContext) -> None:
    clean_url: Optional[str] = normalize_url(message.text or "")
    if not clean_url:
        await message.answer(
            "⚠️ <b>Invalid URL!</b> Please provide a valid link from a supported OLX domain.",
            reply_markup=cancel_keyboard(),
            parse_mode="HTML",
        )
        return

    await state.update_data(url=clean_url)
    await state.set_state(AddLinkState.waiting_for_title)
    await message.answer(
        "🏷 <b>Enter a memorable name/tag for this search:</b>\n"
        "<i>(e.g., 'iPhone 15 Pro Warsaw' or 'MacBook M3 Cheap')</i>",
        reply_markup=cancel_keyboard(),
        parse_mode="HTML",
    )


@router.message(AddLinkState.waiting_for_title)
async def process_link_title(message: Message, state: FSMContext) -> None:
    title: str = (message.text or "").strip()
    if not title or len(title) > 100:
        await message.answer("⚠️ Title must be between 1 and 100 characters. Try again:")
        return

    data = await state.get_data()
    url: str = data["url"]
    await state.clear()

    status_msg = await message.answer("⏳ <i>Validating search and indexing existing listings...</i>", parse_mode="HTML")

    client = OLXClient()
    initial_offers: List[OfferDTO] = await client.get_offers(url)
    await client.close()

    async with async_session_factory() as session:
        link = await create_link(
            session=session,
            user_id=message.from_user.id,
            title=title,
            url=url,
        )

        initial_count = 0
        if initial_offers:
            payload = [
                {
                    "olx_offer_id": item.olx_offer_id,
                    "title": item.title,
                    "price": item.price,
                    "url": item.url,
                    "published_at": item.published_at,
                }
                for item in initial_offers
            ]
            initial_count = await bulk_save_offers(session=session, link_id=link.id, offers_data=payload)

    success_text: str = (
        f"✅ <b>Monitor Activated Successfully!</b>\n\n"
        f"🏷 <b>Tag:</b> {title}\n"
        f"📦 <b>Initial Baseline Indexed:</b> {initial_count} items\n"
        f"⏱ <b>Interval:</b> Checked every ~60 seconds\n\n"
        f"You will now receive notifications strictly for newly published listings."
    )
    await status_msg.edit_text(success_text, reply_markup=main_menu_keyboard(), parse_mode="HTML")


@router.callback_query(F.data.startswith("menu:list_links:"))
async def handle_list_links(callback: CallbackQuery) -> None:
    page: int = int(callback.data.split(":")[2])
    page_size: int = 5
    offset: int = page * page_size

    async with async_session_factory() as session:
        links: List[MonitoredLink] = await get_user_links_paginated(
            session=session,
            user_id=callback.from_user.id,
            limit=page_size,
            offset=offset,
        )
        total_count: int = await count_user_links(session=session, user_id=callback.from_user.id)

    if not links and page == 0:
        try:
            await callback.message.edit_text(
                "📋 <b>You have no active monitors.</b>\nClick below to add your first search.",
                reply_markup=main_menu_keyboard(),
                parse_mode="HTML",
            )
        except Exception:
            pass
        await callback.answer()
        return

    text: str = f"📋 <b>Your Monitored Searches (Page {page + 1}):</b>\nTotal: {total_count}"
    try:
        await callback.message.edit_text(
            text,
            reply_markup=links_pagination_keyboard(links, page, total_count, page_size),
            parse_mode="HTML",
        )
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data.startswith("link:view:"))
async def handle_view_link(callback: CallbackQuery) -> None:
    parts = callback.data.split(":")
    link_id: int = int(parts[2])
    page: int = int(parts[3])

    async with async_session_factory() as session:
        link: Optional[MonitoredLink] = await get_link_by_id(session, link_id, callback.from_user.id)
        if not link:
            await callback.answer("Link not found.", show_alert=True)
            return
        indexed_count: int = await count_seen_offers_for_link(session, link_id)

    status_str: str = "🟢 Active (Listening)" if link.is_active else "⏸️ Paused"
    last_check_str: str = link.last_check_at.strftime("%Y-%m-%d %H:%M:%S UTC") if link.last_check_at else "Never"

    details: str = (
        f"🏷 <b>Title:</b> {link.title}\n"
        f"📊 <b>Status:</b> {status_str}\n"
        f"🕒 <b>Last Check:</b> {last_check_str}\n"
        f"📦 <b>Indexed Offers in DB:</b> {indexed_count}\n"
        f"🔗 <b>Target URL:</b> <a href='{link.url}'>Open OLX Search</a>"
    )
    await callback.message.edit_text(
        details,
        reply_markup=link_control_keyboard(link_id, link.is_active, page),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("link:toggle:"))
async def handle_toggle_link(callback: CallbackQuery) -> None:
    parts = callback.data.split(":")
    link_id: int = int(parts[2])
    page: int = int(parts[3])

    async with async_session_factory() as session:
        new_status = await toggle_link_status(session, link_id, callback.from_user.id)

    if new_status is None:
        await callback.answer("Error updating link.", show_alert=True)
        return

    status_word = "resumed" if new_status else "paused"
    await callback.answer(f"Monitor {status_word}!")

    fake_cb = CallbackQuery(
        id=callback.id,
        from_user=callback.from_user,
        chat_instance=callback.chat_instance,
        message=callback.message,
        data=f"link:view:{link_id}:{page}",
    )
    await handle_view_link(fake_cb)


@router.callback_query(F.data.startswith("link:delete:"))
async def handle_delete_link(callback: CallbackQuery) -> None:
    parts = callback.data.split(":")
    link_id: int = int(parts[2])
    page: int = int(parts[3])

    async with async_session_factory() as session:
        await delete_link(session, link_id, callback.from_user.id)

    await callback.answer("Monitor deleted.")

    fake_cb = CallbackQuery(
        id=callback.id,
        from_user=callback.from_user,
        chat_instance=callback.chat_instance,
        message=callback.message,
        data=f"menu:list_links:{page}",
    )
    await handle_list_links(fake_cb)


@router.callback_query(F.data == "menu:status")
async def handle_status(callback: CallbackQuery) -> None:
    async with async_session_factory() as session:
        total_links = await count_user_links(session, callback.from_user.id)

    text = (
        f"⚙️ <b>System Status & Metrics:</b>\n\n"
        f"🤖 <b>Bot Engine:</b> Aiogram 3.x (Async)\n"
        f"🗄 <b>Database:</b> PostgreSQL 16 (Docker Pool Active)\n"
        f"🔍 <b>Scraping Engine:</b> curl_cffi Chrome Fingerprint\n"
        f"📊 <b>Your Active Links:</b> {total_links}\n"
        f"⏱ <b>Polling Frequency:</b> Every ~60 seconds"
    )
    await callback.message.edit_text(text, reply_markup=main_menu_keyboard(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("phone:reveal:"))
async def handle_reveal_phone(callback: CallbackQuery) -> None:
    parts = callback.data.split(":")
    offer_id = parts[2]

    async with async_session_factory() as session:
        offer = await get_offer_by_olx_id(session, offer_id)

    if not offer:
        await callback.answer("Offer not found in records.", show_alert=True)
        return

    phone: Optional[str] = getattr(offer, "phone", None)

    if not phone:
        client = OLXClient()
        phone = await client.fetch_phone_number(offer_id, offer.url)
        await client.close()

        if phone:
            async with async_session_factory() as session:
                await update_offer_phone(session, offer_id, phone)

    if phone:
        response_text = (
            f"📞 <b>Phone Number for:</b>\n"
            f"<i>{offer.title}</i>\n\n"
            f"👉 <code>{phone}</code> <i>(Tap to copy)</i>"
        )
        await callback.message.reply(response_text, parse_mode="HTML")
        await callback.answer("Phone sent to chat!")
        try:
            clean_digits = re.sub(r"[^\d+]", "", phone)
            updated_keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text=f"📞 {phone}", url=f"tel:{clean_digits}")],
                    [InlineKeyboardButton(text="🔗 Open on OLX", url=offer.url)],
                ]
            )
            await callback.message.edit_reply_markup(reply_markup=updated_keyboard)
        except Exception:
            pass
    else:
        client = OLXClient()
        is_cooldown = time.time() < client.phone_cooldown_until
        await client.close()
        if is_cooldown:
            await callback.answer("⚠️ OLX hourly limit reached on IP. Please click 'Open on OLX'.", show_alert=True)
        else:
            await callback.answer("ℹ️ Seller hides phone number (In-app messages only).", show_alert=True)