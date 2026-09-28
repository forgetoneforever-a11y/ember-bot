import os
from dotenv import load_dotenv

load_dotenv()

# --- Основное ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

# --- Админ ---
ADMIN_ID = int(os.getenv("ADMIN_ID", "8617178928"))
ADMIN_LOGIN = os.getenv("ADMIN_LOGIN", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "change_me_123")

# --- Безопасность ---
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "ember_secret_123")
SECRET_KEY = os.getenv("SECRET_KEY", "ember_secret_key_change_me_in_render")

# --- Бренд ---
BRAND = "Ember"
TAGLINE = "Одна искра — и вы уже горите 🔥"
MIN_AGE = 18

# --- Проверки ---
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в .env")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL не найден в .env")
