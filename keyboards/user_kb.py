from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from config import config


def main_menu_kb(is_admin: bool = False) -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="📅 Записаться"))
    builder.row(KeyboardButton(text="💅 Прайсы"), KeyboardButton(text="🖼 Портфолио"))
    builder.row(KeyboardButton(text="❌ Отменить запись"))
    if is_admin:
        builder.row(KeyboardButton(text="⚙️ Админ-панель"))
    return builder.as_markup(resize_keyboard=True)


def times_kb(date: str, slots: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for slot in slots:
        builder.button(text=slot["time"], callback_data=f"book:time:{slot['id']}")
    builder.adjust(4)
    builder.row(InlineKeyboardButton(text="⬅️ Назад к календарю", callback_data="book:back_to_calendar"))
    return builder.as_markup()


def confirm_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить", callback_data="book:confirm")
    builder.button(text="✏️ Начать заново", callback_data="book:restart")
    builder.adjust(1)
    return builder.as_markup()


def portfolio_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Смотреть портфолио", url=config.PORTFOLIO_URL)
    return builder.as_markup()


def subscribe_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📢 Подписаться", url=config.CHANNEL_LINK)
    builder.button(text="✅ Проверить подписку", callback_data="check_subscription")
    builder.adjust(1)
    return builder.as_markup()


def cancel_booking_confirm_kb(booking_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Да, отменить запись", callback_data=f"cancel:confirm:{booking_id}")
    builder.button(text="Нет, оставить", callback_data="cancel:abort")
    builder.adjust(1)
    return builder.as_markup()
