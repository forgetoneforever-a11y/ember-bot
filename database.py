# --- Временное хранение фото ---
async def save_temp_photo(user_id: int, photo_id: str):
    """Сохраняет последнее фото пользователя (для будущей регистрации)."""
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS temp_photos (
                user_id BIGINT PRIMARY KEY,
                photo_id TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            );
        """)
        await conn.execute("""
            INSERT INTO temp_photos(user_id, photo_id)
            VALUES($1, $2)
            ON CONFLICT (user_id) DO UPDATE SET
                photo_id = EXCLUDED.photo_id,
                created_at = NOW()
        """, user_id, photo_id)


async def get_temp_photo(user_id: int):
    """Получает последнее сохранённое фото пользователя."""
    async with pool.acquire() as conn:
        try:
            row = await conn.fetchrow(
                "SELECT photo_id FROM temp_photos WHERE user_id=$1",
                user_id
            )
            return row["photo_id"] if row else None
        except Exception:
            return None
