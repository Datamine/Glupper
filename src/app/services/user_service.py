from datetime import UTC, datetime
from typing import Optional
from uuid import UUID, uuid4

from glupper.app.core.auth import get_password_hash
from glupper.app.core.cache import (
    cache_user_profile,
    get_cached_user_profile,
    invalidate_user_profile_cache,
)
from glupper.app.core.db import pool
from glupper.app.models.models import User

async def create_user(username: str, email: str, password: str, bio: Optional[str] = None) -> User:
    """Create a new user"""
    user_id = uuid4()
    password_hash = get_password_hash(password)
    now = datetime.now(UTC)
    
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO users (id, username, email, password_hash, bio, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
        """, user_id, username, email, password_hash, bio, now, now)
    
    return User(
        id=user_id,
        username=username,
        email=email,
        password_hash=password_hash,
        bio=bio,
        created_at=now,
        updated_at=now,
    )

async def get_user_by_id(user_id: UUID) -> Optional[dict]:
    """Get user by ID with caching"""
    # Try to get from cache first
    cached_user = await get_cached_user_profile(user_id)
    if cached_user:
        return cached_user
    
    # If not in cache, get from database
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT
                id, username, email, bio, profile_picture_url,
                follower_count, following_count, created_at, updated_at
            FROM users
            WHERE id = $1
        """, user_id)
        
    if not row:
        return None
        
    user = dict(row)
    
    # Cache the result
    await cache_user_profile(user_id, user)
    
    return user

async def get_user_by_username(username: str) -> Optional[dict]:
    """Get user by username"""
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT
                id, username, email, password_hash, bio, profile_picture_url,
                follower_count, following_count, created_at, updated_at
            FROM users
            WHERE username = $1
        """, username)
        
    if not row:
        return None
        
    return dict(row)

async def update_user_profile(user_id: UUID, update_data: dict) -> Optional[dict]:
    """Update user profile"""
    allowed_fields = ["bio", "profile_picture_url"]
    update_fields = {k: v for k, v in update_data.items() if k in allowed_fields}
    
    if not update_fields:
        return await get_user_by_id(user_id)
        
    # Build a safer query for the update
    now = datetime.now(UTC)
    
    async with pool.acquire() as conn:
        if "bio" in update_fields:
            await conn.execute(
                "UPDATE users SET bio = $2, updated_at = $3 WHERE id = $1",
                user_id, update_fields["bio"], now,
            )
        elif "profile_picture_url" in update_fields:
            await conn.execute(
                "UPDATE users SET profile_picture_url = $2, updated_at = $3 WHERE id = $1",
                user_id, update_fields["profile_picture_url"], now,
            )
        else:
            # Just update the timestamp if no valid fields
            await conn.execute(
                "UPDATE users SET updated_at = $2 WHERE id = $1",
                user_id, now,
            )
    
    # Invalidate cache for this user
    await invalidate_user_profile_cache(user_id)
    
    # Return updated user
    return await get_user_by_id(user_id)

async def get_user_followers(user_id: UUID, limit: int = 20, offset: int = 0) -> list[dict]:
    """Get users following this user"""
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT
                u.id, u.username, u.profile_picture_url, u.bio,
                u.follower_count, u.following_count
            FROM follows f
            JOIN users u ON f.follower_id = u.id
            WHERE f.followee_id = $1
            ORDER BY f.created_at DESC
            LIMIT $2 OFFSET $3
        """, user_id, limit, offset)
        
    return [dict(row) for row in rows]

async def get_user_following(user_id: UUID, limit: int = 20, offset: int = 0) -> list[dict]:
    """Get users this user is following"""
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT
                u.id, u.username, u.profile_picture_url, u.bio,
                u.follower_count, u.following_count
            FROM follows f
            JOIN users u ON f.followee_id = u.id
            WHERE f.follower_id = $1
            ORDER BY f.created_at DESC
            LIMIT $2 OFFSET $3
        """, user_id, limit, offset)
        
    return [dict(row) for row in rows]

async def follow_user(follower_id: UUID, followee_id: UUID) -> bool:
    """Follow a user"""
    if follower_id == followee_id:
        return False
    
    async with pool.acquire() as conn, conn.transaction():
        # Check if already following
        existing = await conn.fetchval("""
            SELECT id FROM follows
            WHERE follower_id = $1 AND followee_id = $2
        """, follower_id, followee_id)
        
        if existing:
            return False
            
        # Create follow relationship
        follow_id = uuid4()
        now = datetime.now(UTC)
        await conn.execute("""
            INSERT INTO follows (id, follower_id, followee_id, created_at)
            VALUES ($1, $2, $3, $4)
        """, follow_id, follower_id, followee_id, now)
        
        # Update follower and following counts
        await conn.execute("""
            UPDATE users SET following_count = following_count + 1, updated_at = $2
            WHERE id = $1
        """, follower_id, now)
        
        await conn.execute("""
            UPDATE users SET follower_count = follower_count + 1, updated_at = $2
            WHERE id = $1
        """, followee_id, now)
    
    # Invalidate user caches
    await invalidate_user_profile_cache(follower_id)
    await invalidate_user_profile_cache(followee_id)
    
    return True

async def unfollow_user(follower_id: UUID, followee_id: UUID) -> bool:
    """Unfollow a user"""
    if follower_id == followee_id:
        return False
    
    async with pool.acquire() as conn, conn.transaction():
        # Check if following
        existing = await conn.fetchval("""
            SELECT id FROM follows
            WHERE follower_id = $1 AND followee_id = $2
        """, follower_id, followee_id)
        
        if not existing:
            return False
            
        # Delete follow relationship
        await conn.execute("""
            DELETE FROM follows
            WHERE follower_id = $1 AND followee_id = $2
        """, follower_id, followee_id)
        
        # Update follower and following counts
        now = datetime.now(UTC)
        await conn.execute("""
            UPDATE users SET following_count = greatest(following_count - 1, 0), updated_at = $2
            WHERE id = $1
        """, follower_id, now)
        
        await conn.execute("""
            UPDATE users SET follower_count = greatest(follower_count - 1, 0), updated_at = $2
            WHERE id = $1
        """, followee_id, now)
    
    # Invalidate user caches
    await invalidate_user_profile_cache(follower_id)
    await invalidate_user_profile_cache(followee_id)
    
    return True
