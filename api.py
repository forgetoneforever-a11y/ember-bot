import asyncio
import concurrent.futures
import hmac
import hashlib
import json
import os
from functools import wraps
from urllib.parse import parse_qsl

from flask import (Flask, jsonify, request, send_from_directory, redirect,
                   session, render_template_string)
from flask_cors import CORS
from aiogram.types import Update, InlineKeyboardMarkup, InlineKeyboardButton

from config import BOT_TOKEN, ADMIN_ID
from database import (init_db, create_user, get_user,
                      get_next_profile, add_like, add_skip,
                      get_user_info, set_city_filter)


app = Flask(__name__)
CORS(app)
app.secret_key = os.getenv("SECRET_KEY", "ember_secret_key_12345")

WEBAPP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "webapp")


# ============================================================
# БЕЗОПАСНЫЙ ЗАПУСК ASYNC-ФУНКЦИЙ
# ============================================================

def run_async(coro):
    """Безопасно запускает async-функцию.
    Если event loop уже запущен — создаёт новый в отдельном потоке.
    Если нет — создаёт новый в текущем потоке.
    """
    try:
        current_loop = asyncio.get_event_loop_policy().get_event_loop()
        is_running = current_loop.is_running()
    except Exception:
        is_running = False

    if is_running:
        # Запускаем в отдельном потоке со своим loop
        def runner():
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            try:
                return new_loop.run_until_complete(coro)
            finally:
                new_loop.close()

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(runner).result()
    else:
        # Запускаем в текущем потоке
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        try:
            return new_loop.run_until_complete(coro)
        finally:
            new_loop.close()


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
# BOT (webhook)
# ============================================================

_bot = None
_dp = None
_bot_ready = False


def ensure_bot():
    global _bot, _dp, _bot_ready
    if _bot_ready:
        return
    from bot import create_bot_and_dispatcher
    _bot, _dp = create_bot_and_dispatcher()
    _bot_ready = True
    print("🤖 Бот инициализирован (webhook режим).")


_db_ready = False


@app.before_request
def ensure_db():
    global _db_ready
    if not _db_ready:
        run_async(init_db())
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


# ---------- Прокси фото ----------

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


# ---------- Отдача WebApp ----------

@app.route("/webapp/")
def webapp_index():
    return send_from_directory(WEBAPP_DIR, "index.html")


@app.route("/webapp/<path:path>")
def webapp_static(path):
    return send_from_directory(WEBAPP_DIR, path)


# ---------- Регистрация ----------

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


# ---------- Моя анкета ----------

@app.route("/api/me", methods=["POST"])
def api_me():
    tg_user = get_tg_user_from_request()
    if not tg_user:
        return jsonify({"error": "invalid initData"}), 401

    u = run_async(get_user(tg_user["id"]))
    if not u:
        return jsonify({"error": "not registered"}), 404

    return jsonify({
        "user_id": u["user_id"],
        "name": u["name"],
        "age": u["age"],
        "city": u["city"],
        "bio": u["bio"],
        "photo_id": u["photo_id"],
        "is_verified": u["is_verified"],
        "is_premium": u["is_premium"],
        "filter_city_only": u["filter_city_only"] if "filter_city_only" in u.keys() else False,
    })


# ---------- Фильтр по городу ----------

@app.route("/api/filter/city", methods=["POST"])
def api_filter_city():
    tg_user = get_tg_user_from_request()
    if not tg_user:
        return jsonify({"error": "invalid initData"}), 401

    data = request.get_json(silent=True) or {}
    only_city = bool(data.get("only_city", False))

    run_async(set_city_filter(tg_user["id"], only_city))
    return jsonify({"ok": True, "only_city": only_city})


# ---------- Лента ----------

@app.route("/api/feed", methods=["POST"])
def api_feed():
    tg_user = get_tg_user_from_request()
    if not tg_user:
        return jsonify({"error": "invalid initData"}), 401

    user_id = tg_user["id"]
    me = run_async(get_user(user_id))
    if not me:
        return jsonify({"error": "not registered"}), 404

    profile = run_async(get_next_profile(user_id))
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
            "is_verified": profile["is_verified"],
            "is_premium": profile["is_premium"],
        }
    })


