from typing import Annotated, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from src.core.auth import get_current_user
from src.core.db import pool
from src.models.models import User
from src.schemas.schemas import MutedUsersResponse, UserResponse, UserUpdateRequest
from src.services.user_service import (
    follow_user,
    get_muted_users,
    get_user_by_id,
    get_user_followers,
    get_user_following,
    is_user_muted,
    mute_user,
    unfollow_user,
    unmute_user,
    update_user_profile,
)

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.get("/{user_id}", status_code=status.HTTP_200_OK)
async def get_user(user_id: UUID) -> UserResponse:
    """
    Get a user's profile by their ID.

    Parameters:
    - **user_id**: UUID of the user to retrieve

    Returns:
    - **UserResponse**: User profile information

    Raises:
    - **404 Not Found**: If user does not exist
    """
    user = await get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return user


@router.put("/me", status_code=status.HTTP_200_OK)
async def update_profile(
    update_data: UserUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    """
    Update the current authenticated user's profile.

    Parameters:
    - **update_data**: User data to update (bio, profile picture)
    - **current_user**: User object from token authentication dependency

    Returns:
    - **UserResponse**: Updated user profile information

    Raises:
    - **401 Unauthorized**: If not authenticated
    """
    updated_user = await update_user_profile(current_user.id, update_data.dict(exclude_unset=True))
    return updated_user


