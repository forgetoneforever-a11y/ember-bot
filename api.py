import hmac
import hashlib
import json
import os
import asyncio
from urllib.parse import parse_qsl

from flask import (Flask, jsonify, request, send_from_directory, redirect)
from flask_cors import CORS
from aiogram import Bot, Dispatcher
from aiogram.types import Update
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN
from database import (init_db, create_user, get_user,
                      get_next_profile, add_like, add_skip,
                      get_user_info)


app = Flask(__name__)
CORS(app)

WEBAPP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "webapp")


# ============================================================
# BOT (webhook, без потока)
# ============================================================

_bot = None
_dp = None
_loop = None
_bot_ready = False


def ensure_bot():
    """Создаёт бота и диспетчер один раз."""
    global _bot, _dp, _loop, _bot_ready
    if _bot_ready:
        return
    from bot import create_bot_and_dispatcher
    _bot, _dp = create_bot_and_dispatcher()
    _loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_loop)
    _bot_ready = True
    print("🤖 Бот инициализирован (webhook режим).")


def run_async(coro):
    """Запускает async-функцию в главном потоке с собственным loop."""
    global _loop
    if _loop is None:
        _loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_loop)
    return _loop.run_until_complete(coro)


# ============================================================
# ПРОВЕРКА ПОДПИСИ TELEGRAM
# ============================================================

def verify_telegram_init_data(init_data: str):
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


def get_tg_user_from_request():
    data = request.get_json(silent=True) or {}
    init_data = data.get("initData")
    if not init_data:
        return None
    return verify_telegram_init_data(init_data)


# ============================================================
# УВЕДОМЛЕНИЯ ЧЕРЕЗ HTTP
# ============================================================

def tg_send_message(chat_id: int, text: str):
    try:
        import requests as rq
        rq.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=10
        )
    except Exception as e:
        print(f"tg_send_message error: {e}")


def tg_send_photo(chat_id: int, photo_id: str, caption: str = "", reply_markup: dict = None):
    try:
        import requests as rq
        payload = {
            "chat_id": chat_id,
            "photo": photo_id,
            "caption": caption,
            "parse_mode": "HTML",
        }
        if reply_markup:
            payload["reply_markup"] = json.dumps(reply_markup)
        rq.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
            json=payload,
            timeout=10
        )
    except Exception as e:
        print(f"tg_send_photo error: {e}")


# ============================================================
# ИНИЦИАЛИЗАЦИЯ
# ============================================================

_db_ready = False


@app.before_request
def ensure_db():
    global _db_ready
    if not _db_ready:
        init_db()
        _db_ready = True


# ============================================================
# ROUTES
# ============================================================

@app.route("/")
def root():
    return jsonify({"status": "ok", "service": "Ember API"})


@app.route("/test")
def test_route():
    return jsonify({
        "webapp_dir": WEBAPP_DIR,
        "webapp_exists": os.path.exists(WEBAPP_DIR),
        "files_in_webapp": os.listdir(WEBAPP_DIR) if os.path.exists(WEBAPP_DIR) else []
    })


@app.route("/api/photo/<path:file_id>")
def api_photo(file_id):
    try:
        import requests as rq
        r = rq.get(
            f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}",
            timeout=10
        )
        data = r.json()
        if not data.get("ok"):
            return "not found", 404
        file_path = data["result"]["file_path"]
        return redirect(f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}")
    except Exception as e:
        print(f"photo proxy error: {e}")
        return "error", 500


@app.route("/webapp/")
def webapp_index():
    return send_from_directory(WEBAPP_DIR, "index.html")


@app.route("/webapp/<path:path>")
def webapp_static(path):
    return send_from_directory(WEBAPP_DIR, path)


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
        create_user({
            "user_id": user_id,
            "username": username,
            "name": name,
            "age": age,
            "gender": gender,
            "looking_for": looking_for,
            "city": city,
            "bio": bio[:200],
            "photo_id": photo_id,
        })
        return jsonify({"ok": True})
    except Exception as e:
        print(f"create_user error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/me", methods=["POST"])
def api_me():
    tg_user = get_tg_user_from_request()
    if not tg_user:
        return jsonify({"error": "invalid initData"}), 401

    u = get_user(tg_user["id"])
    if not u:
        return jsonify({"error": "not registered"}), 404

    return jsonify({
        "user_id": u["user_id"],
        "name": u["name"],
        "age": u["age"],
        "city": u["city"],
        "bio": u["bio"],
        "photo_id": u["photo_id"],
    })


