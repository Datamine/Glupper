from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from src.core.cache import (
    cache_post,
    get_cached_post,
    invalidate_post_cache,
    invalidate_user_timeline,
)
from src.core.db import get_post_with_comments, pool
from src.services.archive_service import get_archived_urls_for_post, process_post_urls


async def create_post(user_id: UUID, content: str, media_urls: Optional[list[str]] = None) -> dict:
    """Create a new post"""
    post_id = uuid4()
    now = datetime.now()

    if media_urls is None:
        media_urls = []

    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO posts (
                id, user_id, content, media_urls, created_at, updated_at
            ) VALUES ($1, $2, $3, $4, $5, $6)
        """,
            post_id,
            user_id,
            content,
            media_urls,
            now,
            now,
        )

        # Get the complete post with user info
        post = await conn.fetchrow(
            """
            SELECT
                p.id, p.content, p.media_urls, p.like_count, p.comment_count,
                p.repost_count, p.is_repost, p.original_post_id, p.created_at,
                u.username, u.profile_picture_url
            FROM posts p
            JOIN users u ON p.user_id = u.id
            WHERE p.id = $1
        """,
            post_id,
        )

    # Construct response
    result = dict(post)
    if result["media_urls"] is not None:
        result["media_urls"] = list(result["media_urls"])

    # Archive URLs in background (don't await)
    # We don't want to block the post creation on archiving
    # This task will run in the background
    process_task = process_post_urls(
        post_id=post_id,
        user_id=user_id,
        content=content,
        media_urls=media_urls or [],
    )

    # Invalidate timelines for followers
    # This would be better done with a background task in production
    async with pool.acquire() as conn:
        follower_rows = await conn.fetch(
            """
            SELECT follower_id FROM follows WHERE followee_id = $1
        """,
            user_id,
        )

    for row in follower_rows:
        await invalidate_user_timeline(row["follower_id"])

    return result


async def get_post(post_id: UUID) -> Optional[dict]:
    """Get a post by ID with caching"""
    # Try to get from cache first
    cached_post = await get_cached_post(post_id)
    if cached_post:
        return cached_post

    # If not in cache, get from database
    post = await get_post_with_comments(post_id)
    if not post:
        return None

    # Get archived URLs for the post
    archived_urls = await get_archived_urls_for_post(post_id)
    if archived_urls:
        post["archived_urls"] = archived_urls

    # Cache the result
    await cache_post(post_id, post)

    return post


async def create_comment(
    user_id: UUID,
    post_id: UUID,
    content: str,
    media_urls: Optional[list[str]] = None,
) -> Optional[dict]:
    """Create a comment on a post (which is itself a post)"""
    comment_id = uuid4()
    now = datetime.now()

    if media_urls is None:
        media_urls = []

    async with pool.acquire() as conn:
        async with conn.transaction():
            # First check if original post exists
            post_exists = await conn.fetchval("SELECT 1 FROM posts WHERE id = $1", post_id)
            if not post_exists:
                return None

            # Create the comment as a post with original_post_id set
            await conn.execute(
                """
                INSERT INTO posts (
                    id, user_id, content, media_urls,
                    original_post_id, created_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
                comment_id,
                user_id,
                content,
                media_urls,
                post_id,
                now,
                now,
            )

            # Increment comment count on original post
            await conn.execute(
                """
                UPDATE posts
                SET comment_count = comment_count + 1, updated_at = $2
                WHERE id = $1
            """,
                post_id,
                now,
            )

            # Get the complete comment with user info
            comment = await conn.fetchrow(
                """
                SELECT
                    p.id, p.content, p.media_urls, p.like_count, p.comment_count,
                    p.repost_count, p.is_repost, p.original_post_id, p.created_at,
                    u.username, u.profile_picture_url
                FROM posts p
                JOIN users u ON p.user_id = u.id
                WHERE p.id = $1
            """,
                comment_id,
            )

    # Invalidate cache for the original post
    await invalidate_post_cache(post_id)

    # Construct response
    result = dict(comment)
    if result["media_urls"] is not None:
        result["media_urls"] = list(result["media_urls"])

    # Archive URLs in background (don't await)
    process_task = process_post_urls(
        post_id=comment_id,
        user_id=user_id,
        content=content,
        media_urls=media_urls or [],
    )

    return result


