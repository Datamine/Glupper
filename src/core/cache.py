from __future__ import annotations

import json
from collections.abc import Awaitable
from datetime import datetime
from typing import Any, cast
from uuid import UUID

import redis.asyncio as redis

from src.config_secrets import REDIS_URL

redis_client: redis.Redis | None = None
BANNED_SET_KEY = "glupper:banned_accounts"
GRAPH_CACHE_EPOCH_KEY = "glupper:graph:cache_epoch"
GRAPH_CACHE_PREFIX = "glupper:graph:cache"


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


async def get_graph_cache_epoch() -> int:
    """Return current graph cache epoch, defaulting to zero."""
    client = await init_cache()
    raw_epoch = await client.get(GRAPH_CACHE_EPOCH_KEY)
    if raw_epoch is None:
        return 0
    try:
        return int(raw_epoch)
    except ValueError:
        return 0


async def bump_graph_cache_epoch() -> int:
    """Invalidate graph explorer cache globally via epoch increment."""
    client = await init_cache()
    new_epoch = await cast(Awaitable[int], client.incr(GRAPH_CACHE_EPOCH_KEY))
    return int(new_epoch)


async def get_graph_cache_json(cache_key: str) -> dict[str, Any] | None:
    """Load one graph cache JSON payload by key."""
    client = await init_cache()
    raw_payload = await client.get(cache_key)
    if raw_payload is None:
        return None
    try:
        parsed_payload = json.loads(raw_payload)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed_payload, dict):
        return None
    return parsed_payload


async def set_graph_cache_json(cache_key: str, payload: dict[str, Any], ttl_seconds: int) -> None:
    """Store one graph cache JSON payload with TTL."""
    client = await init_cache()
    await client.set(cache_key, json.dumps(payload), ex=ttl_seconds)


def build_graph_cache_key(*parts: str) -> str:
    """Build namespaced graph cache key."""
    suffix = ":".join(parts)
    return f"{GRAPH_CACHE_PREFIX}:{suffix}"