# ---------- Лайк ----------

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

    is_match = run_async(add_like(from_id, to_id))

    if _bot:
        try:
            me = run_async(get_user_info(from_id))
            partner = run_async(get_user_info(to_id))
            me_full = run_async(get_user(from_id))

            if is_match:
                if me and partner:
                    text_partner = f"💘 <b>У тебя искра!</b>\n\nВы с <b>{me['name']}</b> лайкнули друг друга."
                    if me["username"]:
                        text_partner += f"\n👉 @{me['username']}"
                    try:
                        run_async(_bot.send_message(to_id, text_partner))
                    except Exception:
                        pass

                    text_me = f"💘 <b>У тебя искра!</b>\n\nВы с <b>{partner['name']}</b> лайкнули друг друга."
                    if partner["username"]:
                        text_me += f"\n👉 @{partner['username']}"
                    try:
                        run_async(_bot.send_message(from_id, text_me))
                    except Exception:
                        pass
            else:
                if me and me_full:
                    text = (
                        f"❤️ <b>Тебя лайкнули!</b>\n\n"
                        f"<b>{me['name']}, {me_full['age']}</b>\n"
                        f"📍 {me_full['city']}\n\n"
                        f"{me_full['bio']}"
                    )
                    kb = InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(
                            text="❤️ Ответить взаимно",
                            callback_data=f"like_back:{from_id}"
                        )
                    ]])
                    try:
                        run_async(_bot.send_photo(
                            to_id, me_full["photo_id"],
                            caption=text,
                            reply_markup=kb
                        ))
                    except Exception as e:
                        print(f"like notify error: {e}")
        except Exception as e:
            print(f"match notify error: {e}")

    return jsonify({"ok": True, "match": is_match})


# ---------- Пропуск ----------

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

    run_async(add_skip(from_id, to_id))
    return jsonify({"ok": True})


# ---------- Мэтчи ----------

