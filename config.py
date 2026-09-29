import os
from dotenv import load_dotenv

load_dotenv()

# --- Основное ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

# --- Админ ---
ADMIN_ID = int(os.getenv("ADMIN_ID", "8617178928"))

# --- Бренд ---
BRAND = "Ember"
TAGLINE = "Одна искра — и вы уже горите 🔥"
MIN_AGE = 18

# --- Проверки ---
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в .env")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL не найден в .env")
