"""Проверка подписки пользователя на обязательный канал."""
from aiogram import Bot
from config import config

ALLOWED_STATUSES = {"member", "administrator", "creator"}


async def is_subscribed(bot: Bot, user_id: int) -> bool:
    if config.CHANNEL_ID is None:
        return True  # канал не настроен — подписка не требуется
    try:
        member = await bot.get_chat_member(chat_id=config.CHANNEL_ID, user_id=user_id)
        return member.status in ALLOWED_STATUSES
    except Exception:
        # если бот не может проверить (не админ канала, пользователь не найден и т.п.)
        # — по умолчанию считаем, что подписки нет, но не роняем бота
        return False
