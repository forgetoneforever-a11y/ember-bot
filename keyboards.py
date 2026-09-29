from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

WEBAPP_URL = "https://ember-bot-6xwb.onrender.com/webapp/"


def open_app_kb():
    """Кнопка открытия WebApp (для новых юзеров)."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="🔥 Открыть Ember",
            web_app=WebAppInfo(url=f"{WEBAPP_URL}?v=7")
        )
    ]])


def main_menu_kb():
    """Главное меню бота."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🔍 Смотреть анкеты",
            web_app=WebAppInfo(url=f"{WEBAPP_URL}?screen=feed&v=7")
        )],
        [InlineKeyboardButton(
            text="👤 Моя анкета",
            callback_data="my_profile"
        )],
    ])
