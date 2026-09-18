"""
Админ-панель. Доступ проверяется фильтром AdminFilter (по config.ADMIN_ID)
на уровне роутера, так что все хендлеры этого файла для остальных
пользователей просто невидимы.
"""
from datetime import datetime

from aiogram import Router, F, Bot
from aiogram.filters import Command, BaseFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import config
from database import db
from states.states import (
    AdminAddDay, AdminAddSlot, AdminRemoveSlot, AdminCloseDay,
    AdminViewSchedule, AdminCancelBooking,
)
from keyboards.admin_kb import admin_menu_kb, slots_pick_kb, bookings_pick_kb, admin_cancel_confirm_kb
from keyboards.user_kb import main_menu_kb
from keyboards.calendar_kb import build_calendar
from utils.scheduler import remove_reminder


class AdminFilter(BaseFilter):
    async def __call__(self, event: Message | CallbackQuery) -> bool:
        return event.from_user.id == config.ADMIN_ID


router = Router(name="admin")
router.message.filter(AdminFilter())
router.callback_query.filter(AdminFilter())


@router.message(F.text == "⚙️ Админ-панель")
async def open_admin_panel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Админ-панель:", reply_markup=admin_menu_kb())


@router.message(F.text == "⬅️ Выйти из админ-панели")
async def close_admin_panel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Главное меню:", reply_markup=main_menu_kb(is_admin=True))


def _blank_calendar_prefix(prefix: str):
    now = datetime.now()
    return build_calendar(now.year, now.month, prefix=prefix, selectable_dates=None)


# --------------------------------------------------------- add working day -

@router.message(F.text == "➕ Добавить рабочий день")
async def add_day_start(message: Message, state: FSMContext):
    await message.answer("Выберите дату, которую нужно открыть для записи:", reply_markup=_blank_calendar_prefix("aday"))
    await state.set_state(AdminAddDay.choosing_date)


@router.callback_query(AdminAddDay.choosing_date, F.data.startswith("aday:nav:"))
async def add_day_nav(callback: CallbackQuery):
    _, _, year, month, _ = callback.data.split(":")
    kb = build_calendar(int(year), int(month), prefix="aday", selectable_dates=None)
    await callback.message.edit_reply_markup(reply_markup=kb)
    await callback.answer()


@router.callback_query(AdminAddDay.choosing_date, F.data.startswith("aday:day:"))
async def add_day_pick_date(callback: CallbackQuery, state: FSMContext):
    date_str = callback.data.split(":")[2]
    await state.update_data(date=date_str)
    await callback.message.edit_text(f"Дата: {date_str}\nВведите время начала работы (например, 09:00):")
    await state.set_state(AdminAddDay.entering_start)


@router.message(AdminAddDay.entering_start)
async def add_day_start_time(message: Message, state: FSMContext):
    try:
        datetime.strptime(message.text.strip(), "%H:%M")
    except ValueError:
        await message.answer("Неверный формат. Введите время как ЧЧ:ММ, например 09:00")
        return
    await state.update_data(start_time=message.text.strip())
    await message.answer("Введите время окончания работы (например, 18:00):")
    await state.set_state(AdminAddDay.entering_end)


@router.message(AdminAddDay.entering_end)
async def add_day_end_time(message: Message, state: FSMContext):
    try:
        datetime.strptime(message.text.strip(), "%H:%M")
    except ValueError:
        await message.answer("Неверный формат. Введите время как ЧЧ:ММ, например 18:00")
        return
    await state.update_data(end_time=message.text.strip())
    await message.answer("Введите длительность одного слота в минутах (например, 60):")
    await state.set_state(AdminAddDay.entering_interval)


@router.message(AdminAddDay.entering_interval)
async def add_day_interval(message: Message, state: FSMContext):
    if not message.text.strip().isdigit():
        await message.answer("Введите число минут, например 60")
        return
    interval = int(message.text.strip())
    data = await state.get_data()
    created = await db.add_working_day(data["date"], data["start_time"], data["end_time"], interval)
    await message.answer(
        f"Готово! На {data['date']} создано слотов: {created} "
        f"(с {data['start_time']} до {data['end_time']}, шаг {interval} мин).",
        reply_markup=admin_menu_kb(),
    )
    await state.clear()


# -------------------------------------------------------------- add slot ---

@router.message(F.text == "➕ Добавить слот")
async def add_slot_start(message: Message, state: FSMContext):
    await message.answer("Выберите дату для добавления слота:", reply_markup=_blank_calendar_prefix("aslot"))
    await state.set_state(AdminAddSlot.choosing_date)


