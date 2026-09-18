from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def admin_menu_kb() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="➕ Добавить рабочий день"))
    builder.row(KeyboardButton(text="➕ Добавить слот"), KeyboardButton(text="➖ Удалить слот"))
    builder.row(KeyboardButton(text="🚫 Закрыть день"))
    builder.row(KeyboardButton(text="📋 Расписание на дату"))
    builder.row(KeyboardButton(text="❌ Отменить запись клиента"))
    builder.row(KeyboardButton(text="⬅️ Выйти из админ-панели"))
    return builder.as_markup(resize_keyboard=True)


def slots_pick_kb(date: str, slots: list[dict], action_prefix: str) -> InlineKeyboardMarkup:
    """Клавиатура выбора слота на дату (для удаления слота или просмотра)."""
    builder = InlineKeyboardBuilder()
    for slot in slots:
        mark = "🔒" if slot.get("is_booked") else "🟢"
        builder.button(text=f"{mark} {slot['time']}", callback_data=f"{action_prefix}:{slot['id']}")
    builder.adjust(4)
    return builder.as_markup()


def bookings_pick_kb(bookings: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for b in bookings:
        builder.button(
            text=f"{b['time']} — {b['client_name']}",
            callback_data=f"admin_cancel:pick:{b['id']}",
        )
    builder.adjust(1)
    return builder.as_markup()


def admin_cancel_confirm_kb(booking_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Да, отменить", callback_data=f"admin_cancel:confirm:{booking_id}")
    builder.button(text="Нет", callback_data="admin_cancel:abort")
    builder.adjust(1)
    return builder.as_markup()
