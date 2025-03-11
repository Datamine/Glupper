import json
from typing import Any, Optional
from uuid import UUID

import redis.asyncio as redis

from src.config_secrets import REDIS_URL

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


# Timeline cache functions
async def cache_user_timeline(user_id: UUID, posts: list[dict[str, Any]], expiry: int = 300):
    """Cache a user's timeline posts in Redis for high-performance reads"""
    if not redis_client:
        return

    key = f"timeline:{user_id}"
    serialized_posts = _serialize_uuid(posts)
    await redis_client.setex(key, expiry, json.dumps(serialized_posts))


async def get_cached_timeline(user_id: UUID) -> Optional[list[dict[str, Any]]]:
    """Get cached timeline posts for a user"""
    if not redis_client:
        return None

    key = f"timeline:{user_id}"
    cached = await redis_client.get(key)
    if cached:
        return json.loads(cached)
    return None


# Post cache functions
async def cache_post(post_id: UUID, post_data: dict[str, Any], expiry: int = 300):
    """Cache post data in Redis"""
    if not redis_client:
        return

    key = f"post:{post_id}"
    serialized_post = _serialize_uuid(post_data)
    await redis_client.setex(key, expiry, json.dumps(serialized_post))


async def get_cached_post(post_id: UUID) -> Optional[dict[str, Any]]:
    """Get cached post data"""
    if not redis_client:
        return None

    key = f"post:{post_id}"
    cached = await redis_client.get(key)
    if cached:
        return json.loads(cached)
    return None


# User profile cache functions
async def cache_user_profile(user_id: UUID, profile_data: dict[str, Any], expiry: int = 300):
    """Cache user profile data in Redis"""
    if not redis_client:
        return

    key = f"user:{user_id}"
    serialized_profile = _serialize_uuid(profile_data)
    await redis_client.setex(key, expiry, json.dumps(serialized_profile))


async def get_cached_user_profile(user_id: UUID) -> Optional[dict[str, Any]]:
    """Get cached user profile data"""
    if not redis_client:
        return None

    key = f"user:{user_id}"
    cached = await redis_client.get(key)
    if cached:
        return json.loads(cached)
    return None


# Trending posts cache
async def cache_trending_posts(posts: list[dict[str, Any]], expiry: int = 300):
    """Cache trending posts in Redis"""
    if not redis_client:
        return

    key = "trending:posts"
    serialized_posts = _serialize_uuid(posts)
    await redis_client.setex(key, expiry, json.dumps(serialized_posts))


async def get_cached_trending_posts() -> Optional[list[dict[str, Any]]]:
    """Get cached trending posts"""
    if not redis_client:
        return None

    key = "trending:posts"
    cached = await redis_client.get(key)
    if cached:
        return json.loads(cached)
    return None


# Cache invalidation functions
async def invalidate_user_timeline(user_id: UUID):
    """Invalidate a user's timeline cache"""
    if not redis_client:
        return

    key = f"timeline:{user_id}"
    await redis_client.delete(key)


async def invalidate_post_cache(post_id: UUID):
    """Invalidate post cache"""
    if not redis_client:
        return

    key = f"post:{post_id}"
    await redis_client.delete(key)


async def invalidate_user_profile_cache(user_id: UUID):
    """Invalidate user profile cache"""
    if not redis_client:
        return

    key = f"user:{user_id}"
    await redis_client.delete(key)
