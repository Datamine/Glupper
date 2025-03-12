import logging
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from src.core.cache import (
    cache_post,
    get_cached_post,
    invalidate_post_cache,
)
from src.core.db import get_post_with_comments, pool
from src.services.archive_service import get_archived_urls_for_post, process_post_urls
from src.services.feed_service import push_post_to_timelines

logger = logging.getLogger(__name__)


async def create_post(user_id: UUID, title: str, url: str, media_urls: Optional[list[str]] = None) -> dict:
    """Create a new post with title and URL"""
    post_id = uuid4()
    now = datetime.now()

    if media_urls is None:
        media_urls = []

    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO posts (
                id, user_id, title, url, content, media_urls, created_at, updated_at, is_comment
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        """,
            post_id,
            user_id,
            title,
            url,
            None,  # content is null for top-level posts
            media_urls,
            now,
            now,
            False,
        )

        # Get the complete post with user info
        post = await conn.fetchrow(
            """
            SELECT
                p.id, p.title, p.url, p.content, p.media_urls, p.like_count, p.comment_count,
                p.repost_count, p.is_repost, p.original_post_id, p.parent_post_id, p.is_comment, p.created_at,
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

    # Queue URL for archiving
    # This will add the URL to the SQS queue for processing by the archivebox server
    await process_post_urls(
        post_id=post_id,
        user_id=user_id,
        content=url,  # for top-level posts, primarily archive the URL
        media_urls=media_urls or [],
        title=title,  # pass the title for better archiving
    )

    # Add archive status to the response
    # This will initially show pending status
    archive_status = await get_archive_status(post_id)
    if archive_status:
        result["archive_status"] = archive_status

    # Use fanout-on-write to push the post to all followers' timelines in Redis
    # This is a much more efficient approach than invalidating caches
    full_post = {
        "id": post_id,
        "user_id": user_id,
        "title": title,
        "url": url,
        "content": None,
        "media_urls": media_urls or [],
        "like_count": 0,
        "comment_count": 0,
        "repost_count": 0,
        "is_repost": False,
        "is_comment": False,
        "parent_post_id": None,
        "original_post_id": None,
        "created_at": now.isoformat(),
        "username": result["username"],
        "profile_picture_url": result["profile_picture_url"],
    }

    # Push to Redis in the background (don't await)
    push_post_to_timelines(full_post, user_id)

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

    # Get archived URLs for the post (only completed ones)
    archived_urls = await get_archived_urls_for_post(post_id)
    if archived_urls:
        post["archived_urls"] = archived_urls

    # Also get archive status for all URLs (including pending ones)
    archive_status = await get_archive_status(post_id)
    if archive_status:
        post["archive_status"] = archive_status

    # Cache the result
    await cache_post(post_id, post)

    return post


async def delete_post(post_id: UUID) -> bool:
    """Delete a post and its archives"""
    try:
        # Delete the post from the database
        # This will cascade to likes, comments, etc.
        async with pool.acquire() as conn:
            await conn.execute(
                """
                DELETE FROM posts
                WHERE id = $1
                """,
                post_id,
            )

        # Delete archives for this post
        await delete_archives_for_post(post_id)

        # Invalidate cache
        await invalidate_post_cache(post_id)
        return True
    except Exception:
        logger.exception(f"Error deleting post {post_id}")
        return False


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

    async with pool.acquire() as conn, conn.transaction():
            # First check if original post exists
            post_exists = await conn.fetchval("SELECT 1 FROM posts WHERE id = $1", post_id)
            if not post_exists:
                return None

            # Create the comment as a post with parent_post_id set and is_comment=True
            await conn.execute(
                """
                INSERT INTO posts (
                    id, user_id, title, url, content, media_urls,
                    parent_post_id, created_at, updated_at, is_comment
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            """,
                comment_id,
                user_id,
                None,  # title is null for comments
                None,  # url is null for comments
                content,
                media_urls,
                post_id,
                now,
                now,
                True,
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
                    p.id, p.title, p.url, p.content, p.media_urls, p.like_count, p.comment_count,
                    p.repost_count, p.is_repost, p.original_post_id, p.parent_post_id, p.is_comment, p.created_at,
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
    process_post_urls(
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

    async with pool.acquire() as conn, conn.transaction():
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
    async with pool.acquire() as conn, conn.transaction():
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

    async with pool.acquire() as conn, conn.transaction():
            # Check if original post exists and get author info
            original_post = await conn.fetchrow(
                """
                SELECT p.id, p.user_id, p.title, p.url, p.content, p.media_urls, p.is_comment,
                       u.username as original_username, u.profile_picture_url as original_profile_picture_url
                FROM posts p
                JOIN users u ON p.user_id = u.id
                WHERE p.id = $1
            """,
                original_post_id,
            )

            if not original_post:
                return None

            # Cannot repost a comment
            if original_post["is_comment"]:
                return None

            # Cannot repost your own post
            if original_post["user_id"] == user_id:
                return None

            # Check if already reposted by this user
            existing_repost = await conn.fetchval(
                """
                SELECT 1 FROM posts
                WHERE user_id = $1 AND original_post_id = $2 AND is_repost = TRUE
                """,
                user_id,
                original_post_id,
            )

            if existing_repost:
                return None

            # Create repost record - keep the same structure as the original post
            # We need to add original_user_id, original_username, and original_profile_picture_url
            # But the database schema doesn't have these columns yet, so we'll include them in the response later
            await conn.execute(
                """
                INSERT INTO posts (
                    id, user_id, title, url, content, media_urls,
                    is_repost, original_post_id, is_comment, created_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            """,
                repost_id,
                user_id,
                original_post["title"],
                original_post["url"],
                original_post["content"],
                original_post["media_urls"],
                True,
                original_post_id,
                False,
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
                    p.id, p.title, p.url, p.content, p.media_urls, p.like_count, p.comment_count,
                    p.repost_count, p.is_repost, p.is_comment, p.original_post_id, p.parent_post_id, p.created_at,
                    u.username, u.profile_picture_url
                FROM posts p
                JOIN users u ON p.user_id = u.id
                WHERE p.id = $1
            """,
                repost_id,
            )

    # Invalidate cache for the original post
    await invalidate_post_cache(original_post_id)

    # Construct response
    result = dict(repost)
    if result["media_urls"] is not None:
        result["media_urls"] = list(result["media_urls"])

    # Add original author info to result
    result["original_user_id"] = original_post["user_id"]
    result["original_username"] = original_post["original_username"]
    result["original_profile_picture_url"] = original_post["original_profile_picture_url"]

    # Use fanout-on-write to push the repost to all followers' timelines in Redis
    full_post = {
        "id": repost_id,
        "user_id": user_id,
        "title": result["title"],
        "url": result["url"],
        "content": result["content"],
        "media_urls": result["media_urls"] or [],
        "like_count": 0,
        "comment_count": 0,
        "repost_count": 0,
        "is_repost": True,
        "is_comment": False,
        "original_post_id": original_post_id,
        "original_user_id": original_post["user_id"],
        "original_username": original_post["original_username"],
        "original_profile_picture_url": original_post["original_profile_picture_url"],
        "parent_post_id": None,
        "created_at": now.isoformat(),
        "username": result["username"],
        "profile_picture_url": result["profile_picture_url"],
    }

    # Push to Redis in the background (don't await)
    push_post_to_timelines(full_post, user_id)

    # Archive URLs in background (don't await)
    process_post_urls(
        post_id=repost_id,
        user_id=user_id,
        content=original_post["url"] or original_post["content"],
        media_urls=original_post["media_urls"] or [],
    )

    return result


async def get_user_posts(user_id: UUID, limit: int = 20, offset: int = 0) -> list[dict]:
    """Get posts created by a user"""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                p.id, p.title, p.url, p.content, p.media_urls, p.like_count, p.comment_count,
                p.repost_count, p.is_repost, p.is_comment, p.original_post_id, p.parent_post_id, p.created_at,
                u.username, u.profile_picture_url
            FROM posts p
            JOIN users u ON p.user_id = u.id
            WHERE p.user_id = $1 AND p.is_comment = FALSE
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


async def get_user_liked_posts(
    user_id: UUID, limit: int = 20, cursor: Optional[UUID] = None,
) -> tuple[list[dict], Optional[UUID]]:
    """
    Get posts that a user has liked with cursor-based pagination

    Returns a tuple of (posts, next_cursor) where next_cursor is None if there are no more posts
    """
    async with pool.acquire() as conn:
        # Prepare the base query
        query_parts = [
            """
            WITH liked_posts AS (
                SELECT
                    p.id, p.title, p.url, p.content, p.media_urls, p.like_count, p.comment_count,
                    p.repost_count, p.is_repost, p.is_comment, p.original_post_id, p.parent_post_id, p.created_at,
                    p.user_id as post_author_id, u.username, u.profile_picture_url,
                    l.created_at as liked_at
                FROM likes l
                JOIN posts p ON l.post_id = p.id
                JOIN users u ON p.user_id = u.id
                WHERE l.user_id = $1
            """,
        ]

        # Add cursor condition if provided
        params = [user_id, limit]
        if cursor:
            query_parts.append(
                """
                AND (
                    l.created_at < (SELECT created_at FROM likes WHERE user_id = $1 AND post_id = $3)
                    OR (
                        l.created_at = (SELECT created_at FROM likes WHERE user_id = $1 AND post_id = $3)
                        AND l.post_id < $3
                    )
                )
                """,
            )
            params.append(cursor)

        # Complete the query with ordering and limit
        query_parts.append(
            """
            ORDER BY l.created_at DESC, l.post_id DESC
            LIMIT $2
            )
            SELECT * FROM liked_posts
            """,
        )

        # Execute the query
        full_query = "\n".join(query_parts)
        rows = await conn.fetch(full_query, *params)

        # Process the results
        posts = []
        for row in rows:
            post = dict(row)
            if post["media_urls"] is not None:
                post["media_urls"] = list(post["media_urls"])

            # Mark as liked by the user (since these are all liked posts)
            post["liked_by_user"] = True

            # Get archived URLs for each post
            archived_urls = await get_archived_urls_for_post(post["id"])
            if archived_urls:
                post["archived_urls"] = archived_urls

            # For reposts, enhance with original post information
            if post["is_repost"] and post["original_post_id"]:
                original_post_info = await conn.fetchrow(
                    """
                    SELECT
                        u.id as original_user_id,
                        u.username as original_username,
                        u.profile_picture_url as original_profile_picture_url
                    FROM posts p
                    JOIN users u ON p.user_id = u.id
                    WHERE p.id = $1
                    """,
                    post["original_post_id"],
                )

                if original_post_info:
                    post.update(dict(original_post_info))

            posts.append(post)

        # Determine the next cursor
        next_cursor = None
        if len(posts) == limit:
            next_cursor = posts[-1]["id"]

        return posts, next_cursor