@router.callback_query(AdminAddSlot.choosing_date, F.data.startswith("aslot:nav:"))
async def add_slot_nav(callback: CallbackQuery):
    _, _, year, month, _ = callback.data.split(":")
    kb = build_calendar(int(year), int(month), prefix="aslot", selectable_dates=None)
    await callback.message.edit_reply_markup(reply_markup=kb)
    await callback.answer()


@router.callback_query(AdminAddSlot.choosing_date, F.data.startswith("aslot:day:"))
async def add_slot_pick_date(callback: CallbackQuery, state: FSMContext):
    date_str = callback.data.split(":")[2]
    await state.update_data(date=date_str)
    await callback.message.edit_text(f"Дата: {date_str}\nВведите время слота (например, 14:30):")
    await state.set_state(AdminAddSlot.entering_time)


@router.message(AdminAddSlot.entering_time)
async def add_slot_time(message: Message, state: FSMContext):
    try:
        datetime.strptime(message.text.strip(), "%H:%M")
    except ValueError:
        await message.answer("Неверный формат. Введите время как ЧЧ:ММ")
        return
    data = await state.get_data()
    ok = await db.add_slot(data["date"], message.text.strip())
    if ok:
        await message.answer(f"Слот {message.text.strip()} на {data['date']} добавлен.", reply_markup=admin_menu_kb())
    else:
        await message.answer("Такой слот уже существует.", reply_markup=admin_menu_kb())
    await state.clear()


# ----------------------------------------------------------- remove slot ---

@router.message(F.text == "➖ Удалить слот")
async def remove_slot_start(message: Message, state: FSMContext):
    await message.answer("Выберите дату:", reply_markup=_blank_calendar_prefix("rslot"))
    await state.set_state(AdminRemoveSlot.choosing_date)


@router.callback_query(AdminRemoveSlot.choosing_date, F.data.startswith("rslot:nav:"))
async def remove_slot_nav(callback: CallbackQuery):
    _, _, year, month, _ = callback.data.split(":")
    kb = build_calendar(int(year), int(month), prefix="rslot", selectable_dates=None)
    await callback.message.edit_reply_markup(reply_markup=kb)
    await callback.answer()


@router.callback_query(AdminRemoveSlot.choosing_date, F.data.startswith("rslot:day:"))
async def remove_slot_pick_date(callback: CallbackQuery, state: FSMContext):
    date_str = callback.data.split(":")[2]
    slots = await db.get_slots_for_date(date_str, only_free=False)
    free_slots = [s for s in slots if not s["is_booked"]]
    if not free_slots:
        await callback.message.edit_text("На эту дату нет свободных (незанятых) слотов для удаления.")
        await state.clear()
        return
    await state.update_data(date=date_str)
    await callback.message.edit_text(
        f"Слоты на {date_str} (нажмите, чтобы удалить свободный):",
        reply_markup=slots_pick_kb(date_str, free_slots, "rslot:pick"),
    )
    await state.set_state(AdminRemoveSlot.choosing_slot)


@router.callback_query(AdminRemoveSlot.choosing_slot, F.data.startswith("rslot:pick:"))
async def remove_slot_pick_slot(callback: CallbackQuery, state: FSMContext):
    slot_id = int(callback.data.split(":")[2])
    data = await state.get_data()
    slots = await db.get_slots_for_date(data["date"], only_free=False)
    slot = next((s for s in slots if s["id"] == slot_id), None)
    if not slot or slot["is_booked"]:
        await callback.answer("Слот занят или уже удалён.", show_alert=True)
        return
    await db.remove_slot(data["date"], slot["time"])
    await callback.message.edit_text(f"Слот {slot['time']} на {data['date']} удалён.")
    await state.clear()


# ------------------------------------------------------------- close day ---

@router.message(F.text == "🚫 Закрыть день")
async def close_day_start(message: Message, state: FSMContext):
    await message.answer("Выберите дату, которую нужно полностью закрыть:", reply_markup=_blank_calendar_prefix("cday"))
    await state.set_state(AdminCloseDay.choosing_date)


@router.callback_query(AdminCloseDay.choosing_date, F.data.startswith("cday:nav:"))
async def close_day_nav(callback: CallbackQuery):
    _, _, year, month, _ = callback.data.split(":")
    kb = build_calendar(int(year), int(month), prefix="cday", selectable_dates=None)
    await callback.message.edit_reply_markup(reply_markup=kb)
    await callback.answer()


