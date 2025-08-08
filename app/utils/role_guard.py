from aiogram.types import Message
from app.db.models import UserRole


#def require_role(*roles: UserRole):
#   def decorator(handler):
#        async def wrapper(message: Message, *args, **kwargs):
#            user = message.conf.get("user") if hasattr(message, "conf") else None
#            # В MVP роль можно подтягивать из middleware (добавим позже). Здесь – заглушка.
#            if not user or user.role not in roles:
#                return await message.answer("Недостаточно прав для этой команды.")
#            return await handler(message, *args, **kwargs)
#        return wrapper
#    return decorator