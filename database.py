import psycopg2
import psycopg2.extras
from config import DATABASE_URL


# ============================================================
# ПОДКЛЮЧЕНИЕ
# ============================================================

def get_conn():
    """Создаёт синхронное подключение к PostgreSQL."""
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    return conn


def init_db():
    """Создаёт все таблицы, если их нет."""
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
                is_verified BOOLEAN DEFAULT FALSE,
                is_premium BOOLEAN DEFAULT FALSE,
                views INT DEFAULT 0,
                likes_received INT DEFAULT 0,
                gems INT DEFAULT 100,
                filter_city_only BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW()
            );
            """)

            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_verified BOOLEAN DEFAULT FALSE;")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_premium BOOLEAN DEFAULT FALSE;")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS gems INT DEFAULT 100;")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS filter_city_only BOOLEAN DEFAULT FALSE;")

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
            CREATE TABLE IF NOT EXISTS reports (
                id SERIAL PRIMARY KEY,
                from_id BIGINT,
                to_id BIGINT,
                reason TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            );
            """)

            cur.execute("""
            CREATE TABLE IF NOT EXISTS temp_photos (
                user_id BIGINT PRIMARY KEY,
                photo_id TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            );
            """)

            cur.execute("""
            CREATE TABLE IF NOT EXISTS verification (
                user_id BIGINT PRIMARY KEY,
                photo_id TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT NOW()
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

        print("✅ Таблицы созданы/проверены")
    finally:
        conn.close()


# ============================================================
# ПОЛЬЗОВАТЕЛИ
# ============================================================

def get_user_count() -> int:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM users")
            return cur.fetchone()[0]
    finally:
        conn.close()


def user_exists(user_id: int) -> bool:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM users WHERE user_id=%s", (user_id,))
            return cur.fetchone() is not None
    finally:
        conn.close()


def get_user(user_id: int):
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE user_id=%s", (user_id,))
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def get_user_info(user_id: int):
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT name, username FROM users WHERE user_id=%s", (user_id,))
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def create_user(data: dict):
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
                data["user_id"], data.get("username"), data["name"], data["age"],
                data["gender"], data["looking_for"], data["city"],
                data["bio"], data["photo_id"]
            ))
    finally:
        conn.close()


def deactivate_user(user_id: int):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET is_active=FALSE WHERE user_id=%s", (user_id,))
    finally:
        conn.close()


# ============================================================
# ФИЛЬТР ПО ГОРОДУ
# ============================================================

def set_city_filter(user_id: int, only_city: bool):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET filter_city_only=%s WHERE user_id=%s",
                (only_city, user_id)
            )
    finally:
        conn.close()


# ============================================================
# ВРЕМЕННЫЕ ФОТО
# ============================================================

def save_temp_photo(user_id: int, photo_id: str):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO temp_photos(user_id, photo_id)
                VALUES(%s, %s)
                ON CONFLICT (user_id) DO UPDATE SET
                    photo_id = EXCLUDED.photo_id,
                    created_at = NOW()
            """, (user_id, photo_id))
    finally:
        conn.close()


def get_temp_photo(user_id: int):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT photo_id FROM temp_photos WHERE user_id=%s", (user_id,))
            row = cur.fetchone()
            return row[0] if row else None
    except Exception:
        return None
    finally:
        conn.close()


# ============================================================
# ЛЕНТА / ЛАЙКИ / МЭТЧИ
# ============================================================

