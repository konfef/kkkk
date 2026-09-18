"""
Напоминания клиентам за 24 часа до записи, на APScheduler (AsyncIOScheduler).

- при создании записи планируем задачу на (дата_время_записи - 24ч);
  если до визита остаётся меньше 24 часов — задача не создаётся;
- при отмене записи задача снимается по job_id;
- при старте бота все активные будущие записи перечитываются из БД
  и для них задачи создаются заново (APScheduler в этом проекте хранит
  задачи в памяти, поэтому после рестарта их нужно восстановить вручную).
"""
import logging
from datetime import datetime, timedelta

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from database import db

logger = logging.getLogger(__name__)

REMINDER_TEXT = (
    "Напоминаем, что вы записаны на завтра в {time}.\n"
    "Ждём вас ✨"
)


def _job_id(booking_id: int) -> str:
    return f"reminder_{booking_id}"


async def _send_reminder(bot: Bot, booking_id: int) -> None:
    booking = await db.get_booking(booking_id)
    if not booking or booking["status"] != "active":
        return  # запись уже отменили — ничего не отправляем
    try:
        await bot.send_message(
            booking["user_id"],
            REMINDER_TEXT.format(time=booking["time"]),
        )
    except Exception:
        logger.exception("Не удалось отправить напоминание пользователю %s", booking["user_id"])


def schedule_reminder(scheduler: AsyncIOScheduler, bot: Bot, booking_id: int, date: str, time: str) -> str | None:
    """Планирует напоминание. Возвращает job_id, либо None если не создано (визит слишком скоро)."""
    appointment_dt = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
    run_date = appointment_dt - timedelta(hours=24)
    if run_date <= datetime.now():
        return None
    job_id = _job_id(booking_id)
    scheduler.add_job(
        _send_reminder,
        trigger="date",
        run_date=run_date,
        args=[bot, booking_id],
        id=job_id,
        replace_existing=True,
    )
    return job_id


def remove_reminder(scheduler: AsyncIOScheduler, job_id: str | None) -> None:
    if not job_id:
        return
    try:
        scheduler.remove_job(job_id)
    except Exception:
        pass  # задачи уже могло не быть (например, если она уже выполнилась)


async def restore_reminders(scheduler: AsyncIOScheduler, bot: Bot) -> None:
    """Вызывается при старте бота — пересоздаёт задачи для активных будущих записей."""
    bookings = await db.get_all_active_future_bookings()
    restored = 0
    for booking in bookings:
        job_id = schedule_reminder(scheduler, bot, booking["id"], booking["date"], booking["time"])
        if job_id and job_id != booking.get("reminder_job_id"):
            await db.set_booking_reminder_job(booking["id"], job_id)
        if job_id:
            restored += 1
    logger.info("Восстановлено напоминаний: %d из %d активных записей", restored, len(bookings))
