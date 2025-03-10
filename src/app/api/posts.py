from typing import Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from glupper.app.core.auth import get_current_user
from glupper.app.models.models import User
from glupper.app.schemas.schemas import (
    PostCreate, 
    PostResponse, 
    PostDetailResponse,
    CommentCreate,
)
from glupper.app.services.post_service import (
    create_post,
    get_post,
    create_comment,
    like_post,
    unlike_post,
    repost,
    get_user_posts,
)

router = APIRouter(prefix="/posts", tags=["posts"])

@router.post("")
async def create_new_post(
    post_data: PostCreate,
    current_user: User = Depends(get_current_user),
) -> PostResponse:
    """Create a new post"""
    post = await create_post(
        user_id=current_user.id,
        content=post_data.content,
        media_urls=post_data.media_urls,
    )
    return post

@router.get("/{post_id}")
async def get_post_detail(post_id: UUID) -> PostDetailResponse:
    """Get a post by ID with comments"""
    post = await get_post(post_id)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found",
        )
    return post

@router.post("/{post_id}/comments")
async def comment_on_post(
    post_id: UUID,
    comment_data: CommentCreate,
    current_user: User = Depends(get_current_user),
) -> PostResponse:
    """Comment on a post"""
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

@router.post("/{post_id}/like")
async def like(
    post_id: UUID,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Like a post"""
    success = await like_post(current_user.id, post_id)
    return {"success": success}

@router.post("/{post_id}/unlike")
async def unlike(
    post_id: UUID,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Unlike a post"""
    success = await unlike_post(current_user.id, post_id)
    return {"success": success}

@router.post("/{post_id}/repost")
async def repost_post(
    post_id: UUID,
    current_user: User = Depends(get_current_user),
) -> PostResponse:
    """Repost a post"""
    reposted = await repost(current_user.id, post_id)
    if not reposted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found",
        )
    return reposted

@router.get("/user/{user_id}")
async def get_posts_by_user(
    user_id: UUID,
    limit: int = 20,
    offset: int = 0,
) -> List[PostResponse]:
    """Get posts created by a specific user"""
    posts = await get_user_posts(user_id, limit, offset)
    return posts