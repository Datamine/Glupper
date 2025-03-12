import random
from typing import Literal, Optional
from uuid import UUID

from src.core.cache import (
    cache_trending_posts,
    cache_user_timeline,
    get_cached_timeline,
    get_cached_trending_posts,
    redis_client,
)
from src.core.db import get_user_timeline_posts, pool


async def enhance_reposts_with_original_info(posts: list[dict]) -> list[dict]:
    """
    Enhance reposts with information about the original post and author.

    For each repost, fetch the original post author information and add it
    to the repost data structure to make it easier for UIs to display both
    the person who reposted and the original author.
    """
    if not posts:
        return posts

    # Find all reposts and gather original post IDs
    repost_indices = []
    original_post_ids = []

    for i, post in enumerate(posts):
        if post.get("is_repost") and post.get("original_post_id"):
            repost_indices.append(i)
            original_post_ids.append(post["original_post_id"])

    if not original_post_ids:
        return posts

    # Get original post info in a single query
    async with pool.acquire() as conn:
        query = """
        SELECT
            p.id, u.username as original_username, u.profile_picture_url as original_profile_picture_url,
            u.id as original_user_id
        FROM posts p
        JOIN users u ON p.user_id = u.id
        WHERE p.id = ANY($1)
        """
        rows = await conn.fetch(query, original_post_ids)

        # Create mapping of original post ID to author info
        original_info = {}
        for row in rows:
            original_info[row["id"]] = {
                "original_username": row["original_username"],
                "original_profile_picture_url": row["original_profile_picture_url"],
                "original_user_id": row["original_user_id"],
            }

        # Enhance reposts with original author info
        for idx in repost_indices:
            original_post_id = posts[idx]["original_post_id"]
            if original_post_id in original_info:
                posts[idx].update(original_info[original_post_id])

    return posts


async def get_home_timeline(
    user_id: UUID,
    limit: int = 20,
    before_id: Optional[UUID] = None,
    feed_type: Literal["chronological", "for_you"] = "chronological",
) -> list[dict]:
    """
    Get home timeline for a user

    This function implements a high-performance timeline algorithm that:
    1. Uses Redis as the primary data source for timeline data
    2. Falls back to database only when necessary
    3. Maintains timeline in Redis for fast access

    Parameters:
    - user_id: The ID of the user requesting the timeline
    - limit: Maximum number of posts to return
    - before_id: Optional cursor for pagination
    - feed_type: "chronological" (posts from followed users in time order) or
                "for_you" (personalized feed with recommended content)
    """
    # If requesting chronological feed, use the standard implementation
    if feed_type == "chronological":
        # Skip cache if using cursor-based pagination
        if before_id is None:
            # Try to get from cache first
            cached_timeline = await get_cached_timeline(user_id)
            if cached_timeline:
                return cached_timeline[:limit]

        # If not in cache or using pagination, get from database
        posts = await get_user_timeline_posts(user_id, limit, before_id)

        # Enhance reposts with original post information
        posts = await enhance_reposts_with_original_info(posts)

        # Cache the result if this is the first page
        if before_id is None:
            await cache_user_timeline(user_id, posts)

        return posts

    # If requesting "for you" feed, use personalized recommendations
    if feed_type == "for_you":
        return await get_for_you_feed(user_id, limit, before_id)

    # Default to chronological if invalid feed type
    return await get_home_timeline(user_id, limit, before_id, "chronological")


async def push_post_to_timelines(post: dict, author_id: UUID):
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


