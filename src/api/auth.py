from __future__ import annotations

from datetime import timedelta
from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import EmailStr

from src.api.serializers import account_to_private_response
from src.core.auth import ACCESS_TOKEN_EXPIRE_MINUTES, create_access_token, get_current_account
from src.models.models import Account
from src.schemas.schemas import AccountPrivateResponse, AuthResponse, LoginPasswordRequest, RegisterGoogleRequest, RegisterPasswordRequest, Token
from src.services.account_service import (
    DuplicateAccountError,
    InvalidCredentialsError,
    InvalidInviteCodeError,
    get_account_by_google_subject,
    register_google_account,
    register_password_account,
    touch_last_active,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/register/password", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register_with_password(payload: RegisterPasswordRequest) -> AuthResponse:
    """Register a new account via email/password with an invite code."""
    try:
        account = await register_password_account(
            username=payload.username,
            email=payload.email,
            password=payload.password,
            invite_code=payload.invite_code,
        )
    except DuplicateAccountError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except InvalidInviteCodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    token = create_access_token(
        subject_account_id=account.id,
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return AuthResponse(
        access_token=token,
        token_type="bearer",
        account=await account_to_private_response(account),
    )


@router.post("/login/password", response_model=Token, status_code=status.HTTP_200_OK)
async def login_with_password(payload: LoginPasswordRequest) -> Token:
    """Authenticate via email/username and password."""
    from src.services.account_service import authenticate_password_account

    try:
        account = await authenticate_password_account(
            username_or_email=payload.username_or_email,
            password=payload.password,
        )
    except InvalidCredentialsError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials") from exc

    await touch_last_active(account.id)
    token = create_access_token(
        subject_account_id=account.id,
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return Token(access_token=token, token_type="bearer")


@router.post("/register/google", response_model=AuthResponse, status_code=status.HTTP_200_OK)
async def register_or_login_google(payload: RegisterGoogleRequest) -> AuthResponse:
    """Register/login using a Google id_token.

    Existing google users are logged in directly. New users must provide username + invite_code.
    """
    token_info = await _verify_google_id_token(payload.id_token)
    existing_account = await get_account_by_google_subject(token_info["sub"])
    if existing_account is not None:
        await touch_last_active(existing_account.id)
        token = create_access_token(subject_account_id=existing_account.id)
        return AuthResponse(
            access_token=token,
            token_type="bearer",
            account=await account_to_private_response(existing_account),
        )

    if payload.username is None or payload.invite_code is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New Google registrations require username and invite_code",
        )

    try:
        account = await register_google_account(
            username=payload.username,
            email=EmailStr(token_info["email"]),
            google_subject=token_info["sub"],
            invite_code=payload.invite_code,
        )
    except DuplicateAccountError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except InvalidInviteCodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    token = create_access_token(subject_account_id=account.id)
    return AuthResponse(
        access_token=token,
        token_type="bearer",
        account=await account_to_private_response(account),
    )


@router.get("/me", response_model=AccountPrivateResponse, status_code=status.HTTP_200_OK)
async def get_me(current_account: Annotated[Account, Depends(get_current_account)]) -> AccountPrivateResponse:
    """Return authenticated account record."""
    await touch_last_active(current_account.id)
    refreshed = await account_to_private_response(current_account)
    return refreshed


async def _verify_google_id_token(id_token: str) -> dict[str, str]:
    url = "https://oauth2.googleapis.com/tokeninfo"
    async with httpx.AsyncClient(timeout=8.0) as client:
        response = await client.get(url, params={"id_token": id_token})

    if response.status_code != status.HTTP_200_OK:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Google id_token")

    payload: dict[str, Any] = response.json()
    subject = payload.get("sub")
    email = payload.get("email")
    email_verified = payload.get("email_verified")

    verified_values = {True, "true", "True"}
    if not isinstance(subject, str) or not isinstance(email, str) or email_verified not in verified_values:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Google token missing required verified identity fields")

    return {"sub": subject, "email": email}
