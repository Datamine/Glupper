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


@router.get("/{user_id}/followers", status_code=status.HTTP_200_OK)
async def get_followers(
    user_id: UUID,
    limit: int = 20,
    offset: int = 0,
) -> list[UserResponse]:
    """
    Get a list of users who follow the specified user.

    Parameters:
    - **user_id**: UUID of the user whose followers to retrieve
    - **limit**: Maximum number of users to return (default: 20)
    - **offset**: Pagination offset (default: 0)

    Returns:
    - **list[UserResponse]**: List of users who follow the specified user

    Raises:
    - **404 Not Found**: If user does not exist
    """
    # First check if user exists
    user = await get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    followers = await get_user_followers(user_id, limit, offset)
    return followers


@router.get("/{user_id}/following", status_code=status.HTTP_200_OK)
async def get_following(
    user_id: UUID,
    limit: int = 20,
    offset: int = 0,
) -> list[UserResponse]:
    """
    Get a list of users that the specified user is following.

    Parameters:
    - **user_id**: UUID of the user whose followings to retrieve
    - **limit**: Maximum number of users to return (default: 20)
    - **offset**: Pagination offset (default: 0)

    Returns:
    - **list[UserResponse]**: List of users followed by the specified user

    Raises:
    - **404 Not Found**: If user does not exist
    """
    # First check if user exists
    user = await get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    following = await get_user_following(user_id, limit, offset)
    return following


@router.post("/{user_id}/follow", status_code=status.HTTP_200_OK)
async def follow(
    user_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, bool]:
    """
    Follow another user.

    Parameters:
    - **user_id**: UUID of the user to follow
    - **current_user**: User object from token authentication dependency

    Returns:
    - **dict[str, bool]**: Success status of the operation

    Raises:
    - **401 Unauthorized**: If not authenticated
    - **404 Not Found**: If user does not exist
    - **400 Bad Request**: If attempting to follow yourself
    """
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


@router.post("/{user_id}/unfollow", status_code=status.HTTP_200_OK)
async def unfollow(
    user_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, bool]:
    """
    Unfollow a currently followed user.

    Parameters:
    - **user_id**: UUID of the user to unfollow
    - **current_user**: User object from token authentication dependency

    Returns:
    - **dict[str, bool]**: Success status of the operation

    Raises:
    - **401 Unauthorized**: If not authenticated
    - **404 Not Found**: If user does not exist
    - **400 Bad Request**: If attempting to unfollow yourself
    """
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


@router.post("/{user_id}/mute", status_code=status.HTTP_200_OK)
async def mute(
    user_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, bool]:
    """
    Mute another user to hide their posts from your feed.

    Parameters:
    - **user_id**: UUID of the user to mute
    - **current_user**: User object from token authentication dependency

    Returns:
    - **dict[str, bool]**: Success status of the operation

    Raises:
    - **401 Unauthorized**: If not authenticated
    - **404 Not Found**: If user does not exist
    - **400 Bad Request**: If attempting to mute yourself
    """
    # Check if user exists
    user = await get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Cannot mute yourself
    if current_user.id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot mute yourself",
        )

    success = await mute_user(current_user.id, user_id)
    return {"success": success}


@router.post("/{user_id}/unmute", status_code=status.HTTP_200_OK)
async def unmute(
    user_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, bool]:
    """
    Unmute a previously muted user to see their posts again.

    Parameters:
    - **user_id**: UUID of the user to unmute
    - **current_user**: User object from token authentication dependency

    Returns:
    - **dict[str, bool]**: Success status of the operation

    Raises:
    - **401 Unauthorized**: If not authenticated
    - **404 Not Found**: If user does not exist
    - **400 Bad Request**: If attempting to unmute yourself
    """
    # Check if user exists
    user = await get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Cannot unmute yourself
    if current_user.id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot unmute yourself",
        )

    success = await unmute_user(current_user.id, user_id)
    return {"success": success}


@router.get("/me/muted", status_code=status.HTTP_200_OK)
async def get_muted(
    limit: int = 50,
    offset: int = 0,
    current_user: Annotated[User, Depends(get_current_user)],
) -> MutedUsersResponse:
    """
    Get list of users that the current user has muted.

    Parameters:
    - **limit**: Maximum number of users to return (default: 50)
    - **offset**: Pagination offset (default: 0)
    - **current_user**: User object from token authentication dependency

    Returns:
    - **MutedUsersResponse**: List of muted users with pagination info

    Raises:
    - **401 Unauthorized**: If not authenticated
    """
    muted_users = await get_muted_users(current_user.id, limit, offset)

    # Get total count of muted users
    async with pool.acquire() as conn:
        total = await conn.fetchval(
            "SELECT COUNT(*) FROM mutes WHERE muter_id = $1",
            current_user.id
        )

    return MutedUsersResponse(
        users=muted_users,
        total=total or 0
    )


@router.get("/{user_id}/muted", status_code=status.HTTP_200_OK)
async def check_if_muted(
    user_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, bool]:
    """
    Check if a user is muted by the current user.

    Parameters:
    - **user_id**: UUID of the user to check
    - **current_user**: User object from token authentication dependency

    Returns:
    - **dict[str, bool]**: Whether the user is muted

    Raises:
    - **401 Unauthorized**: If not authenticated
    - **404 Not Found**: If user does not exist
    """
    # Check if user exists
    user = await get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    is_muted = await is_user_muted(current_user.id, user_id)
    return {"is_muted": is_muted}
