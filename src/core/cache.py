from __future__ import annotations

import json
from collections.abc import Awaitable
from datetime import datetime
from typing import cast
from uuid import UUID

import redis.asyncio as redis

from src.config_secrets import REDIS_URL

redis_client: redis.Redis | None = None
BANNED_SET_KEY = "glupper:banned_accounts"


async def init_cache() -> redis.Redis:
    """Initialize Redis client."""
    global redis_client
    if redis_client is not None:
        return redis_client
    redis_client = cast(redis.Redis, redis.from_url(REDIS_URL, decode_responses=True))  # type: ignore[no-untyped-call]
    return redis_client


async def close_cache() -> None:
    """Close Redis client connection."""
    global redis_client
    if redis_client is not None:
        await redis_client.close()
    redis_client = None


async def add_banned_accounts(account_ids: list[UUID], reason: str) -> None:
    """Store banned accounts in Redis for fast lookups."""
    client = await init_cache()
    banned_at = datetime.utcnow().isoformat()
    pipe = client.pipeline()

    for account_id in account_ids:
        account_key = str(account_id)
        pipe.sadd(BANNED_SET_KEY, account_key)
        detail_key = _ban_detail_key(account_key)
        payload = json.dumps({"reason": reason, "banned_at": banned_at})
        pipe.set(detail_key, payload)

    await pipe.execute()


async def is_banned(account_id: UUID) -> bool:
    """Check if account appears in the Redis banned set."""
    client = await init_cache()
    is_member = await cast(Awaitable[int], client.sismember(BANNED_SET_KEY, str(account_id)))
    return bool(is_member)


async def get_ban_record(account_id: UUID) -> dict[str, str] | None:
    """Return cached ban details for one account when present."""
    client = await init_cache()
    payload = await client.get(_ban_detail_key(str(account_id)))
    if payload is None:
        return None
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return None

    reason = parsed.get("reason")
    banned_at = parsed.get("banned_at")
    if not isinstance(reason, str) or not isinstance(banned_at, str):
        return None
    return {"reason": reason, "banned_at": banned_at}


def _ban_detail_key(account_id: str) -> str:
    return f"glupper:banned_account:{account_id}"
