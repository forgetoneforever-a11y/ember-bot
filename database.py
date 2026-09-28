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

        # На случай, если таблица была создана раньше без новых полей
        await conn.execute("""
        ALTER TABLE users ADD COLUMN IF NOT EXISTS is_verified BOOLEAN DEFAULT FALSE;
        """)
        await conn.execute("""
        ALTER TABLE users ADD COLUMN IF NOT EXISTS is_premium BOOLEAN DEFAULT FALSE;
        """)
        await conn.execute("""
        ALTER TABLE users ADD COLUMN IF NOT EXISTS gems INT DEFAULT 100;
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

        # Временное хранение фото (для /photo)
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS temp_photos (
            user_id BIGINT PRIMARY KEY,
            photo_id TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        );
        """)

        # Верификация
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS verification (
            user_id BIGINT PRIMARY KEY,
            photo_id TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT NOW()
        );
        """)

        # Просмотры (кого уже видел юзер в ленте)
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS views (
            from_id BIGINT,
            to_id BIGINT,
            created_at TIMESTAMP DEFAULT NOW(),
            PRIMARY KEY (from_id, to_id)
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


async def get_user_info(user_id: int):
    """Краткая инфа о юзере (имя, username) — для уведомлений."""
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT name, username FROM users WHERE user_id=$1",
            user_id
        )


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
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO temp_photos(user_id, photo_id)
            VALUES($1, $2)
            ON CONFLICT (user_id) DO UPDATE SET
                photo_id = EXCLUDED.photo_id,
                created_at = NOW()
        """, user_id, photo_id)


async def get_temp_photo(user_id: int):
    async with pool.acquire() as conn:
        try:
            row = await conn.fetchrow(
                "SELECT photo_id FROM temp_photos WHERE user_id=$1", user_id)
            return row["photo_id"] if row else None
        except Exception:
            return None


# ============================================================
# === ЛЕНТА / ЛАЙКИ / МЭТЧИ ===
# ============================================================

async def get_next_profile(user_id: int):
    """Возвращает следующую анкету для показа в ленте."""
    async with pool.acquire() as conn:
        me = await conn.fetchrow(
            "SELECT gender, looking_for FROM users WHERE user_id=$1 AND is_active=TRUE",
            user_id
        )
        if not me:
            return None

        row = await conn.fetchrow("""
            SELECT user_id, name, age, gender, city, bio, photo_id,
                   is_verified, is_premium
            FROM users
            WHERE is_active = TRUE
              AND user_id != $1
              AND gender = $2
              AND looking_for = $3
              AND user_id NOT IN (SELECT to_id FROM views WHERE from_id=$1)
              AND user_id NOT IN (SELECT to_id FROM likes WHERE from_id=$1)
            ORDER BY is_verified DESC, RANDOM()
            LIMIT 1
        """, user_id, me["looking_for"], me["gender"])

        if row:
            await conn.execute(
                "INSERT INTO views(from_id, to_id) VALUES($1,$2) ON CONFLICT DO NOTHING",
                user_id, row["user_id"]
            )
        return row


async def add_like(from_id: int, to_id: int) -> bool:
    """Добавляет лайк. Возвращает True, если это мэтч."""
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO likes(from_id, to_id) VALUES($1,$2) ON CONFLICT DO NOTHING",
            from_id, to_id
        )
        await conn.execute(
            "UPDATE users SET likes_received = likes_received + 1 WHERE user_id=$1",
            to_id
        )
        row = await conn.fetchrow(
            "SELECT 1 FROM likes WHERE from_id=$1 AND to_id=$2",
            to_id, from_id
        )
        if row:
            u1, u2 = sorted([from_id, to_id])
            await conn.execute(
                "INSERT INTO matches(user1, user2) VALUES($1,$2) ON CONFLICT DO NOTHING",
                u1, u2
            )
            return True
        return False


async def add_skip(from_id: int, to_id: int):
    """Юзер пропустил анкету (не лайк и не мэтч)."""
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO views(from_id, to_id) VALUES($1,$2) ON CONFLICT DO NOTHING",
            from_id, to_id
        )


# ============================================================
# === ВЕРИФИКАЦИЯ ===
# ============================================================

async def create_verification(user_id: int, photo_id: str):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO verification(user_id, photo_id, status)
            VALUES($1, $2, 'pending')
            ON CONFLICT (user_id) DO UPDATE SET
                photo_id = EXCLUDED.photo_id,
                status = 'pending',
                created_at = NOW()
        """, user_id, photo_id)


async def approve_verification(user_id: int):
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE verification SET status='approved' WHERE user_id=$1",
            user_id
        )
        await conn.execute(
            "UPDATE users SET is_verified=TRUE WHERE user_id=$1",
            user_id
        )


async def reject_verification(user_id: int):
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE verification SET status='rejected' WHERE user_id=$1",
            user_id
        )
        await conn.execute(
            "UPDATE users SET is_verified=FALSE WHERE user_id=$1",
            user_id
        )


async def get_verification_status(user_id: int):
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT status FROM verification WHERE user_id=$1",
            user_id
        )
        return row["status"] if row else None
