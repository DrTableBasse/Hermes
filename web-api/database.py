import asyncpg
import os
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

_pool: Optional[asyncpg.Pool] = None


async def init_pool():
    global _pool
    _pool = await asyncpg.create_pool(
        host=os.getenv('PG_HOST', 'localhost'),
        port=int(os.getenv('PG_PORT', '5432')),
        database=os.getenv('PG_DB'),
        user=os.getenv('PG_USER'),
        password=os.getenv('PG_PASSWORD'),
        min_size=2,
        max_size=10,
    )


async def close_pool():
    if _pool:
        await _pool.close()


@asynccontextmanager
async def get_conn():
    conn = await _pool.acquire()
    try:
        yield conn
    finally:
        await _pool.release(conn)


async def fetch(q: str, *args) -> List[Dict[str, Any]]:
    async with get_conn() as conn:
        rows = await conn.fetch(q, *args)
        return [dict(r) for r in rows]


async def fetchrow(q: str, *args) -> Optional[Dict[str, Any]]:
    async with get_conn() as conn:
        row = await conn.fetchrow(q, *args)
        return dict(row) if row else None


async def fetchval(q: str, *args):
    async with get_conn() as conn:
        return await conn.fetchval(q, *args)


async def execute(q: str, *args):
    async with get_conn() as conn:
        return await conn.execute(q, *args)


async def executemany(q: str, params: list):
    async with get_conn() as conn:
        await conn.executemany(q, params)
