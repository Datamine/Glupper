import base64
from typing import Annotated, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.core.auth import get_current_user
from src.core.db import pool
from src.models.models import User
from src.schemas.schemas import (
    CommentCreate,
    FeedResponse,
    PostCreate,
    PostDetailResponse,
    PostResponse,
)
from src.services.post_service import (
    create_comment,
    create_post,
    get_post,
    get_user_liked_posts,
    get_user_posts,
    like_post,
    repost,
    unlike_post,
)

router = APIRouter(prefix="/api/v1/posts", tags=["posts"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_new_post(
    post_data: PostCreate,
    current_user: Annotated[User, Depends(get_current_user)],
) -> PostResponse:
    """
    Create a new post for the authenticated user.

    Parameters:
    - **post_data**: Post with title and URL
    - **current_user**: User object from token authentication dependency

    Returns:
    - **PostResponse**: The created post

    Raises:
    - **401 Unauthorized**: If not authenticated
    - **422 Unprocessable Entity**: If title or URL is invalid

    Notes:
    - Title must be between 1 and 100 characters
    - URL must start with http:// or https://
    """
    post = await create_post(
        user_id=current_user.id,
        title=post_data.title,
        url=post_data.url,
        media_urls=None,
    )
    return post


@router.get("/{post_id}", status_code=status.HTTP_200_OK)
async def get_post_detail(post_id: UUID) -> PostDetailResponse:
    """
    Get a post by ID with its comments.

    Parameters:
    - **post_id**: UUID of the post to retrieve

    Returns:
    - **PostDetailResponse**: Post details including comments

    Raises:
    - **404 Not Found**: If post does not exist
    """
    post = await get_post(post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found",
        )
    return post


@router.post("/{post_id}/comments", status_code=status.HTTP_201_CREATED)
async def comment_on_post(
    post_id: UUID,
    comment_data: CommentCreate,
    current_user: Annotated[User, Depends(get_current_user)],
) -> PostResponse:
    """
    Create a comment on a post.

    Parameters:
    - **post_id**: UUID of the post to comment on
    - **comment_data**: Comment content and optional media URLs
    - **current_user**: User object from token authentication dependency

    Returns:
    - **PostResponse**: The created comment

    Raises:
    - **401 Unauthorized**: If not authenticated
    - **404 Not Found**: If the post does not exist
    - **422 Unprocessable Entity**: If comment content exceeds 300 characters

    Notes:
    - Comments can contain up to 300 characters of text
    """
    comment = await create_comment(
        user_id=current_user.id,
        post_id=post_id,
        content=comment_data.content,
        media_urls=comment_data.media_urls,
    )

    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found",
        )

    return comment


@router.post("/{post_id}/like", status_code=status.HTTP_200_OK)
async def like(
    post_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, bool]:
    """
    Like a post.

    Parameters:
    - **post_id**: UUID of the post to like
    - **current_user**: User object from token authentication dependency

    Returns:
    - **dict[str, bool]**: Success status of the operation

    Raises:
    - **401 Unauthorized**: If not authenticated
    """
    success = await like_post(current_user.id, post_id)
    return {"success": success}


@router.post("/{post_id}/unlike", status_code=status.HTTP_200_OK)
async def unlike(
    post_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, bool]:
    """
    Unlike a previously liked post.

    Parameters:
    - **post_id**: UUID of the post to unlike
    - **current_user**: User object from token authentication dependency

    Returns:
    - **dict[str, bool]**: Success status of the operation

    Raises:
    - **401 Unauthorized**: If not authenticated
    """
    success = await unlike_post(current_user.id, post_id)
    return {"success": success}


@router.post("/{post_id}/repost", status_code=status.HTTP_201_CREATED)
async def repost_post(
    post_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
) -> PostResponse:
    """
    Repost another user's post.

    Parameters:
    - **post_id**: UUID of the post to repost
    - **current_user**: User object from token authentication dependency

    Returns:
    - **PostResponse**: The created repost

    Raises:
    - **400 Bad Request**: If trying to repost own post or already reposted
    - **401 Unauthorized**: If not authenticated
    - **404 Not Found**: If the original post does not exist or is a comment
    """
    # First, check if the post exists and get basic info about it
    async with pool.acquire() as conn:
        post_info = await conn.fetchrow(
            """
            SELECT user_id, is_comment
            FROM posts
            WHERE id = $1
            """,
            post_id
        )

        if not post_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Post not found",
            )

        if post_info["is_comment"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot repost a comment",
            )

        if post_info["user_id"] == current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot repost your own post",
            )

        # Check if already reposted
        existing_repost = await conn.fetchval(
            """
            SELECT 1 FROM posts
            WHERE user_id = $1 AND original_post_id = $2 AND is_repost = TRUE
            """,
            current_user.id,
            post_id
        )

        if existing_repost:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You have already reposted this post",
            )

    # Now attempt to create the repost
    reposted = await repost(current_user.id, post_id)
    if not reposted:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create repost",
        )
    return reposted


@router.get("/user/{user_id}", status_code=status.HTTP_200_OK)
async def get_posts_by_user(
    user_id: UUID,
    limit: int = 20,
    offset: int = 0,
) -> list[PostResponse]:
    """
    Get posts created by a specific user.

    Parameters:
    - **user_id**: UUID of the user whose posts to retrieve
    - **limit**: Maximum number of posts to return (default: 20)
    - **offset**: Pagination offset (default: 0)

    Returns:
    - **list[PostResponse]**: List of posts by the specified user
    """
    posts = await get_user_posts(user_id, limit, offset)
    return posts


@router.get("/likes", status_code=status.HTTP_200_OK)
async def get_liked_posts(
    current_user: Annotated[User, Depends(get_current_user)],
    cursor: Optional[str] = None,
    limit: int = Query(20, ge=1, le=50),
) -> FeedResponse:
    """
    Get posts that the authenticated user has liked.

    Parameters:
    - **cursor**: Optional base64 encoded UUID cursor for pagination
    - **limit**: Maximum number of posts to return (default: 20, min: 1, max: 50)
    - **current_user**: User object from token authentication dependency

    Returns:
    - **FeedResponse**: List of liked posts and pagination cursor

    Raises:
    - **401 Unauthorized**: If not authenticated

    Notes:
    - Uses cursor-based pagination for optimal performance
    - The cursor is a base64 encoded post ID
    - Posts are returned in reverse chronological order (most recently liked first)
    """
    # Decode cursor if provided
    cursor_uuid = None
    if cursor:
        try:
            cursor_bytes = base64.b64decode(cursor.encode("utf-8"))
            cursor_uuid = UUID(cursor_bytes.decode("utf-8"))
        except (ValueError, TypeError):
            pass

    # Get liked posts from the service layer
    posts, next_cursor_uuid = await get_user_liked_posts(
        user_id=current_user.id,
        limit=limit,
        cursor=cursor_uuid
    )

    # Generate the next cursor if there are more results
    next_cursor = None
    if next_cursor_uuid:
        next_cursor = base64.b64encode(str(next_cursor_uuid).encode("utf-8")).decode("utf-8")

    return {
        "posts": posts,
        "next_cursor": next_cursor,
    }
