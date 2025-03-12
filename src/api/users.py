from typing import Annotated, List
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
) -> List[UserResponse]:
    """
    Get a list of users who follow the specified user.
    
    Parameters:
    - **user_id**: UUID of the user whose followers to retrieve
    - **limit**: Maximum number of users to return (default: 20)
    - **offset**: Pagination offset (default: 0)
    
    Returns:
    - **List[UserResponse]**: List of users who follow the specified user
    
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
) -> List[UserResponse]:
    """
    Get a list of users that the specified user is following.
    
    Parameters:
    - **user_id**: UUID of the user whose followings to retrieve
    - **limit**: Maximum number of users to return (default: 20)
    - **offset**: Pagination offset (default: 0)
    
    Returns:
    - **List[UserResponse]**: List of users followed by the specified user
    
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
