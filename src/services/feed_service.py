import random
from typing import Dict, List, Optional
from uuid import UUID

from src.core.cache import (
    cache_trending_posts,
    cache_user_timeline,
    get_cached_timeline,
    get_cached_trending_posts,
    redis_client,
)
from src.core.db import get_user_timeline_posts, pool


async def get_home_timeline(user_id: UUID, limit: int = 20, before_id: Optional[UUID] = None) -> list[Dict]:
    """
    Get home timeline for a user

    This function implements a high-performance timeline algorithm that:
    1. Uses Redis as the primary data source for timeline data
    2. Falls back to database only when necessary
    3. Maintains timeline in Redis for fast access
    """
    # Skip cache if using cursor-based pagination
    if before_id is None:
        # Try to get from cache first
        cached_timeline = await get_cached_timeline(user_id)
        if cached_timeline:
            return cached_timeline[:limit]

    # If not in cache or using pagination, get from database
    posts = await get_user_timeline_posts(user_id, limit, before_id)

    # Cache the result if this is the first page
    if before_id is None:
        await cache_user_timeline(user_id, posts)

    return posts


async def push_post_to_timelines(post: Dict, author_id: UUID):
    """
    Push a new post to followers' timelines in Redis
    
    This implements a fanout-on-write approach for high-performance feeds
    using proper serialization via Pydantic models
    """
    if not redis_client:
        return
        
    # Get all followers of the post author
    async with pool.acquire() as conn:
        query = """
        SELECT follower_id FROM follows WHERE followee_id = $1
        """
        follower_rows = await conn.fetch(query, author_id)
        follower_ids = [str(row["follower_id"]) for row in follower_rows]
        
    # Add the author to the list (to see their own posts)
    follower_ids.append(str(author_id))
    
    if not follower_ids:
        return
        
    # Convert to RedisPost for proper serialization
    from src.schemas.schemas import RedisPost
    redis_post = RedisPost.from_dict(post)
    serialized_post = redis_post.to_redis()
    
    # Push to each follower's timeline
    pipe = redis_client.pipeline()
    for follower_id in follower_ids:
        timeline_key = f"timeline:{follower_id}"
        
        # Add to the beginning of the list
        pipe.lpush(timeline_key, serialized_post)
        
        # Trim the list to keep it at a reasonable size
        pipe.ltrim(timeline_key, 0, 500)  # Keep 500 most recent posts
        
        # Set expiry (5 days)
        pipe.expire(timeline_key, 432000)
    
    # Execute pipeline
    await pipe.execute()
    
    
async def get_timeline_from_redis(user_id: UUID, limit: int = 20, start_idx: int = 0) -> List[Dict]:
    """
    Get timeline directly from Redis for maximum performance
    using proper deserialization via Pydantic models
    """
    if not redis_client:
        return await get_home_timeline(user_id, limit)
        
    timeline_key = f"timeline:{user_id}"
    
    # Get posts from Redis list
    end_idx = start_idx + limit - 1
    posts_json = await redis_client.lrange(timeline_key, start_idx, end_idx)
    
    if not posts_json:
        # If Redis doesn't have the timeline, load it from the database
        posts = await get_user_timeline_posts(user_id, limit)
        
        # Store in Redis for future requests
        if posts:
            from src.schemas.schemas import RedisPost
            pipe = redis_client.pipeline()
            for post in posts:
                redis_post = RedisPost.from_dict(post)
                serialized_post = redis_post.to_redis()
                pipe.rpush(timeline_key, serialized_post)
            pipe.expire(timeline_key, 432000)  # 5 days expiry
            await pipe.execute()
        
        return posts
    
    # Parse and deserialize posts using our Pydantic models
    from src.schemas.schemas import RedisPost
    parsed_posts = []
    
    for post_json in posts_json:
        try:
            # Use our RedisPost model to properly deserialize the data
            redis_post = RedisPost.from_redis(post_json)
            if redis_post:
                parsed_posts.append(redis_post.dict())
        except Exception as e:
            import logging
            logging.error(f"Error parsing post from Redis: {e}")
            continue
    
    return parsed_posts


