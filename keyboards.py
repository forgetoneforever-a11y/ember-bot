from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

# URL WebApp — временно заглушка, заменим после деплоя на Render
WEBAPP_URL = "https://example.com/webapp"


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