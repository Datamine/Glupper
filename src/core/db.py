from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import asyncpg
from asyncpg import Connection, Pool

from src.config_secrets import DATABASE_URL

pool: Pool | None = None


async def init_db() -> Pool:
    """Initialize a shared asyncpg pool and ensure required tables exist."""
    global pool
    if pool is not None:
        return pool

    pool = await asyncpg.create_pool(
        DATABASE_URL,
        min_size=2,
        max_size=20,
    )
    await _create_tables(pool)
    return pool


async def close_db() -> None:
    """Close the shared database pool."""
    global pool
    if pool is not None:
        await pool.close()
    pool = None


@asynccontextmanager
async def get_connection() -> AsyncIterator[Connection]:
    """Yield one database connection from the pool."""
    db_pool = await init_db()
    connection = await db_pool.acquire()
    try:
        yield connection
    finally:
        await db_pool.release(connection)


async def _create_tables(db_pool: Pool) -> None:
    """Create all Glupper MVP tables if they do not exist."""
    schema_sql = """
    CREATE TABLE IF NOT EXISTS accounts (
        id UUID PRIMARY KEY,
        username TEXT NOT NULL UNIQUE,
        email TEXT NOT NULL UNIQUE,
        password_hash TEXT,
        auth_provider TEXT NOT NULL CHECK (auth_provider IN ('email', 'google')),
        auth_provider_subject TEXT,
        sponsor_id UUID REFERENCES accounts(id) ON DELETE SET NULL,
        status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'revouch_required', 'banned')),
        demerit_count INTEGER NOT NULL DEFAULT 0,
        trust_started_at TIMESTAMP,
        recovery_eligible_at TIMESTAMP,
        last_active_at TIMESTAMP NOT NULL DEFAULT NOW(),
        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
        CONSTRAINT valid_auth_fields CHECK (
            (auth_provider = 'email' AND password_hash IS NOT NULL) OR
            (auth_provider = 'google' AND auth_provider_subject IS NOT NULL)
        )
    );

    CREATE UNIQUE INDEX IF NOT EXISTS idx_accounts_google_subject
        ON accounts(auth_provider, auth_provider_subject)
        WHERE auth_provider = 'google';

    CREATE TABLE IF NOT EXISTS invite_codes (
        code TEXT PRIMARY KEY,
        sponsor_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
        max_uses INTEGER NOT NULL DEFAULT 1 CHECK (max_uses > 0),
        uses INTEGER NOT NULL DEFAULT 0 CHECK (uses >= 0),
        expires_at TIMESTAMP,
        is_active BOOLEAN NOT NULL DEFAULT TRUE,
        created_at TIMESTAMP NOT NULL DEFAULT NOW()
    );

    CREATE INDEX IF NOT EXISTS idx_invite_codes_sponsor
        ON invite_codes(sponsor_id);

    CREATE TABLE IF NOT EXISTS social_identities (
        id UUID PRIMARY KEY,
        account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
        provider TEXT NOT NULL,
        handle TEXT NOT NULL,
        provider_user_id TEXT NOT NULL,
        verified_at TIMESTAMP NOT NULL DEFAULT NOW(),
        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
        UNIQUE (provider, provider_user_id),
        UNIQUE (account_id, provider)
    );

    CREATE TABLE IF NOT EXISTS account_events (
        id UUID PRIMARY KEY,
        account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
        event_type TEXT NOT NULL,
        payload JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMP NOT NULL DEFAULT NOW()
    );

    CREATE INDEX IF NOT EXISTS idx_account_events_account_created
        ON account_events(account_id, created_at DESC);

    ALTER TABLE accounts
        ADD COLUMN IF NOT EXISTS recovery_eligible_at TIMESTAMP;
    """

    async with db_pool.acquire() as connection:
        await connection.execute(schema_sql)
