"""
Универсальная inline-клавиатура календаря.

Callback data формат: "{prefix}:day:{YYYY-MM-DD}"   — выбор дня
                       "{prefix}:nav:{year}:{month}:{dir}" — навигация (dir = prev/next)
                       "{prefix}:ignore"              — некликабельная ячейка

Один и тот же календарь используется и для клиента (выбор даты записи),
и для админа (выбор даты для управления слотами) — отличается только prefix
и набор дат, которые разрешено выбирать (selectable_dates).
"""
import calendar
from datetime import date
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

MONTHS_RU = [
    "", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
]
WEEKDAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def build_calendar(
    year: int,
    month: int,
    prefix: str,
    selectable_dates: set[str] | None = None,
    min_date: date | None = None,
    max_date: date | None = None,
) -> InlineKeyboardMarkup:
    """
    selectable_dates: если передано — кликабельны только даты из набора
                       (остальные показываются как неактивная точка).
                       Если None — кликабельны все даты в пределах [min_date, max_date].
    """
    builder = InlineKeyboardBuilder()

    builder.row(InlineKeyboardButton(text=f"{MONTHS_RU[month]} {year}", callback_data=f"{prefix}:ignore"))
    builder.row(*[InlineKeyboardButton(text=d, callback_data=f"{prefix}:ignore") for d in WEEKDAYS_RU])

    month_days = calendar.Calendar(firstweekday=0).monthdatescalendar(year, month)
    for week in month_days:
        row = []
        for day in week:
            if day.month != month:
                row.append(InlineKeyboardButton(text=" ", callback_data=f"{prefix}:ignore"))
                continue
            day_str = day.isoformat()
            in_range = True
            if min_date and day < min_date:
                in_range = False
            if max_date and day > max_date:
                in_range = False
            if selectable_dates is not None:
                clickable = in_range and day_str in selectable_dates
            else:
                clickable = in_range
            if clickable:
                row.append(InlineKeyboardButton(text=str(day.day), callback_data=f"{prefix}:day:{day_str}"))
            else:
                row.append(InlineKeyboardButton(text="·", callback_data=f"{prefix}:ignore"))
        builder.row(*row)

    prev_month = month - 1 or 12
    prev_year = year - 1 if month == 1 else year
    next_month = month + 1 if month != 12 else 1
    next_year = year + 1 if month == 12 else year
    builder.row(
        InlineKeyboardButton(text="◀️", callback_data=f"{prefix}:nav:{prev_year}:{prev_month}:prev"),
        InlineKeyboardButton(text="▶️", callback_data=f"{prefix}:nav:{next_year}:{next_month}:next"),
    )
    return builder.as_markup()
