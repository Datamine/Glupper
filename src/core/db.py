from typing import Any, Optional
from uuid import UUID

import asyncpg
from asyncpg import Connection, Pool

from src.config_secrets import DATABASE_URL

# Database connection pool
pool: Optional[Pool] = None


async def init_db():
    """Initialize database connection pool"""
    global pool
    pool = await asyncpg.create_pool(
        DATABASE_URL,
        min_size=10,
        max_size=100,  # High connection count for performance
    )

    # Initialize database schema
    await _create_tables()


async def close_db():
    """Close database connection pool"""
    global pool
    if pool:
        await pool.close()


async def get_connection() -> Connection:
    """Get a connection from the pool"""
    if pool is None:
        await init_db()
    assert pool is not None
    return await pool.acquire()


async def release_connection(conn: Connection):
    """Release a connection back to the pool"""
    if pool:
        await pool.release(conn)


# Create tables
async def _create_tables():
    """Create database tables if they don't exist"""
    async with pool.acquire() as conn:
        # Users table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id UUID PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                bio TEXT,
                profile_picture_url TEXT,
                follower_count INTEGER DEFAULT 0,
                following_count INTEGER DEFAULT 0,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
        """)

        # Posts table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                id UUID PRIMARY KEY,
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                title TEXT,
                url TEXT,
                content TEXT,
                media_urls TEXT[] DEFAULT '{}',
                like_count INTEGER DEFAULT 0,
                comment_count INTEGER DEFAULT 0,
                repost_count INTEGER DEFAULT 0,
                is_repost BOOLEAN DEFAULT FALSE,
                is_comment BOOLEAN DEFAULT FALSE,
                original_post_id UUID REFERENCES posts(id),
                parent_post_id UUID REFERENCES posts(id),
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL,
                CONSTRAINT post_content_check CHECK (
                    (is_comment = TRUE AND content IS NOT NULL AND title IS NULL AND url IS NULL) OR
                    (is_comment = FALSE AND title IS NOT NULL AND url IS NOT NULL AND content IS NULL) OR
                    (is_repost = TRUE)
                )
            );
            CREATE INDEX IF NOT EXISTS idx_posts_user_id ON posts(user_id);
            CREATE INDEX IF NOT EXISTS idx_posts_created_at ON posts(created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_posts_parent_id ON posts(parent_post_id);
        """)

        # Likes table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS likes (
                id UUID PRIMARY KEY,
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                post_id UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
                created_at TIMESTAMP NOT NULL,
                UNIQUE(user_id, post_id)
            );
            CREATE INDEX IF NOT EXISTS idx_likes_post_id ON likes(post_id);
            CREATE INDEX IF NOT EXISTS idx_likes_user_id ON likes(user_id);
        """)

        # Follows table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS follows (
                id UUID PRIMARY KEY,
                follower_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                followee_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created_at TIMESTAMP NOT NULL,
                UNIQUE(follower_id, followee_id)
            );
            CREATE INDEX IF NOT EXISTS idx_follows_follower_id ON follows(follower_id);
            CREATE INDEX IF NOT EXISTS idx_follows_followee_id ON follows(followee_id);
        """)
        
        # Mutes table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS mutes (
                id UUID PRIMARY KEY,
                muter_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                muted_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created_at TIMESTAMP NOT NULL,
                UNIQUE(muter_id, muted_id)
            );
            CREATE INDEX IF NOT EXISTS idx_mutes_muter_id ON mutes(muter_id);
            CREATE INDEX IF NOT EXISTS idx_mutes_muted_id ON mutes(muted_id);
        """)

        # Archived URLs table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS archived_urls (
                id SERIAL PRIMARY KEY,
                post_id UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
                original_url TEXT NOT NULL,
                archive_id TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL,
                UNIQUE(post_id, original_url)
            );
            CREATE INDEX IF NOT EXISTS idx_archived_urls_post_id ON archived_urls(post_id);
            CREATE INDEX IF NOT EXISTS idx_archived_urls_original_url ON archived_urls(original_url);
            CREATE INDEX IF NOT EXISTS idx_archived_urls_archive_id ON archived_urls(archive_id);
        """)
        
        # Messages table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id UUID PRIMARY KEY,
                sender_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                recipient_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                content TEXT NOT NULL,
                is_read BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_messages_sender_id ON messages(sender_id);
            CREATE INDEX IF NOT EXISTS idx_messages_recipient_id ON messages(recipient_id);
            CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(
                LEAST(sender_id, recipient_id),
                GREATEST(sender_id, recipient_id)
            );
            CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at DESC);
        """)


# High-performance query functions
async def get_user_timeline_posts(
    user_id: UUID,
    limit: int = 20,
    before_id: Optional[UUID] = None,
) -> list[dict[str, Any]]:
    """
    Get timeline posts for a user - highly optimized query

    This uses a complex but efficient query that:
    1. Fetches posts from followed users + own posts
    2. Excludes posts from muted users
    3. Uses cursor-based pagination for performance
    4. Includes necessary post metadata in a single query
    """
    async with pool.acquire() as conn:
        # Subquery to get IDs of users being followed and muted users
        query = """
        WITH followed_users AS (
            SELECT followee_id FROM follows WHERE follower_id = $1
        ),
        muted_users AS (
            SELECT muted_id FROM mutes WHERE muter_id = $1
        )
        SELECT
            p.id, p.title, p.url, p.content, p.media_urls, p.like_count, p.comment_count,
            p.repost_count, p.is_repost, p.is_comment, p.original_post_id, p.parent_post_id, p.created_at,
            u.id as user_id, u.username, u.profile_picture_url,
            EXISTS(SELECT 1 FROM likes WHERE post_id = p.id AND user_id = $1) as liked_by_user
        FROM posts p
        JOIN users u ON p.user_id = u.id
        WHERE (p.user_id IN (SELECT followee_id FROM followed_users)
           OR p.user_id = $1)
           AND p.user_id NOT IN (SELECT muted_id FROM muted_users)  -- Exclude muted users
           AND p.is_comment = FALSE
        """

        params = [user_id, limit]

        # Add cursor-based pagination if a before_id is provided
        if before_id:
            query += """
            AND (
                p.created_at < (SELECT created_at FROM posts WHERE id = $3)
                OR (p.created_at = (SELECT created_at FROM posts WHERE id = $3) AND p.id < $3)
            )
            """
            params.append(before_id)

        query += """
        ORDER BY p.created_at DESC, p.id DESC
        LIMIT $2
        """

        result = await conn.fetch(query, *params)

        # Convert the results to a list of dictionaries
        posts = []
        for row in result:
            post = dict(row)
            # Parse the media_urls from PostgreSQL array to Python list
            if post["media_urls"] is not None:
                post["media_urls"] = list(post["media_urls"])

            # Get archived URLs for this post
            archived_urls_rows = await conn.fetch(
                """
                SELECT original_url, archived_url
                FROM archived_urls
                WHERE post_id = $1
            """,
                post["id"],
            )

            if archived_urls_rows:
                post["archived_urls"] = {row["original_url"]: row["archived_url"] for row in archived_urls_rows}

            posts.append(post)

        return posts


async def get_post_with_comments(post_id: UUID, limit: int = 20, offset: int = 0) -> dict[str, Any]:
    """Get a post with its comments in a single efficient query"""
    async with pool.acquire() as conn:
        # Get the post with user info
        post_query = """
        SELECT
            p.id, p.title, p.url, p.content, p.media_urls, p.like_count, p.comment_count,
            p.repost_count, p.is_repost, p.is_comment, p.original_post_id, p.parent_post_id, p.created_at,
            u.id as user_id, u.username, u.profile_picture_url
        FROM posts p
        JOIN users u ON p.user_id = u.id
        WHERE p.id = $1
        """

        post_row = await conn.fetchrow(post_query, post_id)
        if not post_row:
            return {}

        post = dict(post_row)
        if post["media_urls"] is not None:
            post["media_urls"] = list(post["media_urls"])

        # Get archived URLs for this post
        archived_urls_rows = await conn.fetch(
            """
            SELECT original_url, archived_url
            FROM archived_urls
            WHERE post_id = $1
        """,
            post_id,
        )

        if archived_urls_rows:
            post["archived_urls"] = {row["original_url"]: row["archived_url"] for row in archived_urls_rows}

        # Get comments for this post
        comments_query = """
        SELECT
            p.id, p.title, p.url, p.content, p.media_urls, p.like_count, p.comment_count,
            p.repost_count, p.is_repost, p.is_comment, p.original_post_id, p.parent_post_id, p.created_at,
            u.id as user_id, u.username, u.profile_picture_url
        FROM posts p
        JOIN users u ON p.user_id = u.id
        WHERE p.parent_post_id = $1 AND p.is_comment = TRUE
        ORDER BY p.created_at DESC
        LIMIT $2 OFFSET $3
        """

        comments_rows = await conn.fetch(comments_query, post_id, limit, offset)
        comments = []
        for row in comments_rows:
            comment = dict(row)
            if comment["media_urls"] is not None:
                comment["media_urls"] = list(comment["media_urls"])

            # Get archived URLs for each comment
            comment_archived_urls_rows = await conn.fetch(
                """
                SELECT original_url, archived_url
                FROM archived_urls
                WHERE post_id = $1
            """,
                comment["id"],
            )

            if comment_archived_urls_rows:
                comment["archived_urls"] = {
                    row["original_url"]: row["archived_url"] for row in comment_archived_urls_rows
                }

            comments.append(comment)

        post["comments"] = comments
        return post