@app.route("/api/feed", methods=["POST"])
def api_feed():
    tg_user = get_tg_user_from_request()
    if not tg_user:
        return jsonify({"error": "invalid initData"}), 401

    user_id = tg_user["id"]
    me = get_user(user_id)
    if not me:
        return jsonify({"error": "not registered"}), 404

    profile = get_next_profile(user_id)
    if not profile:
        return jsonify({"profile": None})

    return jsonify({
        "profile": {
            "user_id": profile["user_id"],
            "name": profile["name"],
            "age": profile["age"],
            "city": profile["city"],
            "bio": profile["bio"],
            "photo_id": profile["photo_id"],
        }
    })


@app.route("/api/like", methods=["POST"])
def api_like():
    tg_user = get_tg_user_from_request()
    if not tg_user:
        return jsonify({"error": "invalid initData"}), 401

    from_id = tg_user["id"]
    data = request.get_json(silent=True) or {}
    to_id = data.get("to_id")

    if not to_id or not isinstance(to_id, int):
        return jsonify({"error": "missing to_id"}), 400

    is_match = add_like(from_id, to_id)

    try:
        me = get_user_info(from_id)
        partner = get_user_info(to_id)
        me_full = get_user(from_id)

        if is_match:
            if me and partner:
                text_partner = f"💘 <b>У тебя искра!</b>\n\nВы с <b>{me['name']}</b> лайкнули друг друга."
                if me.get("username"):
                    text_partner += f"\n👉 @{me['username']}"
                tg_send_message(to_id, text_partner)

                text_me = f"💘 <b>У тебя искра!</b>\n\nВы с <b>{partner['name']}</b> лайкнули друг друга."
                if partner.get("username"):
                    text_me += f"\n👉 @{partner['username']}"
                tg_send_message(from_id, text_me)
        else:
            if me and me_full:
                text = (
                    f"❤️ <b>Тебя лайкнули!</b>\n\n"
                    f"<b>{me['name']}, {me_full['age']}</b>\n"
                    f"📍 {me_full['city']}\n\n"
                    f"{me_full['bio']}"
                )
                kb = {
                    "inline_keyboard": [[
                        {"text": "❤️ Ответить взаимно", "callback_data": f"like_back:{from_id}"}
                    ]]
                }
                tg_send_photo(to_id, me_full["photo_id"], text, kb)
    except Exception as e:
        print(f"like notify error: {e}")

    return jsonify({"ok": True, "match": is_match})


@app.route("/api/skip", methods=["POST"])
def api_skip():
    tg_user = get_tg_user_from_request()
    if not tg_user:
        return jsonify({"error": "invalid initData"}), 401

    from_id = tg_user["id"]
    data = request.get_json(silent=True) or {}
    to_id = data.get("to_id")

    if not to_id or not isinstance(to_id, int):
        return jsonify({"error": "missing to_id"}), 400

    add_skip(from_id, to_id)
    return jsonify({"ok": True})


# ============================================================
# WEBHOOK
# ============================================================

@app.route("/webhook/<secret>", methods=["POST"])
def telegram_webhook(secret):
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
    try:
        render_url = os.getenv("RENDER_EXTERNAL_URL", "https://ember-bot-6xwb.onrender.com")
        secret = os.getenv("WEBHOOK_SECRET", "ember_secret_123")
        webhook_url = f"{render_url}/webhook/{secret}"

        import requests as rq
        r = rq.get(
            f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url={webhook_url}&drop_pending_updates=true",
            timeout=10
        )
        data = r.json()
        return jsonify({
            "ok": data.get("ok"),
            "webhook_url": webhook_url,
            "telegram_says": data
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/delete_webhook")
def delete_webhook():
    try:
        import requests as rq
        r = rq.get(
            f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook?drop_pending_updates=true",
            timeout=10
        )
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ============================================================
# АВТО-WEBHOOK
# ============================================================

def _auto_set_webhook():
    try:
        import time
        time.sleep(3)
        import requests as rq
        render_url = os.getenv("RENDER_EXTERNAL_URL", "https://ember-bot-6xwb.onrender.com")
        secret = os.getenv("WEBHOOK_SECRET", "ember_secret_123")
        webhook_url = f"{render_url}/webhook/{secret}"
        r = rq.get(
            f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url={webhook_url}&drop_pending_updates=true",
            timeout=10
        )
        print(f"🔗 Авто-webhook: {r.json()}")
    except Exception as e:
        print(f"auto webhook error: {e}")


if os.getenv("RENDER"):
    import threading
    threading.Thread(target=_auto_set_webhook, daemon=True).start()


# ============================================================
# ЗАПУСК
# ============================================================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
