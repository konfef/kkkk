"""Кнопки без FSM: Прайсы и Портфолио + служебные callback'и календаря."""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery

from keyboards.user_kb import portfolio_kb

router = Router(name="common")


@router.callback_query(F.data.endswith(":ignore"))
async def ignore_calendar_cb(callback: CallbackQuery):
    """Нажатие на некликабельную ячейку календаря (заголовок, дни недели, пустые клетки)."""
    await callback.answer()

PRICES_TEXT = (
    "<b>💅 Прайс-лист</b>\n\n"
    "Френч — <b>1000₽</b>\n"
    "Квадрат — <b>500₽</b>"
)


@router.message(F.text == "💅 Прайсы")
async def show_prices(message: Message):
    await message.answer(PRICES_TEXT)


@router.message(F.text == "🖼 Портфолио")
async def show_portfolio(message: Message):
    await message.answer("Мои работы 👇", reply_markup=portfolio_kb())
