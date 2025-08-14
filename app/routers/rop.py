from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.orm import joinedload
from app.db.models import Application, ApplicationStatus, User
from app.db.repository import session_scope
from app.services.notifier import Notifier

router = Router(name="rop")

class ROPStates(StatesGroup):
    waiting_for_return_comment = State()

def _rop_actions_kb(app_id: int):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    kb.button(text="Одобрить → Юристу", callback_data=f"rop_approve_{app_id}")
    kb.button(text="Вернуть с комментарием", callback_data=f"rop_return_{app_id}")
    kb.adjust(1)
    return kb.as_markup()

@router.message(F.text == "/rop")
async def list_for_rop(message: Message):
    # MVP: показываем все CREATED
    with session_scope() as s:
        # Load all applications with their agent relationship
        apps = s.query(Application).options(joinedload(Application.agent))\
                                 .filter(Application.status == ApplicationStatus.created)\
                                 .all()
        
        if not apps:
            return await message.answer("Нет заявок на проверку.")
            
        # Prepare all message data while the session is still open
        messages = []
        for app in apps:
            message_data = {
                'text': (f"Заявка #{app.id}\n"
                        f"Тип: {app.deal_type}\n"
                        f"Адрес: {app.address}\n"
                        f"Сотрудник: {app.agent_name}"),
                'reply_markup': _rop_actions_kb(app.id)
            }
            messages.append(message_data)
    
    # Now send all messages outside the session
    for msg in messages:
        await message.answer(text=msg['text'], reply_markup=msg['reply_markup'])

@router.callback_query(F.data.startswith("rop_approve_"))
async def rop_approve(cb: CallbackQuery, notifier: Notifier):
    app_id = int(cb.data.split("_")[-1])
    agent_id = None
    
    with session_scope() as s:
        # Use joinedload to ensure agent relationship is loaded
        app = s.query(Application).options(joinedload(Application.agent)).get(app_id)
        if app:
            app.status = ApplicationStatus.to_lawyer
            # Get the user who approved the application (current user)
            rop_user = s.query(User).filter(User.telegram_id == str(cb.from_user.id)).first()
            rop_name = rop_user.full_name if rop_user else "РОП"
            app.rop_id = rop_user.id if rop_user else None
            # Get agent_id safely
            agent = s.query(User).filter(User.id == app.agent_id).first()
            if agent and agent.telegram_id:
                agent_id = agent.telegram_id
    
    # Send notification outside the session
    if agent_id:
        await notifier.notify_application_approved(agent_id, app_id)
    
    await cb.message.answer("✅ Заявка передана юристу")
    await cb.answer()

@router.callback_query(F.data.startswith("rop_return_"))
async def rop_return(cb: CallbackQuery, state: FSMContext):
    print(f"[DEBUG] rop_return: Starting, data={cb.data}")
    app_id = int(cb.data.split("_")[-1])
    await state.update_data(return_app_id=app_id)
    await state.set_state(ROPStates.waiting_for_return_comment)
    print(f"[DEBUG] rop_return: State set to 'waiting_for_return_comment', app_id={app_id}")
    await cb.message.answer("Введите комментарий для возврата:")
    await cb.answer()

@router.message(ROPStates.waiting_for_return_comment)
async def rop_return_comment(message: Message, state: FSMContext, notifier: Notifier):
    print("[DEBUG] rop_return_comment: Handler triggered")
    data = await state.get_data()
    app_id = data.get("return_app_id")
    comment = message.text
    print(f"[DEBUG] rop_return_comment: Processing app_id={app_id}, comment={comment}")
    
    if not app_id:
        print("[ERROR] rop_return_comment: No app_id in state data")
        await message.answer("Ошибка: не удалось определить заявку. Пожалуйста, попробуйте снова.")
        await state.clear()
        return
        
    agent_id = None
    
    try:
        with session_scope() as s:
            app = s.query(Application).options(joinedload(Application.agent)).get(app_id)
            if app:
                print(f"[DEBUG] rop_return_comment: Found application {app_id}, current status: {app.status}")
                app.status = ApplicationStatus.returned_rop
                rop_user = s.query(User).filter(User.telegram_id == str(message.from_user.id)).first()
                rop_name = rop_user.full_name if rop_user else "РОП"
                app.rop_id = rop_user.id if rop_user else None
                agent = s.query(User).filter(User.telegram_id == app.agent.telegram_id).first()
                if agent and agent.telegram_id:
                    agent_id = agent.telegram_id
                print(f"[DEBUG] rop_return_comment: Updated application status to {app.status}, agent_id={agent_id}")
            else:
                print(f"[ERROR] rop_return_comment: Application {app_id} not found")
                await message.answer("Ошибка: заявка не найдена.")
                await state.clear()
                return
        
        if agent_id:
            print(f"[DEBUG] rop_return_comment: Sending notification to agent {agent_id}")
            await notifier.notify_agent_application_returned(agent_id, app_id, comment)
        
        await message.answer(f"✅ Заявка успешно возвращена агенту с комментарием: {comment}")
        print(f"[DEBUG] rop_return_comment: Successfully processed return for app {app_id}")
        
    except Exception as e:
        print(f"[ERROR] rop_return_comment: Unexpected error: {str(e)}")
        await message.answer("Произошла непредвиденная ошибка при обработке запроса.")
    finally:
        await state.clear()
        print("[DEBUG] rop_return_comment: State cleared")