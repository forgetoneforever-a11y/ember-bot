import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN, BRAND, MIN_AGE
from database import init_db, get_user_count, get_user
from keyboards import open_app_kb, main_menu_kb


bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()


# ---------- /start ----------
@dp.message(Command("start"))
async def cmd_start(msg: Message):
    u = await get_user(msg.from_user.id)

    if u:
        # Уже зарегистрирован
        await msg.answer(
            f"🔥 С возвращением, <b>{u['name']}</b>!\n\n"
            "Что будем делать?",
            reply_markup=main_menu_kb()
        )
    else:
        # Новый пользователь
        await msg.answer(
            f"🔥 Привет! Я <b>{BRAND}</b>.\n\n"
            "Здесь ты найдёшь людей, с которыми хочется общаться.\n"
            "Заполни анкету за минуту — прямо в приложении.\n\n"
            f"⚠️ Только {MIN_AGE}+\n"
            "Продолжая, ты соглашаешься на обработку данных.",
            reply_markup=open_app_kb()
        )


# ---------- /help ----------
@dp.message(Command("help"))
async def cmd_help(msg: Message):
    await msg.answer(
        "Что я умею:\n"
        "/start — главное меню\n"
        "/profile — моя анкета\n"
        "/test_db — проверить базу\n"
        "/help — эта справка"
    )


# ---------- /test_db ----------
@dp.message(Command("test_db"))
async def cmd_test_db(msg: Message):
    try:
        count = await get_user_count()
        await msg.answer(f"✅ База работает!\n\nПользователей в базе: <b>{count}</b>")
    except Exception as e:
        await msg.answer(f"❌ Ошибка базы:\n<code>{e}</code>")


# ---------- /profile ----------
@dp.message(Command("profile"))
async def cmd_profile(msg: Message):
    u = await get_user(msg.from_user.id)
    if not u:
        await msg.answer("У тебя ещё нет анкеты. Создай её в приложении:",
                         reply_markup=open_app_kb())
        return
    await msg.answer_photo(
        u["photo_id"],
        caption=format_profile(u),
        reply_markup=main_menu_kb()
    )


# ---------- callback "Моя анкета" ----------
@dp.callback_query(F.data == "my_profile")
async def cb_my_profile(cb: CallbackQuery):
    u = await get_user(cb.from_user.id)
    if not u:
        await cb.answer("У тебя нет анкеты", show_alert=True)
        return
    await cb.message.answer_photo(
        u["photo_id"],
        caption=format_profile(u),
        reply_markup=main_menu_kb()
    )


def format_profile(u) -> str:
    """Красиво форматирует анкету для показа в боте."""
    username = f"@{u['username']}" if u["username"] else "скрыт"
    verified = " ✓" if u.get("is_verified") else ""
    premium = " ⭐" if u.get("is_premium") else ""
    return (
        f"<b>Твоя анкета в Ember</b>{verified}{premium}\n\n"
        f"<b>{u['name']}, {u['age']}</b>\n"
        f"📍 {u['city']}\n"
        f"🔗 {username}\n\n"
        f"{u['bio']}"
    )


# ---------- запуск ----------
async def main():
    await init_db()
    print(f"🔥 {BRAND} запущен. База подключена.")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())