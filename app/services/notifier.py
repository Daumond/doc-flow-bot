from typing import Optional, Union
from aiogram import Bot
from aiogram.types import Message, CallbackQuery
from app.config.logging_config import get_logger

# Initialize logger
logger = get_logger(__name__)

class Notifier:
    def __init__(self, bot: Bot):
        self.bot = bot
        logger.debug("Notifier service initialized")

    async def notify_user(
        self,
        user_id: Union[int, str],
        text: str,
        reply_markup=None
    ) -> bool:
        """Send a notification to a specific user"""
        logger.debug(f"Sending notification to user {user_id}")
        try:
            await self.bot.send_message(
                chat_id=user_id,
                text=text,
                reply_markup=reply_markup
            )
            logger.debug(f"Successfully sent notification to user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to send notification to {user_id}: {str(e)}")
            return False

    async def notify_rop_application_created(
        self,
        user_id: int,
        agent_name: str,
        app_id: int
    ) -> bool:
        """Notify rop that a new application was created"""
        logger.info(f"Notifying about new ROP application {app_id}")
        text = (
            f"📋 Новая заявка #{app_id}\n\n"
            f"Автор: {agent_name}\n\n"
            f"Просмотреть - /rop\n\n"
        )
        return await self.notify_user(user_id, agent_name, text)

    async def notify_agent_application_returned(
        self,
        agent_id: int,
        app_id: int,
        comment: str
    ) -> bool:
        """Notify agent that their application was returned"""
        logger.info(f"Notifying agent {agent_id} about returned application {app_id}")
        text = (
            f"⚠️ Заявка #{app_id} возвращена на доработку\n\n"
            f"Комментарий РОПа: {comment}\n\n"
            "Для продолжения работы с заявкой нажмите /my_applications"
        )
        return await self.notify_user(agent_id, text)

    async def notify_agent_task_assigned(
        self,
        agent_id: int,
        app_id: int,
        task_text: str
    ) -> bool:
        """Notify agent about a new task from lawyer"""
        logger.info(f"Notifying agent {agent_id} about new task for application {app_id}")
        text = (
            f"📋 Новая задача от юриста по заявке #{app_id}\n\n"
            f"Задача: {task_text}\n\n"
            "Для загрузки дополнительных документов нажмите /my_applications"
        )
        return await self.notify_user(agent_id, text)

    async def notify_application_approved(
        self,
        agent_id: int,
        app_id: int
    ) -> bool:
        """Notify agent that their application was approved"""
        logger.info(f"Notifying agent {agent_id} about approved application {app_id}")
        text = (
            f"✅ Заявка #{app_id} одобрена\n\n"
            "Заявка передана юристу на проверку. "
            "Вы получите уведомление о дальнейших действиях."
        )
        return await self.notify_user(agent_id, text)

    async def notify_application_closed(
        self,
        agent_id: int,
        app_id: int
    ) -> bool:
        """Notify agent that their application was closed"""
        logger.info(f"Notifying agent {agent_id} about closed application {app_id}")
        text = (
            f"🏁 Сделка по заявке #{app_id} закрыта\n\n"
        )
        return await self.notify_user(agent_id, text)
