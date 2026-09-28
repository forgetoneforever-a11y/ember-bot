import asyncio
import hmac
import hashlib
import json
import os
from urllib.parse import parse_qsl

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from aiogram.types import Update

from config import BOT_TOKEN
from database import init_db, create_user, get_user


app = Flask(__name__)
CORS(app)

WEBAPP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "webapp")


# --- Отдельный event loop для асинхронных функций из Flask ---
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)


def run_async(coro):
    return loop.run_until_complete(coro)


# --- Проверка подписи от Telegram WebApp ---
def verify_telegram_init_data(init_data: str) -> dict | None:
    try:
        parsed = dict(parse_qsl(init_data, strict_parsing=True))
        hash_ = parsed.pop("hash", None)
        if not hash_:
            return None
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
        secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
        computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(computed_hash, hash_):
            return None
        return json.loads(parsed.get("user", "{}"))
    except Exception as e:
        print(f"verify error: {e}")
        return None


# ============================================================
# === BOT (webhook) =========================================
# ============================================================

# Глобальный объект бота — создаётся один раз при первом webhook-запросе
_bot = None
_dp = None
_bot_ready = False


def ensure_bot():
    """Создаёт бота и диспетчер (один раз)."""
    global _bot, _dp, _bot_ready
    if _bot_ready:
        return
    from bot import create_bot_and_dispatcher
    _bot, _dp = create_bot_and_dispatcher()
    _bot_ready = True
    print("🤖 Бот инициализирован (webhook режим).")


# --- Инициализация базы ---
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
            "user_id": user_id, "username": username, "name": name,
            "age": age, "gender": gender, "looking_for": looking_for,
            "city": city, "bio": bio[:200], "photo_id": photo_id,
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
        "user_id": u["user_id"], "name": u["name"], "age": u["age"],
        "city": u["city"], "bio": u["bio"], "photo_id": u["photo_id"],
    })


# ============================================================
# === WEBHOOK ДЛЯ TELEGRAM ==================================
# ============================================================

@app.route("/webhook/<secret>", methods=["POST"])
def telegram_webhook(secret):
    """Telegram отправляет сюда все апдейты бота."""
    expected = os.getenv("WEBHOOK_SECRET", "ember_secret_123")
    if secret != expected:
        return jsonify({"error": "forbidden"}), 403

    try:
        ensure_bot()
        update_data = request.get_json(force=True)
        update = Update.model_validate(update_data)

        async def process():
            await _dp.feed_update(_bot, update)

        run_async(process())
        return jsonify({"ok": True})
    except Exception as e:
        print(f"webhook error: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/set_webhook")
def set_webhook():
    """Устанавливает webhook в Telegram. Вызови один раз."""
    try:
        ensure_bot()
        render_url = os.getenv("RENDER_EXTERNAL_URL", "https://ember-bot-6xwb.onrender.com")
        secret = os.getenv("WEBHOOK_SECRET", "ember_secret_123")
        webhook_url = f"{render_url}/webhook/{secret}"

        async def set_it():
            await _bot.set_webhook(url=webhook_url, drop_pending_updates=True)
            info = await _bot.get_webhook_info()
            return info

        info = run_async(set_it())
        return jsonify({
            "ok": True,
            "webhook_url": webhook_url,
            "telegram_says": {
                "url": info.url,
                "has_custom_certificate": info.has_custom_certificate,
                "pending_update_count": info.pending_update_count,
                "last_error_message": info.last_error_message,
            }
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/delete_webhook")
def delete_webhook():
    """Удаляет webhook (на случай отладки)."""
    try:
        ensure_bot()

        async def del_it():
            await _bot.delete_webhook(drop_pending_updates=True)

        run_async(del_it())
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
