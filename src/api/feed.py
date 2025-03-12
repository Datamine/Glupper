import base64
from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from src.core.auth import get_current_user
from src.models.models import User
from src.schemas.schemas import (
    FeedResponse,
    PostResponse,
    TrendingTopic,
)
from src.services.feed_service import (
    get_explore_feed,
    get_timeline_from_redis,
    get_trending_posts,
    get_trending_topics,
)

router = APIRouter(prefix="/api/v1/feed", tags=["feed"])


@router.get("/home", status_code=status.HTTP_200_OK)
async def home_timeline(
    cursor: Optional[str] = None,
    limit: int = Query(20, ge=1, le=50),
    current_user: Annotated[User, Depends(get_current_user)],
) -> FeedResponse:
    """
    Get the authenticated user's home timeline.
    
    Parameters:
    - **cursor**: Optional base64 encoded pagination cursor
    - **limit**: Maximum number of posts to return (default: 20, min: 1, max: 50)
    - **current_user**: User object from token authentication dependency
    
    Returns:
    - **FeedResponse**: List of posts and pagination cursor
    
    Raises:
    - **401 Unauthorized**: If not authenticated
    
    Notes:
    - Uses cursor-based pagination for optimal performance
    - The cursor is a base64 encoded post ID used as a starting point
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


@router.get("/explore", status_code=status.HTTP_200_OK)
async def explore_feed(
    offset: int = 0,
    limit: int = Query(20, ge=1, le=50),
    current_user: Annotated[User, Depends(get_current_user)],
) -> FeedResponse:
    """
    Get discover feed with popular content from non-followed users.
    
    Parameters:
    - **offset**: Pagination offset (default: 0)
    - **limit**: Maximum number of posts to return (default: 20, min: 1, max: 50)
    - **current_user**: User object from token authentication dependency
    
    Returns:
    - **FeedResponse**: List of posts and pagination information
    
    Raises:
    - **401 Unauthorized**: If not authenticated
    
    Notes:
    - Shows popular content from users that the current user doesn't follow
    - Uses offset-based pagination
    """
    posts = await get_explore_feed(current_user.id, limit, offset)

    # For simplicity, using offset-based pagination here
    next_offset = offset + limit if len(posts) == limit else None

    return {
        "posts": posts,
        "next_cursor": str(next_offset) if next_offset is not None else None,
    }


@router.get("/trending/topics", status_code=status.HTTP_200_OK)
async def trending_topics() -> list[TrendingTopic]:
    """
    Get trending topics and hashtags.
    
    Returns:
    - **list[TrendingTopic]**: List of trending topics with their post counts
    """
    topics = await get_trending_topics()
    return topics


@router.get("/trending/posts", status_code=status.HTTP_200_OK)
async def trending_posts(
    limit: int = Query(20, ge=1, le=50),
) -> list[PostResponse]:
    """
    Get trending posts across the platform.
    
    Parameters:
    - **limit**: Maximum number of posts to return (default: 20, min: 1, max: 50)
    
    Returns:
    - **list[PostResponse]**: List of trending posts sorted by popularity
    """
    posts = await get_trending_posts(limit)
    return posts