@app.route("/api/matches", methods=["POST"])
def api_matches():
    tg_user = get_tg_user_from_request()
    if not tg_user:
        return jsonify({"error": "invalid initData"}), 401

    user_id = tg_user["id"]

    async def fetch_matches():
        from database import pool
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT u.user_id, u.name, u.username, u.age, u.photo_id
                FROM matches m
                JOIN users u ON u.user_id = CASE
                    WHEN m.user1 = $1 THEN m.user2
                    ELSE m.user1
                END
                WHERE m.user1 = $1 OR m.user2 = $1
                ORDER BY m.created_at DESC
                LIMIT 50
            """, user_id)
            return [dict(r) for r in rows]

    try:
        matches = run_async(fetch_matches())
        return jsonify({"matches": matches})
    except Exception as e:
        print(f"matches error: {e}")
        return jsonify({"matches": []})


# ---------- Профиль по ID ----------

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
# АДМИН-ПАНЕЛЬ
# ============================================================

def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect("/admin/login")
        return f(*args, **kwargs)
    return wrapper


ADMIN_LOGIN_HTML = """
<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Админ Ember</title>
<style>
body{font-family:system-ui;background:#0a0620;color:#fff;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;}
form{background:rgba(255,255,255,.05);padding:32px;border-radius:16px;border:1px solid rgba(255,255,255,.1);backdrop-filter:blur(20px);width:320px;}
h2{margin:0 0 20px;}
input{width:100%;padding:12px;background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.15);border-radius:10px;color:#fff;font-size:15px;margin-bottom:12px;box-sizing:border-box;}
button{width:100%;padding:14px;background:#ff2e63;color:#fff;border:0;border-radius:10px;font-size:15px;font-weight:700;cursor:pointer;}
.err{color:#ff2e63;margin-bottom:10px;}
</style></head><body>
<form method="post">
<h2>🔐 Админ Ember</h2>
{% if error %}<div class="err">{{error}}</div>{% endif %}
<input type="text" name="login" placeholder="Логин" required>
<input type="password" name="password" placeholder="Пароль" required>
<button type="submit">Войти</button>
</form></body></html>
"""


ADMIN_PANEL_HTML = """
<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Админ Ember</title>
<style>
*{box-sizing:border-box;}
body{font-family:system-ui;background:#0a0620;color:#fff;margin:0;padding:24px;}
h1{font-size:28px;margin-top:0;}
.cards{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:30px;}
.card{background:rgba(255,255,255,.05);padding:20px 28px;border-radius:14px;border:1px solid rgba(255,255,255,.1);backdrop-filter:blur(20px);}
.card .num{font-size:32px;font-weight:800;color:#ff2e63;}
.card .lbl{font-size:13px;color:#aaa;text-transform:uppercase;letter-spacing:1px;}
table{width:100%;background:rgba(255,255,255,.03);border-collapse:collapse;border-radius:14px;overflow:hidden;font-size:14px;}
th,td{padding:10px 12px;text-align:left;border-bottom:1px solid rgba(255,255,255,.07);}
th{background:rgba(255,255,255,.08);font-weight:600;}
tr:hover{background:rgba(255,255,255,.03);}
a{color:#c6ff00;text-decoration:none;}
.btn-red{background:#e74c3c;color:#fff;border:0;padding:6px 12px;border-radius:6px;cursor:pointer;font-size:13px;}
.btn-gray{background:rgba(255,255,255,.1);color:#fff;border:0;padding:6px 12px;border-radius:6px;cursor:pointer;font-size:13px;text-decoration:none;}
.top{display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;}
</style></head><body>

<div class="top">
<h1>📊 Ember — админка</h1>
<a href="/admin/logout" class="btn-gray" style="padding:10px 20px;">Выйти</a>
</div>

<div class="cards">
<div class="card"><div class="num">{{stats.total}}</div><div class="lbl">Всего</div></div>
<div class="card"><div class="num">{{stats.active}}</div><div class="lbl">Активных</div></div>
<div class="card"><div class="num">{{stats.verified}}</div><div class="lbl">Вериф.</div></div>
<div class="card"><div class="num">{{stats.likes}}</div><div class="lbl">Лайков</div></div>
<div class="card"><div class="num">{{stats.matches}}</div><div class="lbl">Мэтчей</div></div>
<div class="card"><div class="num">{{stats.reports}}</div><div class="lbl">Жалоб</div></div>
</div>

<h2>👥 Пользователи ({{users|length}})</h2>

<table>
<tr>
<th>ID</th><th>Username</th><th>Имя</th><th>Возраст</th>
<th>Пол</th><th>Ищет</th><th>Город</th>
<th>Просм.</th><th>Лайки</th><th>Вериф.</th><th>Активен</th><th>Действие</th>
</tr>
{% for u in users %}
<tr>
<td>{{u.user_id}}</td>
<td>{% if u.username %}<a href="https://t.me/{{u.username}}" target="_blank">@{{u.username}}</a>{% else %}—{% endif %}</td>
<td>{{u.name}}</td>
<td>{{u.age}}</td>
<td>{{'М' if u.gender=='male' else 'Ж'}}</td>
<td>{{'М' if u.looking_for=='male' else 'Ж'}}</td>
<td>{{u.city}}</td>
<td>{{u.views or 0}}</td>
<td>{{u.likes_received or 0}}</td>
<td>{{'✓' if u.is_verified else '—'}}</td>
<td>{{'✅' if u.is_active else '❌'}}</td>
<td>
{% if u.is_active %}
<form method="post" action="/admin/ban/{{u.user_id}}" style="display:inline;">
<button class="btn-red" type="submit">Бан</button>
</form>
{% endif %}
</td>
</tr>
{% endfor %}
</table>

</body></html>
"""


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        login = request.form.get("login", "")
        password = request.form.get("password", "")
        admin_login_val = os.getenv("ADMIN_LOGIN", "admin")
        admin_pass_val = os.getenv("ADMIN_PASSWORD", "change_me_123")
        if login == admin_login_val and password == admin_pass_val:
            session["is_admin"] = True
            return redirect("/admin")
        return render_template_string(ADMIN_LOGIN_HTML, error="Неверный логин или пароль")
    return render_template_string(ADMIN_LOGIN_HTML)


@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect("/admin/login")


@app.route("/admin")
@admin_required
def admin_panel():
    async def fetch_data():
        from database import pool
        async with pool.acquire() as conn:
            users = await conn.fetch("""
                SELECT user_id, username, name, age, gender, looking_for,
                       city, views, likes_received, is_verified, is_active, is_premium
                FROM users
                ORDER BY created_at DESC
                LIMIT 500
            """)
            total = await conn.fetchval("SELECT COUNT(*) FROM users")
            active = await conn.fetchval("SELECT COUNT(*) FROM users WHERE is_active=TRUE")
            verified = await conn.fetchval("SELECT COUNT(*) FROM users WHERE is_verified=TRUE")
            likes = await conn.fetchval("SELECT COUNT(*) FROM likes")
            matches = await conn.fetchval("SELECT COUNT(*) FROM matches")
            reports = await conn.fetchval("SELECT COUNT(*) FROM reports")
            return {
                "users": [dict(u) for u in users],
                "stats": {
                    "total": total, "active": active, "verified": verified,
                    "likes": likes, "matches": matches, "reports": reports,
                }
            }

    data = run_async(fetch_data())
    return render_template_string(
        ADMIN_PANEL_HTML,
        users=data["users"],
        stats=data["stats"]
    )


@app.route("/admin/ban/<int:user_id>", methods=["POST"])
@admin_required
def admin_ban(user_id):
    async def do_ban():
        from database import pool
        async with pool.acquire() as conn:
            await conn.execute("UPDATE users SET is_active=FALSE WHERE user_id=$1", user_id)
    run_async(do_ban())
    return redirect("/admin")


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
                "pending_update_count": info.pending_update_count,
                "last_error_message": info.last_error_message,
            }
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/delete_webhook")
def delete_webhook():
    try:
        ensure_bot()

        async def del_it():
            await _bot.delete_webhook(drop_pending_updates=True)

        run_async(del_it())
        return jsonify({"ok": True})
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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
