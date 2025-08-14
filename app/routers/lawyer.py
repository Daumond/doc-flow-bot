from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.orm import joinedload

from app.db.models import Application, ApplicationStatus, User, Task
from app.db.repository import session_scope
from app.services.notifier import Notifier

router = Router(name="lawyer")

class LawyerStates(StatesGroup):
    task_text = State()

def _lawyer_actions_kb(app_id: int):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    
    # Add Yandex.Disk button with direct URL if available
    with session_scope() as s:
        app = s.get(Application, app_id)
        if app and app.yandex_public_url:
            kb.button(text="📁 Яндекс.Диск", url=app.yandex_public_url)
    
    # Add other action buttons
    kb.button(text="📝 Поставить задачу", callback_data=f"lawyer_task_{app_id}")
    kb.button(text="✅ Закрыть сделку", callback_data=f"lawyer_close_{app_id}")
    
    kb.adjust(1)
    return kb.as_markup()

@router.message(F.text == "/lawyer")
async def list_for_lawyer(message: Message):
    with (session_scope() as s):
        apps = s.query(Application).options(joinedload(Application.agent)
                                            ).filter(Application.status == ApplicationStatus.to_lawyer).all()

        if not apps:
            return await message.answer("Нет заявок на проверку.")

        messages = []
        for app in apps:
            message_data = {
                'text': (f"Заявка #{app.id}\n"
                        f"Тип: {app.deal_type}\n"
                        f"Адрес: {app.address}\n"
                        f"Сотрудник: {app.agent_name}"),
                'reply_markup': _lawyer_actions_kb(app.id)
            }
            messages.append(message_data)

    # Now send all messages outside the session
    for msg in messages:
        await message.answer(text=msg['text'], reply_markup=msg['reply_markup'])


@router.callback_query(F.data.startswith("lawyer_task_"))
async def lawyer_task(cb: CallbackQuery, state: FSMContext):
    app_id = int(cb.data.split("_")[-1])
    await state.update_data(task_app_id=app_id)
    await cb.message.answer("Введите текст задачи агенту:")
    await state.set_state(LawyerStates.task_text)
    await cb.answer()

@router.message(LawyerStates.task_text)
async def lawyer_task_text(message: Message, state: FSMContext, notifier: Notifier):
    data = await state.get_data()
    app_id = data.get("task_app_id")
    task_text = message.text
    
    with session_scope() as s:
        # Находим заявку
        app = s.query(Application).get(app_id)
        if not app:
            await message.answer("Ошибка: заявка не найдена")
            await state.clear()
            return
            
        # Находим текущего пользователя (юриста)
        lawyer = s.query(User).filter(User.telegram_id == str(message.from_user.id)).first()
        if not lawyer:
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
                    task_text=task_text,
                    lawyer_name=lawyer.full_name or "Юрист"
                )
    
    await message.answer(f"✅ Задача агенту сохранена: {task_text}")
    await state.clear()

@router.callback_query(F.data.startswith("lawyer_close_"))
async def lawyer_close(cb: CallbackQuery, notifier: Notifier):
    app_id = int(cb.data.split("_")[-1])
    
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
    
    await cb.message.answer("✅ Сделка закрыта")
    await cb.answer()
