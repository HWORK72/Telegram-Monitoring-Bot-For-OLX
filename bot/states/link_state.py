from aiogram.fsm.state import State, StatesGroup


class AddLinkState(StatesGroup):
    waiting_for_url = State()
    waiting_for_title = State()