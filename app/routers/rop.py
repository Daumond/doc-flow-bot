from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from app.db.models import Application, ApplicationStatus
from app.db.repository import session_scope

router = Router(name="rop")

@router.message(F.text == "/rop")
async def list_for_rop(message: Message):
    # MVP: показываем все CREATED
    with session_scope() as s:
        apps = s.query(Application).filter(Application.status == ApplicationStatus.created).all()
    if not apps:
        return await message.answer("Нет заявок на проверку.")
    for app in apps:
        await message.answer(
            f"Заявка #{app.id}\nТип: {app.deal_type}\nАдрес: {app.address}\nСотрудник: {app.agent_name}",
            reply_markup=_rop_actions_kb(app.id)
        )

def _rop_actions_kb(app_id: int):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    kb.button(text="Одобрить → Юристу", callback_data=f"rop_approve_{app_id}")
    kb.button(text="Вернуть с комментарием", callback_data=f"rop_return_{app_id}")
    kb.adjust(1)
    return kb.as_markup()

@router.callback_query(F.data.startswith("rop_approve_"))
async def rop_approve(cb: CallbackQuery):
    app_id = int(cb.data.split("_")[-1])
    with session_scope() as s:
        app = s.query(Application).get(app_id)
        if app:
            app.status = ApplicationStatus.to_lawyer
    await cb.message.answer("Заявка передана юристу ✅")
    await cb.answer()

@router.callback_query(F.data.startswith("rop_return_"))
async def rop_return(cb: CallbackQuery, state):
    await cb.message.answer("Введите комментарий для возврата:")
    await state.update_data(return_app_id=int(cb.data.split("_")[-1]))
    await state.set_state("rop_return_comment")
    await cb.answer()

@router.message(F.state == "rop_return_comment")
async def rop_return_comment(message: Message, state):
    data = await state.get_data()
    app_id = data.get("return_app_id")
    comment = message.text
    with session_scope() as s:
        app = s.query(Application).get(app_id)
        if app:
            app.status = ApplicationStatus.returned_rop
    await message.answer(f"Заявка возвращена агенту с комментарием: {comment}")
    await state.clear()