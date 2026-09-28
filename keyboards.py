from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

# URL WebApp — реальный адрес на Render
WEBAPP_URL = "https://ember-bot-6xwb.onrender.com/webapp/"


def open_app_kb():
    """Кнопка для открытия WebApp."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="🔥 Открыть Ember",
            web_app=WebAppInfo(url=WEBAPP_URL)
        )
    ]])


def main_menu_kb():
    """Главное меню бота."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🔥 Открыть Ember",
            web_app=WebAppInfo(url=WEBAPP_URL)
        )],
        [InlineKeyboardButton(text="👤 Моя анкета", callback_data="my_profile")],
    ])
