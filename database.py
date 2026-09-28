import asyncpg
from config import DATABASE_URL

pool = None


async def init_db():
    """Создаёт пул соединений и все таблицы, если их нет."""
    global pool
    if pool is None:
        pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)

    async with pool.acquire() as conn:
        # Таблица пользователей
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            name TEXT,
            age INT,
            gender TEXT,
            looking_for TEXT,
            city TEXT,
            bio TEXT,
            photo_id TEXT,
            is_active BOOLEAN DEFAULT TRUE,
            is_verified BOOLEAN DEFAULT FALSE,
            is_premium BOOLEAN DEFAULT FALSE,
            views INT DEFAULT 0,
            likes_received INT DEFAULT 0,
            gems INT DEFAULT 100,
            created_at TIMESTAMP DEFAULT NOW()
        );
        """)

        # Лайки
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS likes (
            from_id BIGINT,
            to_id BIGINT,
            created_at TIMESTAMP DEFAULT NOW(),
            PRIMARY KEY (from_id, to_id)
        );
        """)

        # Мэтчи
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS matches (
            user1 BIGINT,
            user2 BIGINT,
            created_at TIMESTAMP DEFAULT NOW(),
            PRIMARY KEY (user1, user2)
        );
        """)

        # Жалобы
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id SERIAL PRIMARY KEY,
            from_id BIGINT,
            to_id BIGINT,
            reason TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        );
        """)

        # Временное хранение фото (для регистрации через /photo)
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS temp_photos (
            user_id BIGINT PRIMARY KEY,
            photo_id TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        );
        """)

    print("✅ Таблицы созданы/проверены")


# ============================================================
# === ПОЛЬЗОВАТЕЛИ ===
# ============================================================

async def get_user_count() -> int:
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT COUNT(*) FROM users")


async def user_exists(user_id: int) -> bool:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT 1 FROM users WHERE user_id=$1", user_id)
        return row is not None


async def get_user(user_id: int):
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM users WHERE user_id=$1", user_id)


async def create_user(data: dict):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO users(user_id, username, name, age, gender,
                              looking_for, city, bio, photo_id)
            VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9)
            ON CONFLICT (user_id) DO UPDATE SET
                username = EXCLUDED.username,
                name = EXCLUDED.name,
                age = EXCLUDED.age,
                gender = EXCLUDED.gender,
                looking_for = EXCLUDED.looking_for,
                city = EXCLUDED.city,
                bio = EXCLUDED.bio,
                photo_id = EXCLUDED.photo_id,
                is_active = TRUE
        """, data["user_id"], data.get("username"), data["name"], data["age"],
             data["gender"], data["looking_for"], data["city"],
             data["bio"], data["photo_id"])


async def deactivate_user(user_id: int):
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET is_active=FALSE WHERE user_id=$1", user_id)


# ============================================================
# === ВРЕМЕННЫЕ ФОТО ===
# ============================================================

async def save_temp_photo(user_id: int, photo_id: str):
    """Сохраняет последнее фото пользователя (до регистрации анкеты)."""
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO temp_photos(user_id, photo_id)
            VALUES($1, $2)
            ON CONFLICT (user_id) DO UPDATE SET
                photo_id = EXCLUDED.photo_id,
                created_at = NOW()
        """, user_id, photo_id)


async def get_temp_photo(user_id: int):
    """Возвращает photo_id временного фото или None."""
    async with pool.acquire() as conn:
        try:
            row = await conn.fetchrow(
                "SELECT photo_id FROM temp_photos WHERE user_id=$1",
                user_id
            )
            return row["photo_id"] if row else None
        except Exception:
            return None