async def get_for_you_feed(user_id: UUID, limit: int = 20, before_id: Optional[UUID] = None) -> list[dict]:
    """
    Get personalized "For You" feed for a user

    This algorithm builds a feed that includes:
    1. Posts from followed users (like the chronological feed)
    2. Popular posts within the user's interest cluster
    3. Posts that are engaging to similar users

    The algorithm identifies interests and clusters users based on:
    - Following patterns
    - Engagement behavior (likes, comments, reposts)
    - Content similarity
    """
    async with pool.acquire() as conn:
        # Step 1: Get user's followed accounts, liked posts, and engaged content
        # to build a user interest profile
        user_profile_query = """
        WITH
        user_follows AS (
            SELECT followee_id FROM follows WHERE follower_id = $1
        ),
        user_likes AS (
            SELECT post_id FROM likes WHERE user_id = $1 ORDER BY created_at DESC LIMIT 50
        ),
        user_engaged_posts AS (
            SELECT DISTINCT p.id
            FROM posts p
            LEFT JOIN likes l ON p.id = l.post_id AND l.user_id = $1
            WHERE l.id IS NOT NULL OR p.user_id = $1
            ORDER BY p.created_at DESC
            LIMIT 100
        ),
        muted_users AS (
            SELECT muted_id FROM mutes WHERE muter_id = $1
        )
        SELECT
            -- First: gather followed users (for identifying clusters)
            ARRAY(SELECT followee_id FROM user_follows) as followed_users,
            -- Second: gather post IDs the user has liked (to find similar content)
            ARRAY(SELECT post_id FROM user_likes) as liked_posts,
            -- Third: gather user's engaged post content (to extract topics/interests)
            ARRAY(
                SELECT content FROM posts
                WHERE id IN (SELECT id FROM user_engaged_posts) AND content IS NOT NULL
            ) as engaged_content,
            -- Fourth: get muted users to exclude them
            ARRAY(SELECT muted_id FROM muted_users) as muted_users
        """

        user_profile = await conn.fetchrow(user_profile_query, user_id)

        # Extract data from the profile
        followed_users = user_profile["followed_users"] if user_profile["followed_users"] else []
        liked_posts = user_profile["liked_posts"] if user_profile["liked_posts"] else []
        muted_users = user_profile["muted_users"] if user_profile["muted_users"] else []

        # Include the user's ID in the muted list (to avoid seeing your own posts in recommendations)
        muted_users.append(user_id)

        # Step 2: Find similar users (users who follow similar accounts)
        # and prioritize their content
        similar_users_query = """
        WITH
        user_follows AS (
            SELECT followee_id FROM follows WHERE follower_id = $1
        ),
        muted_users AS (
            SELECT unnest($2::uuid[]) as user_id
        ),
        similar_users AS (
            -- Find users who follow at least 2 of the same accounts
            SELECT f.follower_id as user_id,
                   COUNT(DISTINCT f.followee_id) as shared_follows,
                   (SELECT COUNT(*) FROM user_follows) as total_follows,
                   COUNT(DISTINCT f.followee_id)::float /
                   GREATEST(1, (SELECT COUNT(*) FROM user_follows)) as similarity_score
            FROM follows f
            WHERE f.followee_id IN (SELECT followee_id FROM user_follows)
              AND f.follower_id != $1
              AND f.follower_id NOT IN (SELECT user_id FROM muted_users)
            GROUP BY f.follower_id
            HAVING COUNT(DISTINCT f.followee_id) >= 2
            ORDER BY similarity_score DESC, shared_follows DESC
            LIMIT 50
        )
        SELECT ARRAY(SELECT user_id FROM similar_users) as similar_users
        """

        similar_users_result = await conn.fetchrow(similar_users_query, user_id, muted_users)
        similar_users = (
            similar_users_result["similar_users"]
            if similar_users_result and similar_users_result["similar_users"]
            else []
        )

        # Step 3: Build the feed query with a mix of:
        # - Recent posts from followed users (chronological component)
        # - Popular posts from similar users (interest cluster)
        # - Generally trending posts that match user's interests

        # Build the pagination clause
        pagination_clause = ""
        pagination_params = [user_id, followed_users, similar_users, muted_users, limit]

        if before_id:
            pagination_clause = """
            AND (
                p.created_at < (SELECT created_at FROM posts WHERE id = $6)
                OR (p.created_at = (SELECT created_at FROM posts WHERE id = $6) AND p.id < $6)
            )
            """
            pagination_params.append(before_id)

        # The final query combines multiple content sources with a scoring system
        feed_query = f"""
        WITH
        followed_posts AS (
            -- Recent posts from followed users (chronological component)
            SELECT p.*,
                  1.0 as base_score,
                  extract(epoch from now()) - extract(epoch from p.created_at) as age_seconds
            FROM posts p
            WHERE p.user_id = ANY($2)
              AND p.is_comment = FALSE
              AND p.user_id != ALL($4)
            ORDER BY p.created_at DESC
            LIMIT 100
        ),
        similar_users_posts AS (
            -- Posts from users with similar interests
            SELECT p.*,
                  0.8 as base_score,
                  extract(epoch from now()) - extract(epoch from p.created_at) as age_seconds
            FROM posts p
            WHERE p.user_id = ANY($3)
              AND p.is_comment = FALSE
              AND p.user_id != ALL($4)
            ORDER BY
                (p.like_count * 1.0 + p.comment_count * 1.5 + p.repost_count * 2.0) DESC,
                p.created_at DESC
            LIMIT 50
        ),
        trending_posts AS (
            -- Generally trending posts that might be interesting
            SELECT p.*,
                  0.6 as base_score,
                  extract(epoch from now()) - extract(epoch from p.created_at) as age_seconds
            FROM posts p
            WHERE p.user_id != ALL($4)
              AND p.is_comment = FALSE
              AND p.created_at > now() - interval '48 hours'
              AND (p.like_count + p.comment_count * 3 + p.repost_count * 5) > 10
            ORDER BY
                (p.like_count + p.comment_count * 3 + p.repost_count * 5) DESC,
                p.created_at DESC
            LIMIT 30
        ),
        combined_posts AS (
            SELECT
                p.*,
                u.username,
                u.profile_picture_url,
                -- Score calculation based on multiple factors:
                -- 1. Base score (prioritizes followed > similar > trending)
                -- 2. Engagement score (likes, comments, reposts)
                -- 3. Recency factor (newer posts score higher)
                -- 4. For similar users, weight by similarity score
                p.base_score *
                (1.0 + (p.like_count * 0.01 + p.comment_count * 0.03 + p.repost_count * 0.05)) *
                GREATEST(0.2, 1.0 / (1.0 + p.age_seconds/86400.0)) as feed_score
            FROM (
                SELECT * FROM followed_posts
                UNION ALL
                SELECT * FROM similar_users_posts
                UNION ALL
                SELECT * FROM trending_posts
            ) p
            JOIN users u ON p.user_id = u.id
            {pagination_clause}
        ),
        final_ranked_posts AS (
            -- Get unique posts (in case they appear in multiple sources)
            SELECT DISTINCT ON (id) *
            FROM combined_posts
            ORDER BY id, feed_score DESC
        )
        SELECT
            p.id, p.content, p.media_urls, p.like_count, p.comment_count,
            p.repost_count, p.is_repost, p.original_post_id, p.parent_post_id, p.created_at,
            p.user_id, p.username, p.profile_picture_url,
            p.title, p.url,
            EXISTS(SELECT 1 FROM likes WHERE post_id = p.id AND user_id = $1) as liked_by_user
        FROM final_ranked_posts p
        ORDER BY feed_score DESC, created_at DESC
        LIMIT $5
        """

        rows = await conn.fetch(feed_query, *pagination_params)

        # Process the results
        posts = []
        for row in rows:
            post = dict(row)
            if post["media_urls"] is not None:
                post["media_urls"] = list(post["media_urls"])
            posts.append(post)

        # Enhance reposts with original post information
        return await enhance_reposts_with_original_info(posts)


