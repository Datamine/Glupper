from __future__ import annotations

from src.models.models import Account, SocialIdentity
from src.schemas.schemas import AccountPrivateResponse, AccountPublicResponse, SocialIdentityResponse
from src.services.account_service import account_trust_days, list_social_identities


def social_identity_to_response(identity: SocialIdentity) -> SocialIdentityResponse:
    return SocialIdentityResponse(
        id=identity.id,
        provider=identity.provider,
        handle=identity.handle,
        provider_user_id=identity.provider_user_id,
        verified_at=identity.verified_at,
        created_at=identity.created_at,
    )


async def account_to_private_response(account: Account) -> AccountPrivateResponse:
    identities = await list_social_identities(account.id)
    return AccountPrivateResponse(
        id=account.id,
        username=account.username,
        email=account.email,
        status=account.status,
        demerit_count=account.demerit_count,
        trust_days=account_trust_days(account),
        trust_started_at=account.trust_started_at,
        recovery_eligible_at=account.recovery_eligible_at,
        sponsor_id=account.sponsor_id,
        linked_social_accounts=[social_identity_to_response(identity) for identity in identities],
        created_at=account.created_at,
    )


async def account_to_public_response(account: Account) -> AccountPublicResponse:
    identities = await list_social_identities(account.id)
    return AccountPublicResponse(
        id=account.id,
        username=account.username,
        status=account.status,
        demerit_count=account.demerit_count,
        trust_days=account_trust_days(account),
        trust_started_at=account.trust_started_at,
        recovery_eligible_at=account.recovery_eligible_at,
        sponsor_id=account.sponsor_id,
        linked_social_accounts=[social_identity_to_response(identity) for identity in identities],
        created_at=account.created_at,
    )
