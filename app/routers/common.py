from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardRemove
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

from app.db.models import User, UserRole
from app.db.repository import session_scope
from app.keyboards.common import menu_kb
from app.config.logging_config import get_logger
from app.routers.rop import notify_rop_about_registration

# Initialize logger
logger = get_logger(__name__)

router = Router(name="common")

class Reg(StatesGroup):
    ask_fullname = State()
    ask_department = State()

@router.message(F.text == "/start")
async def cmd_start(message: Message, state: FSMContext):
    logger.info(f"Received /start from user {message.from_user.id}")
    try:
        # Проверка, зарегистрирован ли пользователь
        with session_scope() as s:
            u = s.query(User).filter(User.telegram_id == str(message.from_user.id)).first()
            if u:
                logger.info(f"User {message.from_user.id} is already registered")
                return await message.answer("Вы уже зарегистрированы. "
                                            "Для редактирования информации используйте /me", reply_markup=menu_kb() )
        
        await state.set_state(Reg.ask_fullname)
        await message.answer("Привет! Введите ваше ФИО для регистрации:")
        logger.debug(f"Started registration for user {message.from_user.id}")
    except Exception as e:
        logger.error(f"Error in cmd_start for user {message.from_user.id}: {str(e)}")
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

@router.message(Reg.ask_fullname)
async def reg_fullname(message: Message, state: FSMContext):
    logger.info(f"Processing fullname for user {message.from_user.id}")
    try:
        full_name = message.text.strip()
        if not full_name:
            await message.answer("Пожалуйста, введите корректное ФИО:")
            return
            
        await state.update_data(full_name=full_name)
        await state.set_state(Reg.ask_department)
        await message.answer("Укажите номер отдела:")
        logger.debug(f"User {message.from_user.id} provided fullname")
    except Exception as e:
        logger.error(f"Error in reg_fullname for user {message.from_user.id}: {str(e)}")
        await message.answer("Произошла ошибка. Пожалуйста, введите ФИО снова:")

@router.message(Reg.ask_department)
async def reg_department(message: Message, state: FSMContext):
    logger.info(f"Processing department for user {message.from_user.id}")
    try:
        dep = None if message.text.strip() == "-" else message.text.strip()
        data = await state.get_data()

        with session_scope() as s:
            # Создаём пользователя со статусом "на проверке"
            user = User(
                telegram_id=str(message.from_user.id),
                full_name=data["full_name"],
                department_no=dep,
                role=UserRole.agent,
                is_active=False,
                is_approved=False
            )
            s.add(user)
            s.flush()  # получаем user.id

            # Ищем РОПа для отдела
            rop_tg = s.query(User).filter(
                User.role == UserRole.rop,
                User.department_no == dep,
                User.is_active == True,
                User.is_approved == True
            ).first()

        # Уведомление РОПа (если есть)
        if rop_tg:
            await notify_rop_about_registration(message.bot, rop_tg.telegram_id, user)
        else:
            logger.warning(f"Не найден активный РОП для отдела {dep}")

        await state.clear()
        await message.answer(
            "Заявка на регистрацию отправлена РОПу указанного отдела. "
            "Ожидайте подтверждения.",
            reply_markup=ReplyKeyboardRemove()
        )
        logger.info(f"User {message.from_user.id} registered, notification sent to ROP")
    except Exception as e:
        logger.error(f"Error in reg_department for user {message.from_user.id}: {str(e)}")
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

@router.message(F.text == "/me")
async def cmd_me(message: Message):
    logger.info(f"Received /me from user {message.from_user.id}")
    try:
        with session_scope() as s:
            u = s.query(User).filter(User.telegram_id == str(message.from_user.id)).first()
            if not u:
                logger.info(f"User {message.from_user.id} is not registered")
                return await message.answer("Вы не зарегистрированы. Наберите /start")
            await message.answer(f"\nФИО: {u.full_name}\n"
                                 f"Отдел: {u.department_no}\n"
                                 f"Роль: {u.role.value}", reply_markup=menu_kb())
            logger.debug(f"User {message.from_user.id} profile retrieved")
    except Exception as e:
        logger.error(f"Error in cmd_me for user {message.from_user.id}: {str(e)}")
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")

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