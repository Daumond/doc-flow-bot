from typing import Optional, Union
from aiogram import Bot
from aiogram.types import Message, CallbackQuery
from loguru import logger

class Notifier:
    def __init__(self, bot: Bot):
        self.bot = bot

    async def notify_user(
        self,
        user_id: Union[int, str],
        text: str,
        reply_markup=None
    ) -> bool:
        """Send a notification to a specific user"""
        try:
            await self.bot.send_message(
                chat_id=user_id,
                text=text,
                reply_markup=reply_markup
            )
            return True
        except Exception as e:
            logger.error(f"Failed to send notification to {user_id}: {e}")
            return False

    async def notify_agent_application_returned(
        self,
        agent_id: int,
        app_id: int,
        comment: str
    ) -> bool:
        """Notify agent that their application was returned"""
        text = (
            f"⚠️ *Заявка #{app_id} возвращена на доработку*\n\n"
            f"*Комментарий РОПа:* {comment}\n\n"
            "Для продолжения работы с заявкой нажмите /my_applications"
        )
        return await self.notify_user(agent_id, text)

    async def notify_agent_task_assigned(
        self,
        agent_id: int,
        app_id: int,
        task_text: str,
        lawyer_name: str
    ) -> bool:
        """Notify agent about a new task from lawyer"""
        text = (
            f"📋 *Новая задача по заявке #{app_id}*\n\n"
            f"*От юриста:* {lawyer_name}\n"
            f"*Задача:* {task_text}\n\n"
            "Для загрузки дополнительных документов нажмите /my_applications"
        )
        return await self.notify_user(agent_id, text)

    async def notify_application_approved(
        self,
        agent_id: int,
        app_id: int
    ) -> bool:
        """Notify agent that their application was approved"""
        text = (
            f"✅ *Заявка #{app_id} одобрена*\n\n"
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
        text = (
            f"🏁 *Сделка по заявке #{app_id} закрыта*\n\n"
            "Спасибо за работу! Если у вас есть вопросы, обратитесь к курирующему юристу."
        )
        return await self.notify_user(agent_id, text)
