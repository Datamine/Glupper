from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from src.core.auth import get_current_user
from src.models.models import User
from src.schemas.schemas import UserResponse, UserUpdateRequest
from src.services.user_service import (
    follow_user,
    get_user_by_id,
    get_user_followers,
    get_user_following,
    unfollow_user,
    update_user_profile,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/{user_id}")
async def get_user(user_id: UUID) -> UserResponse:
    """Get user profile by ID"""
    user = await get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return user


@router.put("/me")
async def update_profile(
    update_data: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """Update current user's profile"""
    updated_user = await update_user_profile(current_user.id, update_data.dict(exclude_unset=True))
    return updated_user


@router.get("/{user_id}/followers")
async def get_followers(
    user_id: UUID,
    limit: int = 20,
    offset: int = 0,
) -> list[UserResponse]:
    """Get a user's followers"""
    # First check if user exists
    user = await get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    followers = await get_user_followers(user_id, limit, offset)
    return followers


@router.get("/{user_id}/following")
async def get_following(
    user_id: UUID,
    limit: int = 20,
    offset: int = 0,
) -> list[UserResponse]:
    """Get users that this user is following"""
    # First check if user exists
    user = await get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    following = await get_user_following(user_id, limit, offset)
    return following


@router.post("/{user_id}/follow")
async def follow(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Follow a user"""
    # Check if user exists
    user = await get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Cannot follow yourself
    if current_user.id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot follow yourself",
        )

    success = await follow_user(current_user.id, user_id)
    return {"success": success}


@router.post("/{user_id}/unfollow")
async def unfollow(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Unfollow a user"""
    # Check if user exists
    user = await get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Cannot unfollow yourself
    if current_user.id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot unfollow yourself",
        )

    success = await unfollow_user(current_user.id, user_id)
    return {"success": success}
