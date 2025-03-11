from typing import Any, List, Optional
from uuid import UUID
import base64

from fastapi import APIRouter, Depends, HTTPException, Query

from glupper.app.core.auth import get_current_user
from glupper.app.models.models import User
from glupper.app.schemas.schemas import (
    FeedResponse,
    PostResponse,
    TrendingTopic,
)
from glupper.app.services.feed_service import (
    get_home_timeline,
    get_explore_feed,
    get_trending_topics,
    get_trending_posts,
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
    
    # Get timeline posts
    posts = await get_home_timeline(current_user.id, limit, before_id)
    
    # Generate next cursor
    next_cursor = None
    if posts and len(posts) == limit:
        last_post_id = posts[-1]["id"]
        cursor_str = str(last_post_id)
        next_cursor = base64.b64encode(cursor_str.encode("utf-8")).decode("utf-8")
    
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
async def trending_topics() -> List[TrendingTopic]:
    """Get trending topics/hashtags"""
    topics = await get_trending_topics()
    return topics

@router.get("/trending/posts")
async def trending_posts(
    limit: int = Query(20, ge=1, le=50),
) -> List[PostResponse]:
    """Get trending posts"""
    posts = await get_trending_posts(limit)
    return posts