async def like_post(user_id: UUID, post_id: UUID) -> bool:
    """Like a post"""
    like_id = uuid4()
    now = datetime.now()

    async with pool.acquire() as conn:
        async with conn.transaction():
            # Check if already liked
            existing = await conn.fetchval(
                """
                SELECT id FROM likes
                WHERE user_id = $1 AND post_id = $2
            """,
                user_id,
                post_id,
            )

            if existing:
                return False

            # Create like record
            await conn.execute(
                """
                INSERT INTO likes (id, user_id, post_id, created_at)
                VALUES ($1, $2, $3, $4)
            """,
                like_id,
                user_id,
                post_id,
                now,
            )

            # Increment like count
            await conn.execute(
                """
                UPDATE posts
                SET like_count = like_count + 1, updated_at = $2
                WHERE id = $1
            """,
                post_id,
                now,
            )

    # Invalidate cache for the post
    await invalidate_post_cache(post_id)

    return True


async def unlike_post(user_id: UUID, post_id: UUID) -> bool:
    """Unlike a post"""
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Check if liked
            existing = await conn.fetchval(
                """
                SELECT id FROM likes
                WHERE user_id = $1 AND post_id = $2
            """,
                user_id,
                post_id,
            )

            if not existing:
                return False

            # Delete like record
            await conn.execute(
                """
                DELETE FROM likes
                WHERE user_id = $1 AND post_id = $2
            """,
                user_id,
                post_id,
            )

            # Decrement like count
            now = datetime.now()
            await conn.execute(
                """
                UPDATE posts
                SET like_count = greatest(like_count - 1, 0), updated_at = $2
                WHERE id = $1
            """,
                post_id,
                now,
            )

    # Invalidate cache for the post
    await invalidate_post_cache(post_id)

    return True


async def repost(user_id: UUID, original_post_id: UUID) -> Optional[dict]:
    """Repost (share) another post"""
    repost_id = uuid4()
    now = datetime.now()

    async with pool.acquire() as conn:
        async with conn.transaction():
            # Check if original post exists
            original_post = await conn.fetchrow(
                """
                SELECT id, content, media_urls FROM posts WHERE id = $1
            """,
                original_post_id,
            )

            if not original_post:
                return None

            # Create repost record
            await conn.execute(
                """
                INSERT INTO posts (
                    id, user_id, content, media_urls,
                    is_repost, original_post_id, created_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
                repost_id,
                user_id,
                original_post["content"],
                original_post["media_urls"],
                True,
                original_post_id,
                now,
                now,
            )

            # Increment repost count on original post
            await conn.execute(
                """
                UPDATE posts
                SET repost_count = repost_count + 1, updated_at = $2
                WHERE id = $1
            """,
                original_post_id,
                now,
            )

            # Get the complete repost with user info
            repost = await conn.fetchrow(
                """
                SELECT
                    p.id, p.content, p.media_urls, p.like_count, p.comment_count,
                    p.repost_count, p.is_repost, p.original_post_id, p.created_at,
                    u.username, u.profile_picture_url
                FROM posts p
                JOIN users u ON p.user_id = u.id
                WHERE p.id = $1
            """,
                repost_id,
            )

    # Invalidate cache for the original post
    await invalidate_post_cache(original_post_id)

    # Invalidate timelines for followers
    async with pool.acquire() as conn:
        follower_rows = await conn.fetch(
            """
            SELECT follower_id FROM follows WHERE followee_id = $1
        """,
            user_id,
        )

    for row in follower_rows:
        await invalidate_user_timeline(row["follower_id"])

    # Construct response
    result = dict(repost)
    if result["media_urls"] is not None:
        result["media_urls"] = list(result["media_urls"])

    # We need to get the content and media_urls for the archive process
    content = original_post["content"]
    media_urls = original_post["media_urls"]
    if media_urls is not None:
        media_urls = list(media_urls)
    else:
        media_urls = []

    # Archive URLs in background (don't await)
    process_task = process_post_urls(
        post_id=repost_id,
        user_id=user_id,
        content=content,
        media_urls=media_urls,
    )

    return result


async def get_user_posts(user_id: UUID, limit: int = 20, offset: int = 0) -> list[dict]:
    """Get posts created by a user"""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                p.id, p.content, p.media_urls, p.like_count, p.comment_count,
                p.repost_count, p.is_repost, p.original_post_id, p.created_at,
                u.username, u.profile_picture_url
            FROM posts p
            JOIN users u ON p.user_id = u.id
            WHERE p.user_id = $1 AND p.original_post_id IS NULL
            ORDER BY p.created_at DESC
            LIMIT $2 OFFSET $3
        """,
            user_id,
            limit,
            offset,
        )

    result = []
    for row in rows:
        post = dict(row)
        if post["media_urls"] is not None:
            post["media_urls"] = list(post["media_urls"])

        # Get archived URLs for each post
        archived_urls = await get_archived_urls_for_post(post["id"])
        if archived_urls:
            post["archived_urls"] = archived_urls

        result.append(post)

    return result
