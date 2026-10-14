from typing import List
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from database.models.link import MonitoredLink


def main_menu_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="➕ Add New Link", callback_data="menu:add_link")],
        [InlineKeyboardButton(text="📋 My Monitored Links", callback_data="menu:list_links:0")],
        [InlineKeyboardButton(text="📊 Status & Metrics", callback_data="menu:status")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def links_pagination_keyboard(
    links: List[MonitoredLink],
    page: int,
    total_count: int,
    page_size: int = 5,
) -> InlineKeyboardMarkup:
    rows = []
    for link in links:
        status_icon = "🟢" if link.is_active else "⏸️"
        button_text = f"{status_icon} {link.title[:25]}"
        rows.append([InlineKeyboardButton(text=button_text, callback_data=f"link:view:{link.id}:{page}")])

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️ Previous", callback_data=f"menu:list_links:{page - 1}"))
    if (page + 1) * page_size < total_count:
        nav_row.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"menu:list_links:{page + 1}"))

    if nav_row:
        rows.append(nav_row)

    rows.append([InlineKeyboardButton(text="🔙 Back to Main Menu", callback_data="menu:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def link_control_keyboard(link_id: int, is_active: bool, page: int) -> InlineKeyboardMarkup:
    toggle_text = "⏸️ Pause Monitoring" if is_active else "▶️ Resume Monitoring"
    buttons = [
        [InlineKeyboardButton(text=toggle_text, callback_data=f"link:toggle:{link_id}:{page}")],
        [InlineKeyboardButton(text="🗑️ Delete Link", callback_data=f"link:delete:{link_id}:{page}")],
        [InlineKeyboardButton(text="🔙 Back to List", callback_data=f"menu:list_links:{page}")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel", callback_data="action:cancel")]]
    )


def offer_notification_keyboard(offer_id: str, offer_url: str) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="📞 Show Phone Number", callback_data=f"phone:reveal:{offer_id}")],
        [InlineKeyboardButton(text="🔗 Open on OLX", url=offer_url)],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)