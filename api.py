import asyncio
import hmac
import hashlib
import json
import os
import threading
from urllib.parse import parse_qsl

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN
from database import init_db, create_user, get_user


app = Flask(__name__)
CORS(app)

# --- Путь к папке webapp (абсолютный) ---
WEBAPP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "webapp")


# --- Отдельный event loop для асинхронных функций из Flask ---
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)


def run_async(coro):
    """Запускает асинхронную функцию из синхронного Flask-контекста."""
    return loop.run_until_complete(coro)


# --- Проверка подписи от Telegram WebApp ---
def verify_telegram_init_data(init_data: str) -> dict | None:
    try:
        parsed = dict(parse_qsl(init_data, strict_parsing=True))
        hash_ = parsed.pop("hash", None)
        if not hash_:
            return None

        data_check_string = "\n".join(
            f"{k}={v}" for k, v in sorted(parsed.items())
        )

        secret_key = hmac.new(
            b"WebAppData",
            BOT_TOKEN.encode(),
            hashlib.sha256
        ).digest()

        computed_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(computed_hash, hash_):
            return None

        user_json = parsed.get("user", "{}")
        return json.loads(user_json)
    except Exception as e:
        print(f"verify_telegram_init_data error: {e}")
        return None


# ============================================================
# === ЗАПУСК БОТА В ОТДЕЛЬНОМ ПОТОКЕ ===
# ============================================================

def start_bot_in_thread():
    """Запускает Telegram-бота в фоновом потоке."""
    def bot_thread():
        from bot import create_bot_and_dispatcher

        async def run_bot():
            # Инициализация базы
            await init_db()

            # Создаём бота
            bot, dp = create_bot_and_dispatcher()

            print("🔥 Ember bot запущен в фоне.")
            try:
                await dp.start_polling(bot)
            except Exception as e:
                print(f"❌ Ошибка бота: {e}")

        # Отдельный event loop для потока бота
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        new_loop.run_until_complete(run_bot())

    thread = threading.Thread(target=bot_thread, daemon=True)
    thread.start()
    print("🚀 Поток бота запущен.")


# --- Инициализация базы при первом запросе ---
_db_ready = False


@app.before_request
def ensure_db():
    global _db_ready
    if not _db_ready:
        run_async(init_db())
        _db_ready = True


# --- Главная страница API ---
@app.route("/")
def root():
    return jsonify({"status": "ok", "service": "Ember API"})


# --- Тестовый роут ---
@app.route("/test")
def test_route():
    return jsonify({
        "cwd": os.getcwd(),
        "file_dir": os.path.dirname(os.path.abspath(__file__)),
        "webapp_dir": WEBAPP_DIR,
        "webapp_exists": os.path.exists(WEBAPP_DIR),
        "files_in_webapp": os.listdir(WEBAPP_DIR) if os.path.exists(WEBAPP_DIR) else []
    })


# --- Отдача WebApp ---
@app.route("/webapp/")
def webapp_index():
    return send_from_directory(WEBAPP_DIR, "index.html")


@app.route("/webapp/<path:path>")
def webapp_static(path):
    return send_from_directory(WEBAPP_DIR, path)


# --- Регистрация анкеты из WebApp ---
@app.route("/api/register", methods=["POST"])
def api_register():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "no data"}), 400

    init_data = data.get("initData")
    profile = data.get("profile")

    if not init_data or not profile:
        return jsonify({"error": "missing initData or profile"}), 400

    tg_user = verify_telegram_init_data(init_data)
    if not tg_user:
        return jsonify({"error": "invalid initData"}), 401

    user_id = tg_user.get("id")
    username = tg_user.get("username")

    name = (profile.get("name") or "").strip()
    age = profile.get("age")
    gender = profile.get("gender")
    looking_for = profile.get("looking_for")
    city = (profile.get("city") or "").strip()
    bio = (profile.get("bio") or "").strip()
    photo_id = (profile.get("photo_id") or "").strip()

    if len(name) < 2 or len(name) > 32:
        return jsonify({"error": "Имя от 2 до 32 символов"}), 400
    if not isinstance(age, int) or age < 18 or age > 99:
        return jsonify({"error": "Возраст от 18 до 99"}), 400
    if gender not in ("male", "female"):
        return jsonify({"error": "Неверный пол"}), 400
    if looking_for not in ("male", "female"):
        return jsonify({"error": "Неверный looking_for"}), 400
    if not city:
        return jsonify({"error": "Укажи город"}), 400
    if not photo_id:
        return jsonify({"error": "Нужно фото"}), 400

    try:
        run_async(create_user({
            "user_id": user_id,
            "username": username,
            "name": name,
            "age": age,
            "gender": gender,
            "looking_for": looking_for,
            "city": city,
            "bio": bio[:200],
            "photo_id": photo_id,
        }))
        return jsonify({"ok": True})
    except Exception as e:
        print(f"create_user error: {e}")
        return jsonify({"error": str(e)}), 500


# --- Получить анкету ---
@app.route("/api/profile/<int:user_id>")
def api_profile(user_id):
    u = run_async(get_user(user_id))
    if not u:
        return jsonify({"error": "not found"}), 404
    return jsonify({
        "user_id": u["user_id"],
        "name": u["name"],
        "age": u["age"],
        "city": u["city"],
        "bio": u["bio"],
        "photo_id": u["photo_id"],
    })


# --- Запуск бота при старте приложения ---
# Запускаем ТОЛЬКО если это production (на Render).
# На локальном компьютере бот запускается вручную через `python bot.py`.
if os.getenv("RENDER") or os.getenv("START_BOT") == "1":
    start_bot_in_thread()


if __name__ == "__main__":
    # Локальный запуск — только API
    app.run(host="0.0.0.0", port=5000, debug=False)
