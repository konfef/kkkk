"""
Пользовательские хендлеры: главное меню, запись (FSM), отмена записи,
проверка подписки на канал.
"""
from datetime import datetime

from aiogram import Router, F, Bot
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import config
from database import db
from states.states import BookingStates
from keyboards.user_kb import (
    main_menu_kb, times_kb, confirm_kb, subscribe_kb, cancel_booking_confirm_kb,
)
from keyboards.calendar_kb import build_calendar
from utils.subscription import is_subscribed
from utils.scheduler import schedule_reminder, remove_reminder

router = Router(name="user")


def is_admin(user_id: int) -> bool:
    return user_id == config.ADMIN_ID


# --------------------------------------------------------------- /start ----

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Здравствуйте! Это бот для записи к мастеру маникюра 💅\n"
        "Выберите действие в меню.",
        reply_markup=main_menu_kb(is_admin(message.from_user.id)),
    )


# ------------------------------------------------------------ booking ------

async def _show_calendar(message: Message, state: FSMContext, year: int, month: int):
    available_dates = set(await db.get_available_dates(config.DAYS_AHEAD))
    if not available_dates:
        await message.answer("К сожалению, сейчас нет свободных дат для записи. Загляните позже 🙏")
        return
    kb = build_calendar(year, month, prefix="book", selectable_dates=available_dates)
    await message.answer("Выберите дату записи:", reply_markup=kb)
    await state.set_state(BookingStates.choosing_date)


@router.message(F.text == "📅 Записаться")
async def start_booking(message: Message, state: FSMContext, bot: Bot):
    if config.REQUIRE_SUBSCRIPTION and not await is_subscribed(bot, message.from_user.id):
        await message.answer(
            "Для записи необходимо подписаться на канал",
            reply_markup=subscribe_kb(),
        )
        return

    existing = await db.get_active_booking_for_user(message.from_user.id)
    if existing:
        await message.answer(
            f"У вас уже есть активная запись на {existing['date']} в {existing['time']}.\n"
            "Чтобы записаться на другое время, сначала отмените текущую запись."
        )
        return

    now = datetime.now()
    await _show_calendar(message, state, now.year, now.month)


@router.callback_query(F.data == "check_subscription")
async def check_subscription_cb(callback: CallbackQuery, bot: Bot):
    if await is_subscribed(bot, callback.from_user.id):
        await callback.message.edit_text("Спасибо за подписку! Теперь нажмите «📅 Записаться» ещё раз.")
    else:
        await callback.answer("Подписка не найдена. Подпишитесь на канал и попробуйте снова.", show_alert=True)


@router.callback_query(BookingStates.choosing_date, F.data.startswith("book:nav:"))
async def booking_calendar_nav(callback: CallbackQuery, state: FSMContext):
    _, _, year, month, _direction = callback.data.split(":")
    available_dates = set(await db.get_available_dates(config.DAYS_AHEAD))
    kb = build_calendar(int(year), int(month), prefix="book", selectable_dates=available_dates)
    await callback.message.edit_reply_markup(reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "book:ignore")
async def booking_calendar_ignore(callback: CallbackQuery):
    await callback.answer()


@router.callback_query(BookingStates.choosing_date, F.data.startswith("book:day:"))
async def booking_choose_date(callback: CallbackQuery, state: FSMContext):
    date_str = callback.data.split(":")[2]
    slots = await db.get_slots_for_date(date_str, only_free=True)
    if not slots:
        await callback.answer("На эту дату уже нет свободных слотов.", show_alert=True)
        return
    await state.update_data(date=date_str)
    await callback.message.edit_text(
        f"Дата: <b>{date_str}</b>\nВыберите удобное время:",
        reply_markup=times_kb(date_str, slots),
    )
    await state.set_state(BookingStates.choosing_time)


@router.callback_query(BookingStates.choosing_time, F.data == "book:back_to_calendar")
async def booking_back_to_calendar(callback: CallbackQuery, state: FSMContext):
    now = datetime.now()
    available_dates = set(await db.get_available_dates(config.DAYS_AHEAD))
    kb = build_calendar(now.year, now.month, prefix="book", selectable_dates=available_dates)
    await callback.message.edit_text("Выберите дату записи:", reply_markup=kb)
    await state.set_state(BookingStates.choosing_date)


@router.callback_query(BookingStates.choosing_time, F.data.startswith("book:time:"))
async def booking_choose_time(callback: CallbackQuery, state: FSMContext):
    slot_id = int(callback.data.split(":")[2])
    data = await state.get_data()
    date_str = data.get("date")

    # проверяем, что слот всё ещё свободен (на случай, если кто-то успел его занять)
    slots = await db.get_slots_for_date(date_str, only_free=True)
    slot = next((s for s in slots if s["id"] == slot_id), None)
    if not slot:
        await callback.answer("Это время уже заняли, выберите другое.", show_alert=True)
        slots = await db.get_slots_for_date(date_str, only_free=True)
        if not slots:
            await callback.message.edit_text("На эту дату больше нет свободных слотов.")
            await state.clear()
            return
        await callback.message.edit_reply_markup(reply_markup=times_kb(date_str, slots))
        return

    await state.update_data(slot_id=slot_id, time=slot["time"])
    await callback.message.edit_text(
        f"Дата: <b>{date_str}</b>\nВремя: <b>{slot['time']}</b>\n\nКак вас зовут?"
    )
    await state.set_state(BookingStates.entering_name)


@router.message(BookingStates.entering_name)
async def booking_enter_name(message: Message, state: FSMContext):
    name = (message.text or "").strip()
    if not name or len(name) > 64:
        await message.answer("Пожалуйста, введите корректное имя.")
        return
    await state.update_data(client_name=name)
    await message.answer("Укажите номер телефона (например, +7 900 000-00-00):")
    await state.set_state(BookingStates.entering_phone)


