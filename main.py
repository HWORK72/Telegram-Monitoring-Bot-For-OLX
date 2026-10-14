import asyncio
import logging
from typing import Optional
from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.fsm.storage.memory import MemoryStorage
from core.config import get_settings
from core.logger import setup_logging
from database.connection import engine, init_database
from bot.handlers.user import router as user_router
from scheduler.poller import PollerService

logger: logging.Logger = setup_logging()
settings = get_settings()


async def start_application() -> None:
    logger.info("Initializing High-Load OLX Monitor Application...")

    await init_database()

    session: Optional[AiohttpSession] = None
    if settings.PROXY_URL:
        logger.info("Proxy configured: routing Telegram updates through proxy.")
        session = AiohttpSession(proxy=settings.PROXY_URL)
    else:
        logger.info("No proxy configured: running Telegram bot via direct connection.")

    bot: Bot = Bot(token=settings.BOT_TOKEN, session=session)
    dp: Dispatcher = Dispatcher(storage=MemoryStorage())

    dp.include_router(user_router)

    poller: PollerService = PollerService(bot=bot)
    poller_task: asyncio.Task = asyncio.create_task(poller.start())

    try:
        logger.info("Starting Telegram Bot long-polling...")
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    except Exception as exc:
        logger.error("Critical error in bot polling: %s", exc, exc_info=True)
    finally:
        logger.info("Graceful shutdown triggered. Releasing resources...")
        await poller.stop()
        poller_task.cancel()
        try:
            await poller_task
        except asyncio.CancelledError:
            pass
        await bot.session.close()
        await engine.dispose()
        logger.info("Application shutdown completed cleanly.")


if __name__ == "__main__":
    try:
        asyncio.run(start_application())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Process terminated by user.")