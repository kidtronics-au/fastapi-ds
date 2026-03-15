"""Pure async vector search against the chunks table."""

import asyncpg


async def retrieve(
    query_embedding: list[float],
    pool: asyncpg.Pool,
    match_count: int = 5,
) -> list[dict]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM match_chunks($1, $2)",
            query_embedding,
            match_count,
        )
    return [dict(row) for row in rows]
