"""
Слой работы с SQLite (через aiosqlite — асинхронный доступ, чтобы не
блокировать event loop бота).

Таблицы:
- slots          — все существующие слоты (дата+время) и их занятость
- closed_days    — дни, полностью закрытые администратором
- bookings       — записи клиентов (в т.ч. отменённые, для истории)
"""
import aiosqlite
from datetime import datetime, timedelta
from typing import Optional

from config import config

DB_PATH = config.DB_PATH

CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS slots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    time TEXT NOT NULL,
    is_booked INTEGER NOT NULL DEFAULT 0,
    UNIQUE(date, time)
);

CREATE TABLE IF NOT EXISTS closed_days (
    date TEXT PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    username TEXT,
    client_name TEXT,
    phone TEXT,
    date TEXT NOT NULL,
    time TEXT NOT NULL,
    slot_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',   -- active | cancelled
    reminder_job_id TEXT,
    created_at TEXT NOT NULL
);
"""


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(CREATE_TABLES_SQL)
        await db.commit()


# ---------------------------------------------------------------- slots ----

async def add_working_day(date: str, start_time: str, end_time: str, interval_minutes: int = 60) -> int:
    """
    Генерирует слоты на указанную дату в диапазоне [start_time, end_time)
    с заданным шагом (в минутах). Возвращает количество созданных слотов.
    Если день был закрыт — снимает закрытие.
    """
    fmt = "%H:%M"
    start = datetime.strptime(start_time, fmt)
    end = datetime.strptime(end_time, fmt)
    created = 0
    async with aiosqlite.connect(DB_PATH) as db:
        cur = start
        while cur < end:
            time_str = cur.strftime(fmt)
            try:
                await db.execute(
                    "INSERT INTO slots (date, time, is_booked) VALUES (?, ?, 0)",
                    (date, time_str),
                )
                created += 1
            except aiosqlite.IntegrityError:
                pass  # слот уже существует — пропускаем
            cur += timedelta(minutes=interval_minutes)
        await db.execute("DELETE FROM closed_days WHERE date = ?", (date,))
        await db.commit()
    return created


async def add_slot(date: str, time: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute(
                "INSERT INTO slots (date, time, is_booked) VALUES (?, ?, 0)",
                (date, time),
            )
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False


async def remove_slot(date: str, time: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "DELETE FROM slots WHERE date = ? AND time = ? AND is_booked = 0",
            (date, time),
        )
        await db.commit()
        return cur.rowcount > 0


async def get_available_dates(days_ahead: int = 30) -> list[str]:
    """Даты в пределах days_ahead, у которых есть хотя бы один свободный слот и день не закрыт."""
    today = datetime.now().date()
    limit = (today + timedelta(days=days_ahead)).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """
            SELECT DISTINCT s.date FROM slots s
            WHERE s.is_booked = 0
              AND s.date >= ?
              AND s.date <= ?
              AND s.date NOT IN (SELECT date FROM closed_days)
            ORDER BY s.date
            """,
            (today.isoformat(), limit),
        )
        rows = await cur.fetchall()
        return [r[0] for r in rows]


async def get_slots_for_date(date: str, only_free: bool = True) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = "SELECT * FROM slots WHERE date = ?"
        params = [date]
        if only_free:
            query += " AND is_booked = 0"
        query += " ORDER BY time"
        cur = await db.execute(query, params)
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def get_slot(date: str, time: str) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM slots WHERE date = ? AND time = ?", (date, time))
        row = await cur.fetchone()
        return dict(row) if row else None


async def set_slot_booked(slot_id: int, booked: bool) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE slots SET is_booked = ? WHERE id = ?", (1 if booked else 0, slot_id))
        await db.commit()


# ------------------------------------------------------------ closed days --

async def close_day(date: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO closed_days (date) VALUES (?)", (date,))
        await db.commit()


async def is_day_closed(date: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT 1 FROM closed_days WHERE date = ?", (date,))
        row = await cur.fetchone()
        return row is not None


# --------------------------------------------------------------- bookings --

async def get_active_booking_for_user(user_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM bookings WHERE user_id = ? AND status = 'active' LIMIT 1",
            (user_id,),
        )
        row = await cur.fetchone()
        return dict(row) if row else None


async def create_booking(
    user_id: int, username: Optional[str], client_name: str, phone: str,
    date: str, time: str, slot_id: int,
) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """
            INSERT INTO bookings (user_id, username, client_name, phone, date, time, slot_id, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?)
            """,
            (user_id, username, client_name, phone, date, time, slot_id, datetime.now().isoformat()),
        )
        await db.commit()
        return cur.lastrowid


async def set_booking_reminder_job(booking_id: int, job_id: Optional[str]) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE bookings SET reminder_job_id = ? WHERE id = ?", (job_id, booking_id))
        await db.commit()


async def get_booking(booking_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def cancel_booking(booking_id: int) -> Optional[dict]:
    """Отменяет запись, освобождает слот. Возвращает данные записи (до отмены) либо None."""
    booking = await get_booking(booking_id)
    if not booking or booking["status"] != "active":
        return None
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE bookings SET status = 'cancelled' WHERE id = ?", (booking_id,))
        await db.execute("UPDATE slots SET is_booked = 0 WHERE id = ?", (booking["slot_id"],))
        await db.commit()
    return booking


async def get_bookings_for_date(date: str) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM bookings WHERE date = ? AND status = 'active' ORDER BY time",
            (date,),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def get_all_active_future_bookings() -> list[dict]:
    """Используется при старте бота для восстановления напоминаний."""
    today = datetime.now().date().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM bookings WHERE status = 'active' AND date >= ?",
            (today,),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]
