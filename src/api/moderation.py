from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from src.core.auth import require_admin_key
from src.core.cache import add_banned_accounts, get_ban_record, is_banned
from src.schemas.schemas import (
    BannedAccountResponse,
    BootstrapUserRequest,
    ConvictAccountRequest,
    ConvictAccountResponse,
    ExpireInactiveSponsorsRequest,
    ExpireInactiveSponsorsResponse,
)
from src.services.account_service import (
    AccountNotFoundError,
    DuplicateAccountError,
    convict_and_ban_tree,
    create_bootstrap_account,
    expire_inactive_sponsor_trees,
)

router = APIRouter(prefix="/api/v1/moderation", tags=["moderation"])


@router.post("/bootstrap-user", dependencies=[Depends(require_admin_key)], status_code=status.HTTP_201_CREATED)
async def bootstrap_user(payload: BootstrapUserRequest) -> dict[str, str]:
    """Create initial trusted user without invite code."""
    try:
        account = await create_bootstrap_account(payload.username, payload.email, payload.password)
    except DuplicateAccountError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return {"account_id": str(account.id), "username": account.username}


@router.post("/convict", response_model=ConvictAccountResponse, dependencies=[Depends(require_admin_key)], status_code=status.HTTP_200_OK)
async def convict_account(payload: ConvictAccountRequest) -> ConvictAccountResponse:
    """Convict one account as bot and force downstream users into revouch_required recovery."""
    try:
        banned_root_account_id, downstream_revouch_required_ids, penalized_sponsor_id = await convict_and_ban_tree(payload.account_id, payload.reason)
    except AccountNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    await add_banned_accounts(account_ids=[banned_root_account_id], reason=payload.reason)
    return ConvictAccountResponse(
        convicted_account_id=payload.account_id,
        banned_root_account_id=banned_root_account_id,
        downstream_revouch_required_ids=downstream_revouch_required_ids,
        penalized_sponsor_id=penalized_sponsor_id,
    )


@router.post(
    "/expire-inactive-sponsors",
    response_model=ExpireInactiveSponsorsResponse,
    dependencies=[Depends(require_admin_key)],
    status_code=status.HTTP_200_OK,
)
async def expire_inactive_sponsors(payload: ExpireInactiveSponsorsRequest) -> ExpireInactiveSponsorsResponse:
    """Mark descendants as revouch_required when sponsor inactivity exceeds threshold."""
    marked_ids = await expire_inactive_sponsor_trees(payload.inactivity_days)
    return ExpireInactiveSponsorsResponse(marked_account_ids=marked_ids)


@router.get("/banned/{account_id}", response_model=BannedAccountResponse, dependencies=[Depends(require_admin_key)], status_code=status.HTTP_200_OK)
async def get_banned_account_record(account_id: UUID) -> BannedAccountResponse:
    """Read Redis ban dataset entry for one account."""
    cached = await is_banned(account_id)
    cached_record = await get_ban_record(account_id)

    reason: str | None = None
    banned_at: datetime | None = None
    if cached_record is not None:
        reason = cached_record.get("reason")
        banned_at_raw = cached_record.get("banned_at")
        if banned_at_raw is not None:
            banned_at = datetime.fromisoformat(banned_at_raw)

    return BannedAccountResponse(
        account_id=account_id,
        reason=reason,
        banned_at=banned_at,
        exists_in_cache=cached,
    )
