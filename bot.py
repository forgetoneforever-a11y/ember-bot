import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (Message, CallbackQuery, InlineKeyboardMarkup,
                            InlineKeyboardButton, WebAppInfo)
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN, BRAND, MIN_AGE
from database import (init_db, get_user, get_user_count,
                      save_temp_photo, add_like)


logging.basicConfig(level=logging.INFO)

WEBAPP_URL = "https://ember-bot-6xwb.onrender.com/webapp/"


def create_bot_and_dispatcher():
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    # ============================================================
    # /start
    # ============================================================
    @dp.message(Command("start"))
    async def cmd_start(msg: Message):
        u = get_user(msg.from_user.id)

        if u:
            from keyboards import main_menu_kb
            await msg.answer(
                f"🔥 С возвращением, <b>{u['name']}</b>!\n\n"
                "Что будем делать?",
                reply_markup=main_menu_kb()
            )
        else:
            from keyboards import open_app_kb
            await msg.answer(
                f"🔥 Привет! Я <b>{BRAND}</b>.\n\n"
                "Здесь ты найдёшь людей, с которыми хочется общаться.\n"
                "Заполни анкету за минуту — прямо в приложении.\n\n"
                f"⚠️ Только {MIN_AGE}+\n"
                "Продолжая, ты соглашаешься на обработку данных.",
                reply_markup=open_app_kb()
            )

    # ============================================================
    # /help
    # ============================================================
    @dp.message(Command("help"))
    async def cmd_help(msg: Message):
        await msg.answer(
            "Что я умею:\n"
            "/start — главное меню\n"
            "/photo — загрузить фото\n"
            "/profile — моя анкета\n"
            "/test_db — проверить базу\n"
            "/help — эта справка"
        )

    # ============================================================
    # /photo
    # ============================================================
    @dp.message(Command("photo"))
    async def cmd_photo(msg: Message):
        await msg.answer(
            "📸 <b>Загрузи своё фото</b>\n\n"
            "Отправь мне фотографию одним сообщением.\n\n"
            "⚠️ Требования:\n"
            "• Твоё лицо чётко видно\n"
            "• Без чужих людей на фото\n"
            "• Без 18+ контента"
        )

    # ============================================================
    # /test_db
    # ============================================================
    @dp.message(Command("test_db"))
    async def cmd_test_db(msg: Message):
        try:
            count = get_user_count()
            await msg.answer(f"✅ База работает!\n\nПользователей: <b>{count}</b>")
        except Exception as e:
            await msg.answer(f"❌ Ошибка базы:\n<code>{e}</code>")

    # ============================================================
    # /profile
    # ============================================================
    @dp.message(Command("profile"))
    async def cmd_profile(msg: Message):
        u = get_user(msg.from_user.id)
        if not u:
            from keyboards import open_app_kb
            await msg.answer(
                "У тебя ещё нет анкеты. Создай её в приложении:",
                reply_markup=open_app_kb()
            )
            return

        await msg.answer_photo(
            u["photo_id"],
            caption=format_profile(u)
        )

    # ============================================================
    # Callback "Моя анкета"
    # ============================================================
    @dp.callback_query(F.data == "my_profile")
    async def cb_my_profile(cb: CallbackQuery):
        u = get_user(cb.from_user.id)
        if not u:
            await cb.answer("У тебя нет анкеты", show_alert=True)
            return
        await cb.message.answer_photo(
            u["photo_id"],
            caption=format_profile(u)
        )
        await cb.answer()

    # ============================================================
    # Приём фото
    # ============================================================
    @dp.message(F.photo)
    async def handle_photo(msg: Message):
        user_id = msg.from_user.id
        photo_id = msg.photo[-1].file_id

        try:
            save_temp_photo(user_id, photo_id)
        except Exception as e:
            print(f"save_temp_photo error: {e}")

        webapp_url_with_photo = f"{WEBAPP_URL}?photo_id={photo_id}&v=7"
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="🔥 Вернуться в Ember",
                web_app=WebAppInfo(url=webapp_url_with_photo)
            )
        ]])

        await msg.answer(
            "✅ <b>Фото сохранено!</b>\n\n"
            "Нажми кнопку ниже, чтобы вернуться в приложение "
            "и завершить регистрацию.",
            reply_markup=kb
        )

    # ============================================================
    # Callback "Ответить взаимно"
    # ============================================================
    @dp.callback_query(F.data.startswith("like_back:"))
    async def cb_like_back(cb: CallbackQuery):
        from_id = cb.from_user.id
        to_id = int(cb.data.split(":")[1])

        is_match = add_like(from_id, to_id)

        if is_match:
            me = get_user(from_id)
            partner = get_user(to_id)
            try:
                if me and partner:
                    text_me = f"💘 <b>Искра!</b>\n\nВы с <b>{partner['name']}</b> лайкнули друг друга."
                    if partner.get("username"):
                        text_me += f"\n👉 @{partner['username']}"
                    await bot.send_message(from_id, text_me)

                    text_p = f"💘 <b>Искра!</b>\n\nВы с <b>{me['name']}</b> лайкнули друг друга."
                    if me.get("username"):
                        text_p += f"\n👉 @{me['username']}"
                    await bot.send_message(to_id, text_p)
            except Exception as e:
                print(f"like_back notify error: {e}")

            await cb.message.edit_caption(
                caption=(cb.message.caption or "") + "\n\n💘 <b>ВЗАИМНО! Искра!</b>",
                reply_markup=None
            )
        else:
            await cb.message.edit_caption(
                caption=(cb.message.caption or "") + "\n\n❤️ Лайк отправлен!",
                reply_markup=None
            )
        await cb.answer("Готово!")

    return bot, dp


# ============================================================
# Форматирование анкеты
# ============================================================
def format_profile(u) -> str:
    username = f"@{u['username']}" if u.get("username") else "скрыт"
    return (
        f"<b>Твоя анкета в Ember</b>\n\n"
        f"<b>{u['name']}, {u['age']}</b>\n"
        f"📍 {u['city']}\n"
        f"🔗 {username}\n\n"
        f"{u['bio']}"
    )


# ============================================================
# Локальный запуск (polling)
# ============================================================
if __name__ == "__main__":
    async def main():
        init_db()
        bot, dp = create_bot_and_dispatcher()
        print(f"🔥 {BRAND} запущен локально (polling).")
        await dp.start_polling(bot)

    asyncio.run(main())
