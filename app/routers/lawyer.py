from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from app.db.models import Application, ApplicationStatus
from app.db.repository import session_scope

router = Router(name="lawyer")

@router.message(F.text == "/lawyer")
async def list_for_lawyer(message: Message):
    with session_scope() as s:
        apps = s.query(Application).filter(Application.status == ApplicationStatus.to_lawyer).all()
    if not apps:
        return await message.answer("Нет заявок на проверку.")
    for app in apps:
        await message.answer(
            f"Заявка #{app.id}\nТип: {app.deal_type}\nАдрес: {app.address}\nСотрудник: {app.agent_name}",
            reply_markup=_lawyer_actions_kb(app.id)
        )

def _lawyer_actions_kb(app_id: int):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    kb.button(text="Поставить задачу", callback_data=f"lawyer_task_{app_id}")
    kb.button(text="Закрыть сделку", callback_data=f"lawyer_close_{app_id}")
    kb.adjust(1)
    return kb.as_markup()

@router.callback_query(F.data.startswith("lawyer_task_"))
async def lawyer_task(cb: CallbackQuery, state):
    await cb.message.answer("Введите текст задачи агенту:")
    await state.update_data(task_app_id=int(cb.data.split("_")[-1]))
    await state.set_state("lawyer_task_text")
    await cb.answer()

@router.message(F.state == "lawyer_task_text")
async def lawyer_task_text(message: Message, state):
    data = await state.get_data()
    app_id = data.get("task_app_id")
    task_text = message.text
    with session_scope() as s:
        app = s.query(Application).get(app_id)
        if app:
            app.status = ApplicationStatus.lawyer_task
    await message.answer(f"Задача агенту сохранена: {task_text}")
    await state.clear()

@router.callback_query(F.data.startswith("lawyer_close_"))
async def lawyer_close(cb: CallbackQuery):
    app_id = int(cb.data.split("_")[-1])
    with session_scope() as s:
        app = s.query(Application).get(app_id)
        if app:
            app.status = ApplicationStatus.closed
    await cb.message.answer("Сделка закрыта ✅")
    await cb.answer()
