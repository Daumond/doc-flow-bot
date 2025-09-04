import asyncio
from aiogram import Bot, Dispatcher
from aiogram.client.bot import DefaultBotProperties
from aiogram.enums import ParseMode

from app.config.config import settings
from app.config.logging_config import get_logger
from app.db.models import UserRole
from app.db.repository import init_db
from app.routers.common import router as common_router
from app.routers.agent import router as agent_router
from app.routers.rop import router as rop_router
from app.routers.lawyer import router as lawyer_router
from app.services.notifier import Notifier
from app.utils.role_guard import AccessGuard, RoleMiddleware

# Initialize logger
logger = get_logger(__name__)

async def main():
    logger.info("Starting DealFlowBot in {} mode", settings.env)
    
    try:
        # Initialize database
        logger.info("Initializing database...")
        init_db()
        
        # Create bot and dispatcher
        logger.info("Creating bot and dispatcher...")
        bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        dp = Dispatcher()
        
        # Initialize notifier
        logger.info("Initializing notifier...")
        notifier = Notifier(bot)
        dp['notifier'] = notifier
        
        # Include routers
        logger.info("Setting up routers...")
        # Базовый middleware для защиты всех хендлеров
        dp.message.middleware(AccessGuard())
        dp.callback_query.middleware(AccessGuard())

        # Роутер для команд РОПа
        rop_router.message.middleware(RoleMiddleware([UserRole.rop]))
        rop_router.callback_query.middleware(RoleMiddleware([UserRole.rop]))

        # Роутер для команд юриста
        lawyer_router.message.middleware(RoleMiddleware([UserRole.lawyer]))
        lawyer_router.callback_query.middleware(RoleMiddleware([UserRole.lawyer]))

        dp.include_router(common_router)
        dp.include_router(agent_router)
        dp.include_router(rop_router)
        dp.include_router(lawyer_router)
        
        logger.info("Starting bot polling...")
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.exception("An error occurred while starting the bot")
        raise
    finally:
        logger.info("Bot has been stopped")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.exception("Unexpected error occurred")
        raise