@router.message(BookingStates.entering_phone, F.contact)
async def booking_enter_phone_contact(message: Message, state: FSMContext):
    await _save_phone_and_confirm(message, state, message.contact.phone_number)


@router.message(BookingStates.entering_phone, F.text)
async def booking_enter_phone_text(message: Message, state: FSMContext):
    phone = message.text.strip()
    digits = "".join(ch for ch in phone if ch.isdigit())
    if len(digits) < 10:
        await message.answer("Похоже, номер введён некорректно. Попробуйте ещё раз.")
        return
    await _save_phone_and_confirm(message, state, phone)


async def _save_phone_and_confirm(message: Message, state: FSMContext, phone: str):
    await state.update_data(phone=phone)
    data = await state.get_data()
    text = (
        "<b>Проверьте данные записи:</b>\n\n"
        f"📅 Дата: <b>{data['date']}</b>\n"
        f"🕐 Время: <b>{data['time']}</b>\n"
        f"🙋 Имя: <b>{data['client_name']}</b>\n"
        f"📞 Телефон: <b>{phone}</b>"
    )
    await message.answer(text, reply_markup=confirm_kb())
    await state.set_state(BookingStates.confirming)


@router.callback_query(BookingStates.confirming, F.data == "book:restart")
async def booking_restart(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    now = datetime.now()
    available_dates = set(await db.get_available_dates(config.DAYS_AHEAD))
    if not available_dates:
        await callback.message.edit_text("Свободных дат сейчас нет.")
        return
    kb = build_calendar(now.year, now.month, prefix="book", selectable_dates=available_dates)
    await callback.message.edit_text("Выберите дату записи:", reply_markup=kb)
    await state.set_state(BookingStates.choosing_date)


@router.callback_query(BookingStates.confirming, F.data == "book:confirm")
async def booking_confirm(callback: CallbackQuery, state: FSMContext, bot: Bot, scheduler: AsyncIOScheduler):
    data = await state.get_data()
    slot = await db.get_slot(data["date"], data["time"])
    if not slot or slot["is_booked"]:
        await callback.message.edit_text("Это время только что заняли. Пожалуйста, начните запись заново.")
        await state.clear()
        return

    existing = await db.get_active_booking_for_user(callback.from_user.id)
    if existing:
        await callback.message.edit_text("У вас уже есть активная запись — новая запись невозможна.")
        await state.clear()
        return

    booking_id = await db.create_booking(
        user_id=callback.from_user.id,
        username=callback.from_user.username,
        client_name=data["client_name"],
        phone=data["phone"],
        date=data["date"],
        time=data["time"],
        slot_id=slot["id"],
    )
    await db.set_slot_booked(slot["id"], True)

    job_id = schedule_reminder(scheduler, bot, booking_id, data["date"], data["time"])
    if job_id:
        await db.set_booking_reminder_job(booking_id, job_id)

    await callback.message.edit_text(
        "✅ Запись подтверждена!\n\n"
        f"📅 {data['date']} в {data['time']}\n"
        "Ждём вас! Если планы изменятся — отменить запись можно в главном меню."
    )
    await state.clear()

    # уведомление администратору
    admin_text = (
        "🆕 <b>Новая запись</b>\n\n"
        f"👤 {data['client_name']}\n"
        f"📞 {data['phone']}\n"
        f"📅 {data['date']} в {data['time']}\n"
        f"Telegram: @{callback.from_user.username or callback.from_user.id}"
    )
    try:
        await bot.send_message(config.ADMIN_ID, admin_text)
    except Exception:
        pass

    # публикация расписания в отдельный канал (если он настроен)
    if config.SCHEDULE_CHANNEL_ID is not None:
        try:
            channel_bookings = await db.get_bookings_for_date(data["date"])
            lines = [f"• {b['time']} — {b['client_name']}" for b in channel_bookings]
            channel_text = f"<b>Расписание на {data['date']}:</b>\n" + "\n".join(lines)
            await bot.send_message(config.SCHEDULE_CHANNEL_ID, channel_text)
        except Exception:
            pass


# ------------------------------------------------------------ cancel -------

@router.message(F.text == "❌ Отменить запись")
async def cancel_start(message: Message, state: FSMContext):
    await state.clear()
    booking = await db.get_active_booking_for_user(message.from_user.id)
    if not booking:
        await message.answer("У вас нет активных записей.")
        return
    text = (
        "У вас запись:\n"
        f"📅 {booking['date']} в {booking['time']}\n\n"
        "Отменить её?"
    )
    await message.answer(text, reply_markup=cancel_booking_confirm_kb(booking["id"]))


@router.callback_query(F.data.startswith("cancel:confirm:"))
async def cancel_confirm(callback: CallbackQuery, bot: Bot, scheduler: AsyncIOScheduler):
    booking_id = int(callback.data.split(":")[2])
    booking = await db.cancel_booking(booking_id)
    if not booking:
        await callback.answer("Эта запись уже была отменена.", show_alert=True)
        return
    remove_reminder(scheduler, booking.get("reminder_job_id"))
    await callback.message.edit_text("Запись отменена. Будем рады видеть вас снова! 🙌")

    try:
        await bot.send_message(
            config.ADMIN_ID,
            f"🚫 Клиент отменил запись: {booking['client_name']} — {booking['date']} в {booking['time']}",
        )
    except Exception:
        pass


@router.callback_query(F.data == "cancel:abort")
async def cancel_abort(callback: CallbackQuery):
    await callback.message.edit_text("Хорошо, запись оставлена в силе.")
