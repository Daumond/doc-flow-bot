import asyncio
from aiogram import Bot, Dispatcher
from loguru import logger

from app.config.config import settings
from app.db.repository import init_db
from app.routers.common import router as common_router
from app.routers.agent import router as agent_router
from app.routers.rop import router as rop_router
from app.routers.lawyer import router as lawyer_router
from app.services.notifier import Notifier
from aiogram.client.bot import DefaultBotProperties
from aiogram.enums import ParseMode
from app.services.yandex_disk import YandexDiskClient, YandexDiskSettings
from app.services.document_storage import DocumentStorage
from app.config.yandex_disk import get_yandex_disk_settings


async def main():
    logger.info("Starting DealFlowBot in {} mode", settings.env)
    
    # Initialize database
    init_db()
    
    # Create bot and dispatcher
    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    
    # Initialize notifier
    notifier = Notifier(bot)
    
    # Add notifier to context
    dp['notifier'] = notifier
    
    # Include routers
    dp.include_router(common_router)
    dp.include_router(agent_router)
    dp.include_router(rop_router)
    dp.include_router(lawyer_router)
    
    # Start polling
    await dp.start_polling(bot)


async def on_startup(dp: Dispatcher):
    """Application startup handler"""
    # Initialize Yandex.Disk client
    yadisk_settings = get_yandex_disk_settings()
    yadisk = YandexDiskClient(yadisk_settings)
    dp['yadisk'] = yadisk

    # Initialize document storage
    dp['document_storage'] = DocumentStorage(yadisk)

    # Create base folder if it doesn't exist
    try:
        await yadisk.create_folder("doc-flow-bot")
    except Exception as e:
        logger.error(f"Failed to create Yandex.Disk base folder: {e}")


async def on_shutdown(dp: Dispatcher):
    """Application shutdown handler"""
    # Close Yandex.Disk client
    yadisk = dp.get('yadisk')
    if yadisk:
        await yadisk.close()

    # Close database connections
    await dp.storage.close()
    await dp.storage.wait_closed()
    logger.info("Application shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass