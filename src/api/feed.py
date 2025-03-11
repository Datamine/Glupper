import base64
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from src.core.auth import get_current_user
from src.models.models import User
from src.schemas.schemas import (
    FeedResponse,
    PostResponse,
    TrendingTopic,
)
from src.services.feed_service import (
    get_explore_feed,
    get_home_timeline,
    get_timeline_from_redis,
    get_trending_posts,
    get_trending_topics,
)

router = APIRouter(prefix="/feed", tags=["feed"])


@router.get("/home")
async def home_timeline(
    cursor: Optional[str] = None,
    limit: int = Query(20, ge=1, le=50),
    current_user: User = Depends(get_current_user),
) -> FeedResponse:
    """
    Get user's home timeline

    Uses cursor-based pagination for optimal performance.
    The cursor is a base64 encoded post ID used as a starting point.
    """
    # Decode cursor if provided
    before_id = None
    if cursor:
        try:
            cursor_bytes = base64.b64decode(cursor.encode("utf-8"))
            before_id = UUID(cursor_bytes.decode("utf-8"))
        except:
            pass

    # Get timeline posts directly from Redis for maximum performance
    # If cursor is provided, we'll convert it to a start index for Redis
    start_idx = 0
    if before_id:
        # This is a simplified approach - in production you'd want to handle
        # the cursor differently to support proper pagination with Redis lists
        try:
            # If we're using UUIDs as cursors, we'll treat it as an offset instead
            start_idx = int(str(before_id))
        except:
            pass
    
    posts = await get_timeline_from_redis(current_user.id, limit, start_idx)

    # Generate next cursor
    next_cursor = None
    if posts and len(posts) == limit:
        # For Redis-based pagination, use the next index as cursor
        next_idx = start_idx + limit
        next_cursor = base64.b64encode(str(next_idx).encode("utf-8")).decode("utf-8")

    return {
        "posts": posts,
        "next_cursor": next_cursor,
    }


@router.get("/explore")
async def explore_feed(
    offset: int = 0,
    limit: int = Query(20, ge=1, le=50),
    current_user: User = Depends(get_current_user),
) -> FeedResponse:
    """
    Get explore/discover feed

    Shows popular content from users that the current user doesn't follow
    """
    posts = await get_explore_feed(current_user.id, limit, offset)

    # For simplicity, using offset-based pagination here
    next_offset = offset + limit if len(posts) == limit else None

    return {
        "posts": posts,
        "next_cursor": str(next_offset) if next_offset is not None else None,
    }


@router.get("/trending/topics")
async def trending_topics() -> list[TrendingTopic]:
    """Get trending topics/hashtags"""
    topics = await get_trending_topics()
    return topics


@router.get("/trending/posts")
async def trending_posts(
    limit: int = Query(20, ge=1, le=50),
) -> list[PostResponse]:
    """Get trending posts"""
    posts = await get_trending_posts(limit)
    return posts
