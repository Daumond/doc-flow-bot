from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from app.db.models import User, UserRole
from app.db.repository import session_scope

router = Router(name="common")

class Reg(StatesGroup):
    ask_fullname = State()
    ask_department = State()

@router.message(F.text == "/start")
async def cmd_start(message: Message, state: FSMContext):
    # Проверка, зарегистрирован ли пользователь
    with session_scope() as s:
        u = s.query(User).filter(User.telegram_id == str(message.from_user.id)).first()
        if u:
            return await message.answer("Вы уже зарегистрированы. Доступны команды: /new, /me")
    await state.set_state(Reg.ask_fullname)
    await message.answer("Привет! Введите ваше ФИО для регистрации:")

@router.message(Reg.ask_fullname)
async def reg_fullname(message: Message, state: FSMContext):
    await state.update_data(full_name=message.text.strip())
    await state.set_state(Reg.ask_department)
    await message.answer("Укажите номер отдела (можно пропустить, отправив '-' ):")

@router.message(Reg.ask_department)
async def reg_department(message: Message, state: FSMContext):
    dep = None if message.text.strip() == "-" else message.text.strip()
    data = await state.get_data()

    with session_scope() as s:
        # По умолчанию всем даём роль 'agent' (потом админом меняем)
        user = User(
            telegram_id=str(message.from_user.id),
            full_name=data["full_name"],
            department_no=dep,
            role=UserRole.agent,
        )
        s.add(user)

    await state.clear()
    await message.answer("Готово! Вы зарегистрированы как 'агент'. Команды: /new — создать заявку, /me — профиль")

@router.message(F.text == "/me")
async def cmd_me(message: Message):
    with session_scope() as s:
        u = s.query(User).filter(User.telegram_id == str(message.from_user.id)).first()
        if not u:
            return await message.answer("Вы не зарегистрированы. Наберите /start")
        await message.answer(f"\nФИО: {u.full_name}\nОтдел: {u.department_no}\nРоль: {u.role.value}")


from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton


def yes_no_kb():
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="Да", callback_data="yes"),
        InlineKeyboardButton(text="Нет", callback_data="no")
    )
    return kb.as_markup()


def doc_type_kb():
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="Паспорт", callback_data="doc_passport"),
        InlineKeyboardButton(text="ЕГРН", callback_data="doc_egrn"),
        InlineKeyboardButton(text="Прочее", callback_data="doc_other"),
    )
    kb.row(InlineKeyboardButton(text="Завершить загрузку", callback_data="doc_done"))
    return kb.as_markup()