from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from src.core.auth import get_active_account
from src.models.models import Account
from src.schemas.schemas import InviteCreateRequest, InviteResponse
from src.services.account_service import InvalidAccountStateError, create_invite, list_invites_for_account

router = APIRouter(prefix="/api/v1/invites", tags=["invites"])


@router.post("", response_model=InviteResponse, status_code=status.HTTP_201_CREATED)
async def create_new_invite(
    payload: InviteCreateRequest,
    current_account: Annotated[Account, Depends(get_active_account)],
) -> InviteResponse:
    """Create invite code for active account."""
    try:
        invite = await create_invite(
            account_id=current_account.id,
            max_uses=payload.max_uses,
            expires_in_days=payload.expires_in_days,
        )
    except InvalidAccountStateError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    return InviteResponse(
        code=invite.code,
        sponsor_id=invite.sponsor_id,
        max_uses=invite.max_uses,
        uses=invite.uses,
        expires_at=invite.expires_at,
        is_active=invite.is_active,
        created_at=invite.created_at,
    )


@router.get("/mine", response_model=list[InviteResponse], status_code=status.HTTP_200_OK)
async def get_my_invites(current_account: Annotated[Account, Depends(get_active_account)]) -> list[InviteResponse]:
    """List invite codes created by the authenticated account."""
    invites = await list_invites_for_account(current_account.id)
    return [
        InviteResponse(
            code=invite.code,
            sponsor_id=invite.sponsor_id,
            max_uses=invite.max_uses,
            uses=invite.uses,
            expires_at=invite.expires_at,
            is_active=invite.is_active,
            created_at=invite.created_at,
        )
        for invite in invites
    ]
