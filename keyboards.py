from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

WEBAPP_URL = "https://ember-bot-6xwb.onrender.com/webapp/"


def open_app_kb():
    """Кнопка открытия WebApp (для новых юзеров)."""
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
            text="🔍 Смотреть анкеты",
            web_app=WebAppInfo(url=f"{WEBAPP_URL}?screen=feed")  # ← добавили ?screen=feed
        )],
        [
            InlineKeyboardButton(text="👤 Моя анкета", callback_data="my_profile"),
            InlineKeyboardButton(text="🔒 Верификация", callback_data="start_verify"),
        ],
        [
            InlineKeyboardButton(text="⭐ Premium", callback_data="show_premium"),
            InlineKeyboardButton(text="❓ Помощь", callback_data="help"),
        ],
    ])


def my_profile_kb():
    """Кнопки под анкетой."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🗑 Удалить", callback_data="delete_profile"),
    ]])


def confirm_delete_kb():
    """Подтверждение удаления анкеты."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Да, удалить", callback_data="confirm_delete"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_delete"),
    ]])


def profile_kb(user_id: int):
    """Кнопки под чужой анкетой (если через бота)."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="❤️", callback_data=f"like:{user_id}"),
        InlineKeyboardButton(text="👎", callback_data=f"skip:{user_id}"),
        InlineKeyboardButton(text="⚠️", callback_data=f"report:{user_id}"),
    ]])


def report_kb(user_id: int):
    """Жалобы на анкету."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Спам", callback_data=f"rep_ok:{user_id}:spam")],
        [InlineKeyboardButton(text="18+ контент", callback_data=f"rep_ok:{user_id}:adult")],
        [InlineKeyboardButton(text="Оскорбления", callback_data=f"rep_ok:{user_id}:insult")],
        [InlineKeyboardButton(text="Другое", callback_data=f"rep_ok:{user_id}:other")],
    ])


def verify_decide_kb(user_id: int):
    """Кнопки для АДМИНА: одобрить/отклонить верификацию."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Одобрить", callback_data=f"verify_ok:{user_id}"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"verify_no:{user_id}"),
    ]])


def premium_kb():
    """Кнопки Premium."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Оформить", url="https://boosty.to/ember")],
    ])
