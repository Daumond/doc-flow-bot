from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.orm import joinedload
import datetime

from app.db.models import Application, ApplicationStatus, User, Task
from app.db.repository import session_scope
from app.services.notifier import Notifier
from app.config.logging_config import get_logger

# Initialize logger
logger = get_logger(__name__)

router = Router(name="lawyer")

class LawyerStates(StatesGroup):
    task_text = State()

def _lawyer_actions_kb(app_id: int, yandex_public_url: str):
    """Create inline keyboard for lawyer actions"""
    logger.debug(f"Creating actions keyboard for app {app_id}")
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    if yandex_public_url:
        kb.button(text="📁 Яндекс.Диск", url=yandex_public_url)
    kb.button(text="📝 Поставить задачу", callback_data=f"lawyer_task_{app_id}")
    kb.button(text="✅ Закрыть сделку", callback_data=f"lawyer_close_{app_id}")
    kb.adjust(1)
    return kb.as_markup()

@router.message(F.text == "/lawyer")
async def list_for_lawyer(message: Message):
    """Show applications needing lawyer review"""
    logger.info(f"Lawyer {message.from_user.id} requested review list")
    try:
        with session_scope() as s:
            apps = s.query(Application).filter(
                Application.status == ApplicationStatus.to_lawyer
            ).options(joinedload(Application.agent)).all()
            
            if not apps:
                logger.info("No applications for review")
                return await message.answer("Нет заявок на проверке.")
            
            for app in apps:
                try:
                    text = (f"📋 *Заявка #{app.id}*\n"
                            f"Тип: {app.deal_type}\n"
                            f"Адрес: {app.address}\n"
                            f"Агент: {app.agent.full_name if app.agent else 'Не указан'}")
                    yandex_link = getattr(app, 'yandex_public_url', None)
                    await message.answer(text, reply_markup=_lawyer_actions_kb(app.id, yandex_link))
                except Exception as e:
                    logger.error(f"Error showing app {app.id}: {e}")
    except Exception as e:
        logger.error(f"Error in list_for_lawyer: {e}", exc_info=True)
        await message.answer("Ошибка при загрузке заявок.")

@router.callback_query(F.data.startswith("lawyer_task_"))
async def lawyer_task(cb: CallbackQuery, state: FSMContext):
    """Start creating a task"""
    app_id = int(cb.data.split("_")[-1])
    logger.info(f"Lawyer {cb.from_user.id} creating task for app {app_id}")
    try:
        with session_scope() as s:
            if not s.query(Application).get(app_id):
                logger.warning(f"App {app_id} not found")
                return await cb.answer("Заявка не найдена", show_alert=True)
            
            await state.update_data(task_app_id=app_id)
            await state.set_state(LawyerStates.task_text)
            await cb.message.answer("Введите текст задачи агенту:")
            await cb.answer()
    except Exception as e:
        logger.error(f"Error in lawyer_task: {e}", exc_info=True)
        await cb.answer("Ошибка. Попробуйте снова.", show_alert=True)

@router.message(LawyerStates.task_text)
async def lawyer_task_text(message: Message, state: FSMContext, notifier: Notifier):
    """Save task and notify agent"""
    logger.info(f"Processing task from lawyer {message.from_user.id}")
    try:
        data = await state.get_data()
        app_id = data.get("task_app_id")
        task_text = message.text
        
        with session_scope() as s:
            # Находим заявку
            app = s.query(Application).get(app_id)
            if not app:
                logger.error(f"App {app_id} not found")
                await message.answer("Ошибка: заявка не найдена")
                await state.clear()
                return
                
            # Находим текущего пользователя (юриста)
            lawyer = s.query(User).filter(User.telegram_id == str(message.from_user.id)).first()
            if not lawyer:
                logger.error(f"Lawyer {message.from_user.id} not found")
                await message.answer("Ошибка: пользователь не найден")
                await state.clear()
                return
                
            # Обновляем статус заявки
            app.status = ApplicationStatus.lawyer_task
            app.lawyer_id = lawyer.id
            
            # Создаем задачу
            task = Task(
                application_id=app_id,
                author_id=lawyer.id,
                assignee_id=app.agent_id,
                text=task_text,
                status="open"
            )
            s.add(task)
            
            # Отправляем уведомление агенту
            if app.agent_id:
                # Get the agent to access their telegram_id
                agent = s.query(User).filter(User.id == app.agent_id).first()
                if agent and agent.telegram_id:
                    await notifier.notify_agent_task_assigned(
                        agent_id=agent.telegram_id,  # Use telegram_id instead of internal ID
                        app_id=app_id,
                        task_text=task_text
                    )
                    logger.info(f"Notified agent {agent.telegram_id}")
        
        await message.answer(f"✅ Задача агенту сохранена: {task_text}")
        await state.clear()
    except Exception as e:
        logger.error(f"Error in lawyer_task_text: {e}", exc_info=True)
        await message.answer("Ошибка при создании задачи.")

@router.callback_query(F.data.startswith("lawyer_close_"))
async def lawyer_close(cb: CallbackQuery, notifier: Notifier):
    """Close the deal"""
    app_id = int(cb.data.split("_")[-1])
    logger.info(f"Closing deal for app {app_id}")
    try:
        with session_scope() as s:
            app = s.query(Application).get(app_id)
            if app:
                app.status = ApplicationStatus.closed
                
                # Отправляем уведомление агенту
                if app.agent_id:
                    # Get the agent to access their telegram_id
                    agent = s.query(User).filter(User.id == app.agent_id).first()
                    if agent and agent.telegram_id:
                        await notifier.notify_application_closed(agent.telegram_id, app_id)
                        logger.info(f"Notified agent {agent.telegram_id}")
        
        await cb.message.answer("✅ Сделка закрыта")
        await cb.answer()
    except Exception as e:
        logger.error(f"Error in lawyer_close: {e}", exc_info=True)
        await cb.answer("Ошибка при закрытии сделки.", show_alert=True)