def get_next_profile(user_id: int):
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT gender, looking_for, city, filter_city_only FROM users WHERE user_id=%s AND is_active=TRUE",
                (user_id,)
            )
            me = cur.fetchone()
            if not me:
                return None

            sql = """
                SELECT user_id, name, age, gender, city, bio, photo_id,
                       is_verified, is_premium
                FROM users
                WHERE is_active = TRUE
                  AND user_id != %s
                  AND gender = %s
                  AND looking_for = %s
                  AND user_id NOT IN (SELECT to_id FROM views WHERE from_id=%s)
                  AND user_id NOT IN (SELECT to_id FROM likes WHERE from_id=%s)
            """
            args = [user_id, me["looking_for"], me["gender"], user_id, user_id]

            if me["filter_city_only"] and me["city"]:
                sql += " AND LOWER(city) = LOWER(%s)"
                args.append(me["city"])

            sql += " ORDER BY is_verified DESC, RANDOM() LIMIT 1"

            cur.execute(sql, tuple(args))
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
            row = cur.fetchone()
            if row:
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
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO views(from_id, to_id) VALUES(%s,%s) ON CONFLICT DO NOTHING",
                (from_id, to_id)
            )
    finally:
        conn.close()


# ============================================================
# ВЕРИФИКАЦИЯ
# ============================================================

def create_verification(user_id: int, photo_id: str):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO verification(user_id, photo_id, status)
                VALUES(%s, %s, 'pending')
                ON CONFLICT (user_id) DO UPDATE SET
                    photo_id = EXCLUDED.photo_id,
                    status = 'pending',
                    created_at = NOW()
            """, (user_id, photo_id))
    finally:
        conn.close()


def approve_verification(user_id: int):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE verification SET status='approved' WHERE user_id=%s", (user_id,))
            cur.execute("UPDATE users SET is_verified=TRUE WHERE user_id=%s", (user_id,))
    finally:
        conn.close()


def reject_verification(user_id: int):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE verification SET status='rejected' WHERE user_id=%s", (user_id,))
            cur.execute("UPDATE users SET is_verified=FALSE WHERE user_id=%s", (user_id,))
    finally:
        conn.close()


def get_verification_status(user_id: int):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT status FROM verification WHERE user_id=%s", (user_id,))
            row = cur.fetchone()
            return row[0] if row else None
    finally:
        conn.close()


# ============================================================
# УДАЛЕНИЕ АККАУНТА
# ============================================================

def delete_user_completely(user_id: int):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM likes WHERE from_id=%s", (user_id,))
            cur.execute("DELETE FROM likes WHERE to_id=%s", (user_id,))
            cur.execute("DELETE FROM views WHERE from_id=%s", (user_id,))
            cur.execute("DELETE FROM views WHERE to_id=%s", (user_id,))
            cur.execute("DELETE FROM matches WHERE user1=%s OR user2=%s", (user_id, user_id))
            cur.execute("DELETE FROM reports WHERE from_id=%s OR to_id=%s", (user_id, user_id))
            cur.execute("DELETE FROM verification WHERE user_id=%s", (user_id,))
            cur.execute("DELETE FROM temp_photos WHERE user_id=%s", (user_id,))
            cur.execute("DELETE FROM users WHERE user_id=%s", (user_id,))
    finally:
        conn.close()


# ============================================================
# ДЛЯ АДМИНКИ
# ============================================================

def get_all_users():
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT user_id, username, name, age, gender, looking_for,
                       city, views, likes_received, is_verified, is_active, is_premium
                FROM users
                ORDER BY created_at DESC
                LIMIT 500
            """)
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def get_stats():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM users")
            total = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM users WHERE is_active=TRUE")
            active = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM users WHERE is_verified=TRUE")
            verified = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM likes")
            likes = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM matches")
            matches = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM reports")
            reports = cur.fetchone()[0]
            return {
                "total": total, "active": active, "verified": verified,
                "likes": likes, "matches": matches, "reports": reports
            }
    finally:
        conn.close()


def get_matches(user_id: int):
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT u.user_id, u.name, u.username, u.age, u.photo_id
                FROM matches m
                JOIN users u ON u.user_id = CASE
                    WHEN m.user1 = %s THEN m.user2
                    ELSE m.user1
                END
                WHERE m.user1 = %s OR m.user2 = %s
                ORDER BY m.created_at DESC
                LIMIT 50
            """, (user_id, user_id, user_id))
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()
