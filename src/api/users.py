from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.serializers import account_to_private_response, account_to_public_response
from src.core.auth import get_current_account
from src.models.models import Account, AccountStatus
from src.schemas.schemas import AccountPrivateResponse, AccountPublicResponse, RevouchRequest
from src.services.account_service import (
    AccountNotFoundError,
    InvalidAccountStateError,
    InvalidInviteCodeError,
    get_account_by_username,
    revouch_account,
    touch_last_active,
)

router = APIRouter(prefix="/api/v1/accounts", tags=["accounts"])


@router.get("/me", response_model=AccountPrivateResponse, status_code=status.HTTP_200_OK)
async def get_my_profile(current_account: Annotated[Account, Depends(get_current_account)]) -> AccountPrivateResponse:
    """Return private profile for authenticated account."""
    await touch_last_active(current_account.id)
    refreshed = await _require_existing_account(current_account.username)
    return await account_to_private_response(refreshed)


@router.get("/{username}", response_model=AccountPublicResponse, status_code=status.HTTP_200_OK)
async def get_public_profile(username: str) -> AccountPublicResponse:
    """Return public trust profile for one account."""
    account = await _require_existing_account(username)
    return await account_to_public_response(account)


@router.post("/me/revouch", response_model=AccountPrivateResponse, status_code=status.HTTP_200_OK)
async def revouch_me(
    payload: RevouchRequest,
    current_account: Annotated[Account, Depends(get_current_account)],
) -> AccountPrivateResponse:
    """Use a fresh invite to restore active trust and reset trust timer."""
    if current_account.status is AccountStatus.BANNED:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Banned accounts cannot revouch")

    try:
        updated_account = await revouch_account(account_id=current_account.id, invite_code=payload.invite_code)
    except InvalidInviteCodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except InvalidAccountStateError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except AccountNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return await account_to_private_response(updated_account)


@router.post("/me/heartbeat", status_code=status.HTTP_200_OK)
async def heartbeat(current_account: Annotated[Account, Depends(get_current_account)]) -> dict[str, str]:
    """Update last_active_at to support inactivity-based voucher expiry."""
    await touch_last_active(current_account.id)
    return {"status": "ok"}


async def _require_existing_account(username: str) -> Account:
    account = await get_account_by_username(username)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    return account
