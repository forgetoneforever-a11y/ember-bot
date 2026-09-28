import logging
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (Message, CallbackQuery, InlineKeyboardMarkup,
                            InlineKeyboardButton, WebAppInfo)
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN, BRAND, MIN_AGE, ADMIN_ID
from database import (init_db, get_user, get_user_count, save_temp_photo,
                      create_verification, approve_verification,
                      reject_verification, get_verification_status)


logging.basicConfig(level=logging.INFO)

WEBAPP_URL = "https://ember-bot-6xwb.onrender.com/webapp/"


# Храним, кто сейчас в процессе верификации
pending_verification = set()


def create_bot_and_dispatcher():
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    # ============================================================
    # === /start ===
    # ============================================================
    @dp.message(Command("start"))
    async def cmd_start(msg: Message):
        u = await get_user(msg.from_user.id)

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
    # === /help ===
    # ============================================================
    @dp.message(Command("help"))
    async def cmd_help(msg: Message):
        await msg.answer(
            "Что я умею:\n"
            "/start — главное меню\n"
            "/feed — смотреть анкеты\n"
            "/photo — загрузить фото\n"
            "/verify — пройти верификацию\n"
            "/profile — моя анкета\n"
            "/help — эта справка"
        )

    # ============================================================
    # === /feed — лента анкет ===
    # ============================================================
    @dp.message(Command("feed"))
    async def cmd_feed(msg: Message):
        u = await get_user(msg.from_user.id)
        if not u:
            from keyboards import open_app_kb
            await msg.answer(
                "Сначала создай анкету 👇",
                reply_markup=open_app_kb()
            )
            return

        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="🔍 Открыть ленту",
                web_app=WebAppInfo(url=f"{WEBAPP_URL}?screen=feed")
            )
        ]])
        await msg.answer(
            "🔍 <b>Лента анкет</b>\n\n"
            "Смотри анкеты других людей, ставь ❤️ или пропускай 👎.\n"
            "При взаимном лайке вы получите мэтч!",
            reply_markup=kb
        )

    # ============================================================
    # === /photo — загрузка фото для анкеты ===
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
    # === /verify — верификация ===
    # ============================================================
    @dp.message(Command("verify"))
    async def cmd_verify(msg: Message):
        u = await get_user(msg.from_user.id)
        if not u:
            from keyboards import open_app_kb
            await msg.answer("Сначала создай анкету 👇", reply_markup=open_app_kb())
            return

        if u["is_verified"]:
            await msg.answer("✅ Ты уже верифицирован!")
            return

        status = await get_verification_status(msg.from_user.id)
        if status == "pending":
            await msg.answer("⏳ Твоя заявка на проверке. Подожди до 24 часов.")
            return

        await msg.answer(
            "🔒 <b>Верификация</b>\n\n"
            "Чтобы пройти проверку, отправь селфи:\n\n"
            "1. Лицо чётко видно\n"
            "2. Покажи <b>два пальца</b> ✌️ рядом с лицом\n"
            "3. Без фильтров, без маски\n\n"
            "Проверка занимает до 24 часов.\n\n"
            "Что даёт галочка:\n"
            "• Анкета получает в 2 раза больше показов\n"
            "• Значок ✓ рядом с именем\n"
            "• Доверие от других пользователей"
        )
        pending_verification.add(msg.from_user.id)

    # ============================================================
    # === Приём фото (для /photo И /verify) ===
    # ============================================================
    @dp.message(F.photo)
    async def handle_photo(msg: Message):
        user_id = msg.from_user.id
        photo_id = msg.photo[-1].file_id

        # Если юзер в процессе верификации
        if user_id in pending_verification:
            pending_verification.discard(user_id)
            await create_verification(user_id, photo_id)

            # Отправляем админу заявку
            u = await get_user(user_id)
            name = u["name"] if u else "???"
            username = f"@{u['username']}" if u and u["username"] else "нет username"

            from keyboards import verify_decide_kb
            kb = verify_decide_kb(user_id)

            try:
                await bot.send_photo(
                    ADMIN_ID,
                    photo_id,
                    caption=(
                        f"🔔 <b>Заявка на верификацию</b>\n\n"
                        f"👤 Имя: <b>{name}</b>\n"
                        f"🔗 {username}\n"
                        f"🆔 <code>{user_id}</code>"
                    ),
                    reply_markup=kb
                )
            except Exception as e:
                print(f"Не смог отправить админу: {e}")

            await msg.answer(
                "✅ <b>Заявка отправлена!</b>\n\n"
                "Модератор проверит её в течение 24 часов. "
                "Мы уведомим тебя о результате."
            )
            return

        # Иначе — обычное фото для анкеты
        try:
            await save_temp_photo(user_id, photo_id)
        except Exception as e:
            print(f"save_temp_photo error: {e}")

        webapp_url_with_photo = f"{WEBAPP_URL}?photo_id={photo_id}"
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
    # === Решение админа по верификации ===
    # ============================================================
    @dp.callback_query(F.data.startswith("verify_ok:"))
    async def cb_verify_ok(cb: CallbackQuery):
        if cb.from_user.id != ADMIN_ID:
            await cb.answer("Только админ может это делать", show_alert=True)
            return

        user_id = int(cb.data.split(":")[1])
        await approve_verification(user_id)

        try:
            await bot.send_message(
                user_id,
                "🎉 <b>Верификация пройдена!</b>\n\n"
                "Теперь твоя анкета получает в 2 раза больше показов, "
                "а рядом с именем — значок ✓."
            )
        except Exception:
            pass

        if cb.message.caption:
            await cb.message.edit_caption(
                caption=cb.message.caption + "\n\n✅ <b>ОДОБРЕНО</b>",
                reply_markup=None
            )
        await cb.answer("Одобрено!")

    @dp.callback_query(F.data.startswith("verify_no:"))
    async def cb_verify_no(cb: CallbackQuery):
        if cb.from_user.id != ADMIN_ID:
            await cb.answer("Только админ может это делать", show_alert=True)
            return

        user_id = int(cb.data.split(":")[1])
        await reject_verification(user_id)

        try:
            await bot.send_message(
                user_id,
                "❌ <b>Верификация не пройдена</b>\n\n"
                "Причина: фото не соответствует требованиям.\n"
                "Попробуй ещё раз: /verify"
            )
        except Exception:
            pass

        if cb.message.caption:
            await cb.message.edit_caption(
                caption=cb.message.caption + "\n\n❌ <b>ОТКЛОНЕНО</b>",
                reply_markup=None
            )
        await cb.answer("Отклонено!")

    # ============================================================
    # === /test_db ===
    # ============================================================
    @dp.message(Command("test_db"))
    async def cmd_test_db(msg: Message):
        try:
            count = await get_user_count()
            await msg.answer(f"✅ База работает!\n\nПользователей: <b>{count}</b>")
        except Exception as e:
            await msg.answer(f"❌ Ошибка базы:\n<code>{e}</code>")

    # ============================================================
    # === /profile ===
    # ============================================================
    @dp.message(Command("profile"))
    async def cmd_profile(msg: Message):
        u = await get_user(msg.from_user.id)
        if not u:
            from keyboards import open_app_kb
            await msg.answer(
                "У тебя ещё нет анкеты. Создай её в приложении:",
                reply_markup=open_app_kb()
            )
            return
        await msg.answer_photo(u["photo_id"], caption=format_profile(u))

    # ============================================================
    # === Callback "Моя анкета" ===
    # ============================================================
    @dp.callback_query(F.data == "my_profile")
    async def cb_my_profile(cb: CallbackQuery):
        u = await get_user(cb.from_user.id)
        if not u:
            await cb.answer("У тебя нет анкеты", show_alert=True)
            return
        await cb.message.answer_photo(u["photo_id"], caption=format_profile(u))

    # ============================================================
    # === Кнопка "Верификация" в меню ===
    # ============================================================
    @dp.callback_query(F.data == "start_verify")
    async def cb_start_verify(cb: CallbackQuery):
        await cmd_verify(cb.message)
        await cb.answer()

    # ============================================================
    # === Кнопка "Premium" в меню ===
    # ============================================================
    @dp.callback_query(F.data == "show_premium")
    async def cb_show_premium(cb: CallbackQuery):
        await cb.message.answer(
            "⭐ <b>Ember Premium</b>\n\n"
            "Скоро тут будет Premium: без рекламы, "
            "больше показов, кто тебя лайкнул.\n\n"
            "Подписка пока не подключена.",
        )
        await cb.answer()

    # ============================================================
    # === Кнопка "Помощь" в меню ===
    # ============================================================
    @dp.callback_query(F.data == "help")
    async def cb_help(cb: CallbackQuery):
        await cb.message.answer(
            "Что я умею:\n"
            "/start — главное меню\n"
            "/feed — смотреть анкеты\n"
            "/photo — загрузить фото\n"
            "/verify — пройти верификацию\n"
            "/profile — моя анкета\n"
            "/help — эта справка"
        )
        await cb.answer()

    return bot, dp


# ============================================================
# === Красивое форматирование анкеты ===
# ============================================================
def format_profile(u) -> str:
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


# ============================================================
# === Локальный запуск (polling, только для теста) ===
# ============================================================
if __name__ == "__main__":
    import asyncio

    async def main():
        await init_db()
        bot, dp = create_bot_and_dispatcher()
        print(f"🔥 {BRAND} запущен локально (polling).")
        await dp.start_polling(bot)

    asyncio.run(main())
