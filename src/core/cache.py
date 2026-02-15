import json
from typing import Any, Optional
from uuid import UUID

import redis.asyncio as redis

from src.config_secrets import REDIS_URL
from src.schemas.schemas import RedisPost, RedisTimeline, RedisTrending

# Redis connection
redis_client: Optional[redis.Redis] = None


async def init_cache():
    """Initialize Redis connection"""
    global redis_client
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)


async def close_cache():
    """Close Redis connection"""
    global redis_client
    if redis_client:
        await redis_client.close()


# Helper function to convert UUID to string for Redis
def _serialize_uuid(obj: Any) -> Any:
    if isinstance(obj, UUID):
        return str(obj)
    elif isinstance(obj, dict):
        return {k: _serialize_uuid(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_serialize_uuid(item) for item in obj]
    return obj


