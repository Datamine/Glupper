from __future__ import annotations

from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, status

from src.api.serializers import social_identity_to_response
from src.core.auth import get_active_account
from src.models.models import Account
from src.schemas.schemas import SocialIdentityLinkRequest, SocialIdentityResponse
from src.services.account_service import AccountNotFoundError, InvalidAccountStateError, link_social_identity, list_social_identities

router = APIRouter(prefix="/api/v1/social-accounts", tags=["social_accounts"])


@router.post("/link", response_model=SocialIdentityResponse, status_code=status.HTTP_201_CREATED)
async def link_my_social_account(
    payload: SocialIdentityLinkRequest,
    current_account: Annotated[Account, Depends(get_active_account)],
) -> SocialIdentityResponse:
    """Link one social account after provider token verification.

    MVP supports GitHub verification.
    """
    provider = payload.provider.strip().lower()
    if provider != "github":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only github is supported in MVP")

    provider_user_id = await _verify_github_identity(payload.handle, payload.oauth_access_token)

    try:
        identity = await link_social_identity(
            account_id=current_account.id,
            provider=provider,
            handle=payload.handle,
            provider_user_id=provider_user_id,
        )
    except AccountNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except InvalidAccountStateError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    return social_identity_to_response(identity)


@router.get("/mine", response_model=list[SocialIdentityResponse], status_code=status.HTTP_200_OK)
async def list_my_social_accounts(current_account: Annotated[Account, Depends(get_active_account)]) -> list[SocialIdentityResponse]:
    """List authenticated account's linked social identities."""
    identities = await list_social_identities(current_account.id)
    return [social_identity_to_response(identity) for identity in identities]


async def _verify_github_identity(expected_handle: str, oauth_access_token: str) -> str:
    headers = {
        "Authorization": f"Bearer {oauth_access_token}",
        "Accept": "application/vnd.github+json",
    }
    async with httpx.AsyncClient(timeout=8.0) as client:
        response = await client.get("https://api.github.com/user", headers=headers)

    if response.status_code != status.HTTP_200_OK:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="GitHub OAuth verification failed")

    payload: dict[str, Any] = response.json()
    handle = payload.get("login")
    provider_user_id = payload.get("id")

    if not isinstance(handle, str) or provider_user_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid GitHub user payload")
    if handle.casefold() != expected_handle.casefold():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="GitHub handle mismatch")

    return str(provider_user_id)