async def get_explore_feed(user_id: UUID, limit: int = 20, offset: int = 0) -> list[Dict]:
    """
    Get explore/discover feed - posts from users you don't follow

    This is optimized to show:
    1. Popular content from verified or well-followed accounts
    2. Content with high engagement
    3. Content that's trending
    4. A mix of new and established content to promote discovery
    """
    async with pool.acquire() as conn:
        # Get followed users to exclude
        followed_ids_query = """
            SELECT followee_id FROM follows WHERE follower_id = $1
        """
        followed_rows = await conn.fetch(followed_ids_query, user_id)
        followed_ids = [row["followee_id"] for row in followed_rows]

        # Add the user's own ID to exclude
        followed_ids.append(user_id)

        # Build the exclusion list for the query
        exclusion_ids = followed_ids if followed_ids else [user_id]

        # Optimized query to get popular content from non-followed users
        # This uses a scoring algorithm based on engagement metrics
        query = """
        SELECT
            p.id, p.content, p.media_urls, p.like_count, p.comment_count,
            p.repost_count, p.is_repost, p.original_post_id, p.created_at,
            u.id as user_id, u.username, u.profile_picture_url,
            u.follower_count,
            (p.like_count * 1.0 + p.comment_count * 1.5 + p.repost_count * 2.0) *
            (1.0 + (extract(epoch from now()) - extract(epoch from p.created_at))::float / 86400.0)^(-0.8)
            as score
        FROM posts p
        JOIN users u ON p.user_id = u.id
        WHERE p.user_id != ALL($1::uuid[])
          AND p.original_post_id IS NULL
          AND p.created_at > now() - interval '7 days'
        ORDER BY score DESC
        LIMIT $2 OFFSET $3
        """

        rows = await conn.fetch(query, exclusion_ids, limit, offset)

        # Process results
        posts = []
        for row in rows:
            post = dict(row)
            if post["media_urls"] is not None:
                post["media_urls"] = list(post["media_urls"])
            # Remove the score from the result
            post.pop("score", None)
            posts.append(post)

        return posts


async def get_trending_topics() -> list[Dict]:
    """Get trending topics/hashtags"""
    # In a real implementation, this would analyze post content
    # and extract trending hashtags or topics

    # Simulated trending topics for demonstration
    topics = [
        {"name": "#Technology", "post_count": random.randint(1000, 10000)},
        {"name": "#AI", "post_count": random.randint(1000, 10000)},
        {"name": "#Python", "post_count": random.randint(1000, 10000)},
        {"name": "#DataScience", "post_count": random.randint(1000, 10000)},
        {"name": "#MachineLearning", "post_count": random.randint(1000, 10000)},
        {"name": "#WebDev", "post_count": random.randint(1000, 10000)},
        {"name": "#Programming", "post_count": random.randint(1000, 10000)},
        {"name": "#Cloud", "post_count": random.randint(1000, 10000)},
        {"name": "#DevOps", "post_count": random.randint(1000, 10000)},
        {"name": "#OpenSource", "post_count": random.randint(1000, 10000)},
    ]

    # Sort by post count
    topics.sort(key=lambda x: x["post_count"], reverse=True)

    return topics


async def get_trending_posts(limit: int = 20) -> list[Dict]:
    """Get trending posts"""
    # Try to get from cache first
    cached_trending = await get_cached_trending_posts()
    if cached_trending:
        return cached_trending[:limit]

    # If not in cache, get from database
    async with pool.acquire() as conn:
        # This query finds trending posts based on recent engagement
        query = """
        SELECT
            p.id, p.content, p.media_urls, p.like_count, p.comment_count,
            p.repost_count, p.is_repost, p.original_post_id, p.created_at,
            u.id as user_id, u.username, u.profile_picture_url
        FROM posts p
        JOIN users u ON p.user_id = u.id
        WHERE p.created_at > now() - interval '24 hours'
          AND p.original_post_id IS NULL
        ORDER BY (p.like_count + p.comment_count * 3 + p.repost_count * 5) DESC
        LIMIT $1
        """

        rows = await conn.fetch(query, limit)

        # Process results
        posts = []
        for row in rows:
            post = dict(row)
            if post["media_urls"] is not None:
                post["media_urls"] = list(post["media_urls"])
            posts.append(post)

        # Cache the result
        await cache_trending_posts(posts)

        return posts
