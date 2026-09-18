"""
Конфигурация бота.
Значения по умолчанию читаются из переменных окружения — так токен и ID
не хранятся в коде. Для быстрого локального теста можно просто
подставить значения напрямую вместо os.getenv(...).

Канал (подписка + публикация расписания) — ОПЦИОНАЛЕН.
Если у мастера нет канала — просто не указывайте CHANNEL_ID / CHANNEL_LINK
(оставьте пустыми или не задавайте переменные окружения). Тогда:
  - проверка подписки перед записью отключается сама;
  - расписание никуда не публикуется;
  - всё остальное (запись, отмена, админ-панель, напоминания) работает как обычно.
"""
import os
from dataclasses import dataclass


def _int_or_none(value: str | None) -> int | None:
    if value is None or not value.strip():
        return None
    try:
        return int(value)
    except ValueError:
        return None


@dataclass
class Config:
    # Токен бота, полученный от @BotFather
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "PUT_YOUR_BOT_TOKEN_HERE")

    # Telegram ID администратора (мастера) — узнать можно у @userinfobot
    ADMIN_ID: int = int(os.getenv("ADMIN_ID", "123456789"))

    # --- Канал для обязательной подписки (ОПЦИОНАЛЬНО) ---
    # Если не заполнено — проверка подписки перед записью не выполняется.
    # ID канала — отрицательное число вида -100xxxxxxxxxx
    CHANNEL_ID: int | None = _int_or_none(os.getenv("CHANNEL_ID"))
    CHANNEL_LINK: str | None = os.getenv("CHANNEL_LINK") or None

    # --- Канал для публикации расписания (ОПЦИОНАЛЬНО) ---
    # Если не заполнено — расписание никуда не публикуется, только в БД.
    SCHEDULE_CHANNEL_ID: int | None = _int_or_none(os.getenv("SCHEDULE_CHANNEL_ID"))

    # Путь к файлу базы данных SQLite
    DB_PATH: str = os.getenv("DB_PATH", "salon.db")

    # На сколько дней вперёд по умолчанию можно листать календарь
    DAYS_AHEAD: int = 30

    # Ссылка на портфолио
    PORTFOLIO_URL: str = "https://ru.pinterest.com/crystalwithluv/_created/"

    @property
    def REQUIRE_SUBSCRIPTION(self) -> bool:
        """Подписка обязательна только если заданы и CHANNEL_ID, и CHANNEL_LINK."""
        return self.CHANNEL_ID is not None and self.CHANNEL_LINK is not None


config = Config()
