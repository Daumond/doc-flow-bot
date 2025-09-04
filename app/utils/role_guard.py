from aiogram import BaseMiddleware
from typing import Callable, Dict, Any, Awaitable
from app.db.repository import session_scope
from app.db.models import User, UserRole
from app.config.logging_config import get_logger

logger = get_logger(__name__)


class AccessGuard(BaseMiddleware):
    async def __call__(self, handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]], event, data: Dict[str, Any]):
        tg_id = str(getattr(event.from_user, "id", None))
        if not tg_id:
            return  # нет пользователя — пропускаем или игнорируем
        with session_scope() as s:
            user = s.query(User).filter(User.telegram_id == tg_id).first()
            # Регистрацию пропускаем
            txt = getattr(event, "text", "") or ""
            if txt.startswith("/start"):
                return await handler(event, data)
            # Блокируем всё остальное, если нет прав
            if not user or not user.is_active or not user.is_approved:
                await event.answer("Доступ ограничен. Обратитесь к РОПу для подтверждения регистрации.")
                logger.warning(f"Access denied for user {tg_id} in {handler}")
                return
        return await handler(event, data)


class RoleMiddleware(BaseMiddleware):
    def __init__(self, allowed_roles: list[UserRole]):
        super().__init__()
        self.allowed_roles = allowed_roles

    async def __call__(
        self,
        handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
        event,
        data: Dict[str, Any]
    ):
        tg_id = str(getattr(event.from_user, "id", None))
        if not tg_id:
            return

        with session_scope() as s:
            user = s.query(User).filter(User.telegram_id == tg_id).first()

            if not user:
                if hasattr(event, "answer"):
                    await event.answer("⛔ Вы не зарегистрированы.")
                return

            if user.role not in self.allowed_roles:
                if hasattr(event, "answer"):
                    await event.answer("⛔ У вас нет доступа к этой команде.")
                    logger.warning(f"Higher access denied for user {tg_id} in {handler}")
                return

        # передаем user в data, чтобы хендлер мог его использовать
        data["user"] = user
        return await handler(event, data)