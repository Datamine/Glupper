from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from src.core.auth import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    create_access_token,
    get_current_user,
    verify_password,
)
from src.models.models import User
from src.schemas.schemas import Token, UserCreate, UserResponse
from src.services.user_service import create_user, get_user_by_username

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate) -> UserResponse:
    """
    Register a new user.

    Parameters:
    - **user_data**: User registration data including username, email, and password

    Returns:
    - **UserResponse**: Newly created user information

    Raises:
    - **400 Bad Request**: If username is already registered
    """
    # Check if username exists
    existing_user = await get_user_by_username(user_data.username)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )
    return await create_user(
        username=user_data.username,
        email=user_data.email,
        password=user_data.password,
        bio=user_data.bio,
    )


@router.post("/login", status_code=status.HTTP_200_OK)
async def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]) -> Token:
    """
    Authenticate a user and return an access token.

    Parameters:
    - **form_data**: OAuth2 password request form containing username and password

    Returns:
    - **Token**: JWT access token for authentication

    Raises:
    - **401 Unauthorized**: If credentials are invalid
    """
    user = await get_user_by_username(form_data.username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not verify_password(form_data.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"]},
        expires_delta=access_token_expires,
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", status_code=status.HTTP_200_OK)
async def get_current_user_info(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """
    Get the currently authenticated user's information.

    Parameters:
    - **current_user**: User object from token authentication dependency

    Returns:
    - **User**: Current user information

    Raises:
    - **401 Unauthorized**: If not authenticated
    """
    return current_user
