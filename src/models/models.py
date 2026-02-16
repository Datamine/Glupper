from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, EmailStr


class AccountStatus(StrEnum):
    ACTIVE = "active"
    REVOUCH_REQUIRED = "revouch_required"
    BANNED = "banned"


class AuthProvider(StrEnum):
    EMAIL = "email"
    GOOGLE = "google"


class Account(BaseModel):
    id: UUID
    username: str
    email: EmailStr
    password_hash: str | None
    auth_provider: AuthProvider
    auth_provider_subject: str | None
    sponsor_id: UUID | None
    status: AccountStatus
    demerit_count: int
    trust_started_at: datetime | None
    recovery_eligible_at: datetime | None
    last_active_at: datetime
    created_at: datetime
    updated_at: datetime


class InviteCode(BaseModel):
    code: str
    sponsor_id: UUID
    max_uses: int
    uses: int
    expires_at: datetime | None
    is_active: bool
    created_at: datetime


class SocialIdentity(BaseModel):
    id: UUID
    account_id: UUID
    provider: str
    handle: str
    provider_user_id: str
    verified_at: datetime
    created_at: datetime
