from typing import Annotated, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from src.core.auth import get_current_user
from src.models.models import User
from src.schemas.schemas import (
    CommentCreate,
    PostCreate,
    PostDetailResponse,
    PostResponse,
)
from src.services.post_service import (
    create_comment,
    create_post,
    get_post,
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
    - **401 Unauthorized**: If not authenticated
    - **404 Not Found**: If the original post does not exist
    """
    reposted = await repost(current_user.id, post_id)
    if not reposted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found",
        )
    return reposted


@router.get("/user/{user_id}", status_code=status.HTTP_200_OK)
async def get_posts_by_user(
    user_id: UUID,
    limit: int = 20,
    offset: int = 0,
) -> List[PostResponse]:
    """
    Get posts created by a specific user.
    
    Parameters:
    - **user_id**: UUID of the user whose posts to retrieve
    - **limit**: Maximum number of posts to return (default: 20)
    - **offset**: Pagination offset (default: 0)
    
    Returns:
    - **List[PostResponse]**: List of posts by the specified user
    """
    posts = await get_user_posts(user_id, limit, offset)
    return posts
