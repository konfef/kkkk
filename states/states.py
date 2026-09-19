from aiogram.fsm.state import State, StatesGroup


class BookingStates(StatesGroup):
    """Состояния процесса записи клиента."""
    choosing_date = State()
    choosing_time = State()
    choosing_service = State()
    entering_name = State()
    entering_phone = State()
    confirming = State()


class AdminAddDay(StatesGroup):
    """Добавление рабочего дня со слотами."""
    choosing_date = State()
    entering_start = State()
    entering_end = State()
    entering_interval = State()


class AdminAddSlot(StatesGroup):
    choosing_date = State()
    entering_time = State()


class AdminRemoveSlot(StatesGroup):
    choosing_date = State()
    choosing_slot = State()


class AdminCloseDay(StatesGroup):
    choosing_date = State()


class AdminViewSchedule(StatesGroup):
    choosing_date = State()


class AdminCancelBooking(StatesGroup):
    choosing_date = State()
    choosing_booking = State()
