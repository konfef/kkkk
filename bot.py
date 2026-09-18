"""
Точка входа. Запуск: python bot.py
"""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import config
from database.db import init_db
from utils.scheduler import restore_reminders
from handlers import user, admin, common


async def main() -> None:
    logging.basicConfig(level=logging.INFO)

    await init_db()

    bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    scheduler.start()

    # scheduler доступен во всех хендлерах как аргумент `scheduler: AsyncIOScheduler`
    dp["scheduler"] = scheduler

    # порядок важен: сначала common (ловит служебные ":ignore" колбэки),
    # затем admin (свой AdminFilter отсекает обычных пользователей),
    # затем user
    dp.include_router(common.router)
    dp.include_router(admin.router)
    dp.include_router(user.router)

    # восстанавливаем задачи напоминаний после перезапуска бота
    await restore_reminders(scheduler, bot)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот остановлен.")
