from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

from src.models.models import AccountStatus


class Token(BaseModel):
    access_token: str
    token_type: str


class RegisterPasswordRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    invite_code: str

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return value.strip()


class RegisterGoogleRequest(BaseModel):
    id_token: str
    username: str | None = Field(default=None, min_length=3, max_length=32)
    invite_code: str | None = None


class LoginPasswordRequest(BaseModel):
    username_or_email: str
    password: str


class SocialIdentityLinkRequest(BaseModel):
    provider: str = Field(min_length=2, max_length=32)
    handle: str = Field(min_length=1, max_length=128)
    oauth_access_token: str = Field(min_length=5)


class SocialIdentityResponse(BaseModel):
    id: UUID
    provider: str
    handle: str
    provider_user_id: str
    verified_at: datetime
    created_at: datetime


class AccountPublicResponse(BaseModel):
    id: UUID
    username: str
    status: AccountStatus
    demerit_count: int
    trust_days: int
    trust_started_at: datetime | None
    recovery_eligible_at: datetime | None
    sponsor_id: UUID | None
    linked_social_accounts: list[SocialIdentityResponse]
    created_at: datetime


class AccountPrivateResponse(BaseModel):
    id: UUID
    username: str
    email: EmailStr
    status: AccountStatus
    demerit_count: int
    trust_days: int
    trust_started_at: datetime | None
    recovery_eligible_at: datetime | None
    sponsor_id: UUID | None
    linked_social_accounts: list[SocialIdentityResponse]
    created_at: datetime


class AuthResponse(BaseModel):
    access_token: str
    token_type: str
    account: AccountPrivateResponse


class InviteCreateRequest(BaseModel):
    max_uses: int = Field(default=1, ge=1, le=25)
    expires_in_days: int | None = Field(default=30, ge=1, le=365)


class InviteResponse(BaseModel):
    code: str
    sponsor_id: UUID
    max_uses: int
    uses: int
    expires_at: datetime | None
    is_active: bool
    created_at: datetime


class RevouchRequest(BaseModel):
    invite_code: str


class BootstrapUserRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class ConvictAccountRequest(BaseModel):
    account_id: UUID
    reason: str = Field(min_length=3, max_length=300)


class ConvictAccountResponse(BaseModel):
    convicted_account_id: UUID
    banned_root_account_id: UUID
    downstream_revouch_required_ids: list[UUID]
    penalized_sponsor_id: UUID | None


class ExpireInactiveSponsorsRequest(BaseModel):
    inactivity_days: int = Field(default=90, ge=1, le=3650)


class ExpireInactiveSponsorsResponse(BaseModel):
    marked_account_ids: list[UUID]


class BannedAccountResponse(BaseModel):
    account_id: UUID
    reason: str | None
    banned_at: datetime | None
    exists_in_cache: bool
