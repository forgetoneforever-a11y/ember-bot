# ============================================================
# ЗАПУСК БОТА В ОТДЕЛЬНОМ ПОТОКЕ (для Render)
# ============================================================

import threading

_bot_thread_started = False


def start_bot_in_thread():
    """Запускает бота в отдельном потоке с polling."""
    global _bot_thread_started
    if _bot_thread_started:
        return
    _bot_thread_started = True

    def runner():
        import asyncio
        import logging
        from bot import create_bot_and_dispatcher

        logging.basicConfig(level=logging.INFO)

        async def run_bot():
            bot, dp = create_bot_and_dispatcher()
            print("🤖 Бот запущен в фоне (polling).")
            await dp.start_polling(bot)

        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        try:
            new_loop.run_until_complete(run_bot())
        except Exception as e:
            print(f"❌ Ошибка бота: {e}")
        finally:
            new_loop.close()

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    print("🚀 Поток бота запущен.")