@router.callback_query(AdminCloseDay.choosing_date, F.data.startswith("cday:day:"))
async def close_day_pick_date(callback: CallbackQuery, state: FSMContext):
    date_str = callback.data.split(":")[2]
    await db.close_day(date_str)
    await callback.message.edit_text(
        f"День {date_str} закрыт. Новые записи на эту дату недоступны "
        "(уже существующие записи нужно отменить отдельно, если требуется)."
    )
    await state.clear()


# --------------------------------------------------------- view schedule ---

@router.message(F.text == "📋 Расписание на дату")
async def view_schedule_start(message: Message, state: FSMContext):
    await message.answer("Выберите дату:", reply_markup=_blank_calendar_prefix("vsched"))
    await state.set_state(AdminViewSchedule.choosing_date)


@router.callback_query(AdminViewSchedule.choosing_date, F.data.startswith("vsched:nav:"))
async def view_schedule_nav(callback: CallbackQuery):
    _, _, year, month, _ = callback.data.split(":")
    kb = build_calendar(int(year), int(month), prefix="vsched", selectable_dates=None)
    await callback.message.edit_reply_markup(reply_markup=kb)
    await callback.answer()


@router.callback_query(AdminViewSchedule.choosing_date, F.data.startswith("vsched:day:"))
async def view_schedule_pick_date(callback: CallbackQuery, state: FSMContext):
    date_str = callback.data.split(":")[2]
    slots = await db.get_slots_for_date(date_str, only_free=False)
    if not slots:
        text = f"На {date_str} слоты не заданы."
    else:
        bookings = {b["time"]: b for b in await db.get_bookings_for_date(date_str)}
        lines = [f"<b>Расписание на {date_str}:</b>"]
        for s in slots:
            if s["time"] in bookings:
                b = bookings[s["time"]]
                lines.append(f"🔒 {s['time']} — {b['client_name']}, {b['phone']}")
            else:
                lines.append(f"🟢 {s['time']} — свободно")
        text = "\n".join(lines)
    await callback.message.edit_text(text)
    await state.clear()


# -------------------------------------------------------- cancel booking ---

@router.message(F.text == "❌ Отменить запись клиента")
async def admin_cancel_start(message: Message, state: FSMContext):
    await message.answer("Выберите дату записи, которую нужно отменить:", reply_markup=_blank_calendar_prefix("acancel"))
    await state.set_state(AdminCancelBooking.choosing_date)


@router.callback_query(AdminCancelBooking.choosing_date, F.data.startswith("acancel:nav:"))
async def admin_cancel_nav(callback: CallbackQuery):
    _, _, year, month, _ = callback.data.split(":")
    kb = build_calendar(int(year), int(month), prefix="acancel", selectable_dates=None)
    await callback.message.edit_reply_markup(reply_markup=kb)
    await callback.answer()


@router.callback_query(AdminCancelBooking.choosing_date, F.data.startswith("acancel:day:"))
async def admin_cancel_pick_date(callback: CallbackQuery, state: FSMContext):
    date_str = callback.data.split(":")[2]
    bookings = await db.get_bookings_for_date(date_str)
    if not bookings:
        await callback.message.edit_text(f"На {date_str} нет активных записей.")
        await state.clear()
        return
    await callback.message.edit_text(f"Записи на {date_str} — выберите, какую отменить:", reply_markup=bookings_pick_kb(bookings))
    await state.set_state(AdminCancelBooking.choosing_booking)


@router.callback_query(AdminCancelBooking.choosing_booking, F.data.startswith("admin_cancel:pick:"))
async def admin_cancel_pick_booking(callback: CallbackQuery, state: FSMContext):
    booking_id = int(callback.data.split(":")[2])
    await callback.message.edit_text("Подтвердите отмену записи:", reply_markup=admin_cancel_confirm_kb(booking_id))


@router.callback_query(F.data.startswith("admin_cancel:confirm:"))
async def admin_cancel_confirm(callback: CallbackQuery, state: FSMContext, bot: Bot, scheduler: AsyncIOScheduler):
    booking_id = int(callback.data.split(":")[2])
    booking = await db.cancel_booking(booking_id)
    if not booking:
        await callback.answer("Запись уже отменена.", show_alert=True)
        return
    remove_reminder(scheduler, booking.get("reminder_job_id"))
    await callback.message.edit_text(f"Запись {booking['client_name']} на {booking['date']} {booking['time']} отменена.")
    await state.clear()

    try:
        await bot.send_message(
            booking["user_id"],
            f"К сожалению, ваша запись на {booking['date']} в {booking['time']} была отменена мастером. "
            "Свяжитесь с нами для уточнения деталей.",
        )
    except Exception:
        pass


@router.callback_query(F.data == "admin_cancel:abort")
async def admin_cancel_abort(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Отмена записи прервана.")
    await state.clear()