async def get_timeline_from_redis(
    user_id: UUID,
    limit: int = 20,
    start_idx: int = 0,
    feed_type: Literal["chronological", "for_you"] = "chronological",
) -> list[dict]:
    """
    Get timeline directly from Redis for maximum performance
    using proper deserialization via Pydantic models

    Parameters:
    - user_id: The ID of the user requesting the timeline
    - limit: Maximum number of posts to return
    - start_idx: Index to start fetching from in Redis list
    - feed_type: "chronological" or "for_you" feed type
    """
    # For "for_you" feed, we don't use Redis caching since it's more dynamic
    if feed_type == "for_you":
        return await get_for_you_feed(user_id, limit)

    # For chronological feed, use Redis caching
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
        except Exception:
            import logging

            logging.exception("Error parsing post from Redis.")
            continue

    return parsed_posts


async def get_explore_feed(user_id: UUID, limit: int = 20, offset: int = 0) -> list[dict]:
    """
    Get explore/discover feed - posts from users you don't follow

    This is optimized to show:
    1. Popular content from verified or well-followed accounts
    2. Content with high engagement
    3. Content that's trending
    4. A mix of new and established content to promote discovery
    5. Excludes posts from muted users
    """
    async with pool.acquire() as conn:
        # Get followed users and muted users to exclude
        excluded_users_query = """
            SELECT followee_id as user_id FROM follows WHERE follower_id = $1
            UNION
            SELECT muted_id as user_id FROM mutes WHERE muter_id = $1
        """
        excluded_rows = await conn.fetch(excluded_users_query, user_id)
        excluded_ids = [row["user_id"] for row in excluded_rows]

        # Add the user's own ID to exclude
        excluded_ids.append(user_id)

        # Build the exclusion list for the query
        exclusion_ids = excluded_ids if excluded_ids else [user_id]

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


async def get_trending_topics() -> list[dict]:
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


async def get_trending_posts(limit: int = 20) -> list[dict]:
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
