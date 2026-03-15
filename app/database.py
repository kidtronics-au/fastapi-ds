import uuid

import asyncpg
from pgvector.asyncpg import register_vector

from app.config import settings


async def create_pool() -> asyncpg.Pool:
    return await asyncpg.create_pool(str(settings.database_url), init=register_vector)


async def create_session(pool: asyncpg.Pool) -> uuid.UUID:
    session_id = uuid.uuid4()
    student_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    await pool.execute(
        "INSERT INTO chat_sessions (id, student_id, subject) VALUES ($1, $2, $3)",
        session_id,
        student_id,
        "General",
    )
    return session_id
