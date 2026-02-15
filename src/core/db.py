from typing import Any, Optional
from uuid import UUID

import asyncpg
from asyncpg import Connection, Pool

from src.config_secrets import DATABASE_URL

# Database connection pool
pool: Optional[Pool] = None


async def init_db():
    """Initialize database connection pool"""
    global pool
    try:
        pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=5,
            max_size=20,  # Reduced connection count for stability
        )

        # Initialize database schema
        if pool:
            await _create_tables()
        return pool
    except Exception as e:
        import logging
        logging.error(f"Database connection error: {str(e)}")
        return None


async def close_db():
    """Close database connection pool"""
    global pool
    if pool:
        await pool.close()


async def get_connection() -> Connection:
    """Get a connection from the pool"""
    if pool is None:
        await init_db()
    assert pool is not None
    return await pool.acquire()


async def release_connection(conn: Connection):
    """Release a connection back to the pool"""
    if pool:
        await pool.release(conn)

