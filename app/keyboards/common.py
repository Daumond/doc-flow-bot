from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
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

def menu_kb():
    kb = ReplyKeyboardBuilder()
    kb.button(text="📝 Новая заявка")
    kb.button(text="📂 Мои заявки")
    kb.adjust(1)
    return kb.as_markup(resize_keyboard=True)

def deal_type_kb():
    kb = ReplyKeyboardBuilder()
    kb.button(text="Покупка")
    kb.button(text="Продажа")
    kb.adjust(2)
    return kb.as_markup(resize_keyboard=True)