import psycopg2
import psycopg2.extras
from config import DATABASE_URL


def get_conn():
    """Создаёт подключение к PostgreSQL (Neon)."""
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    return conn


def init_db():
    """Создаёт таблицы, если их нет."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
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
                views INT DEFAULT 0,
                likes_received INT DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW()
            );
            """)

            cur.execute("""
            CREATE TABLE IF NOT EXISTS likes (
                from_id BIGINT,
                to_id BIGINT,
                created_at TIMESTAMP DEFAULT NOW(),
                PRIMARY KEY (from_id, to_id)
            );
            """)

            cur.execute("""
            CREATE TABLE IF NOT EXISTS matches (
                user1 BIGINT,
                user2 BIGINT,
                created_at TIMESTAMP DEFAULT NOW(),
                PRIMARY KEY (user1, user2)
            );
            """)

            cur.execute("""
            CREATE TABLE IF NOT EXISTS views (
                from_id BIGINT,
                to_id BIGINT,
                created_at TIMESTAMP DEFAULT NOW(),
                PRIMARY KEY (from_id, to_id)
            );
            """)

            cur.execute("""
            CREATE TABLE IF NOT EXISTS temp_photos (
                user_id BIGINT PRIMARY KEY,
                photo_id TEXT NOT NULL
            );
            """)

        print("✅ Таблицы готовы")
    finally:
        conn.close()


# ============================================================
# ПОЛЬЗОВАТЕЛИ
# ============================================================

def get_user(user_id: int):
    """Возвращает анкету пользователя или None."""
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE user_id=%s", (user_id,))
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def get_user_count() -> int:
    """Сколько всего пользователей в базе."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM users")
            return cur.fetchone()[0]
    finally:
        conn.close()


def get_user_info(user_id: int):
    """Имя и username (для уведомлений о мэтче)."""
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT name, username FROM users WHERE user_id=%s", (user_id,))
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def create_user(data: dict):
    """Создаёт или обновляет анкету пользователя."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO users(user_id, username, name, age, gender,
                                  looking_for, city, bio, photo_id)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)
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
            """, (
                data["user_id"],
                data.get("username"),
                data["name"],
                data["age"],
                data["gender"],
                data["looking_for"],
                data["city"],
                data["bio"],
                data["photo_id"]
            ))
    finally:
        conn.close()


# ============================================================
# ВРЕМЕННОЕ ФОТО (для /photo)
# ============================================================

def save_temp_photo(user_id: int, photo_id: str):
    """Сохраняет фото, пока юзер не завершил регистрацию."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO temp_photos(user_id, photo_id)
                VALUES(%s, %s)
                ON CONFLICT (user_id) DO UPDATE SET
                    photo_id = EXCLUDED.photo_id
            """, (user_id, photo_id))
    finally:
        conn.close()


# ============================================================
# ЛЕНТА
# ============================================================

def get_next_profile(user_id: int):
    """Возвращает следующую анкету для ленты."""
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT gender, looking_for FROM users WHERE user_id=%s",
                (user_id,)
            )
            me = cur.fetchone()
            if not me:
                return None

            cur.execute("""
                SELECT user_id, name, age, city, bio, photo_id
                FROM users
                WHERE is_active = TRUE
                  AND user_id != %s
                  AND gender = %s
                  AND looking_for = %s
                  AND user_id NOT IN (SELECT to_id FROM views WHERE from_id=%s)
                  AND user_id NOT IN (SELECT to_id FROM likes WHERE from_id=%s)
                ORDER BY RANDOM()
                LIMIT 1
            """, (
                user_id,
                me["looking_for"],
                me["gender"],
                user_id,
                user_id
            ))
            row = cur.fetchone()
            if row:
                cur.execute(
                    "INSERT INTO views(from_id, to_id) VALUES(%s,%s) ON CONFLICT DO NOTHING",
                    (user_id, row["user_id"])
                )
                return dict(row)
            return None
    finally:
        conn.close()


def add_like(from_id: int, to_id: int) -> bool:
    """Добавляет лайк. Возвращает True, если это мэтч."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO likes(from_id, to_id) VALUES(%s,%s) ON CONFLICT DO NOTHING",
                (from_id, to_id)
            )
            cur.execute(
                "UPDATE users SET likes_received = likes_received + 1 WHERE user_id=%s",
                (to_id,)
            )
            cur.execute(
                "SELECT 1 FROM likes WHERE from_id=%s AND to_id=%s",
                (to_id, from_id)
            )
            if cur.fetchone():
                u1, u2 = sorted([from_id, to_id])
                cur.execute(
                    "INSERT INTO matches(user1, user2) VALUES(%s,%s) ON CONFLICT DO NOTHING",
                    (u1, u2)
                )
                return True
            return False
    finally:
        conn.close()


def add_skip(from_id: int, to_id: int):
    """Пропуск анкеты (не лайк)."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO views(from_id, to_id) VALUES(%s,%s) ON CONFLICT DO NOTHING",
                (from_id, to_id)
            )
    finally:
        conn.close()
