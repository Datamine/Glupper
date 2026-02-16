from __future__ import annotations

import json
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from asyncpg import Connection, Record
from pydantic import EmailStr

from src.config_secrets import RECOVERY_COOLDOWN_HOURS, RECOVERY_SPONSOR_MAX_DEMERITS, RECOVERY_SPONSOR_MIN_TRUST_DAYS
from src.core.auth import get_password_hash, verify_password
from src.core.db import get_connection
from src.models.models import Account, AccountStatus, AuthProvider, InviteCode, SocialIdentity


class ServiceError(Exception):
    """Base service exception."""


class DuplicateAccountError(ServiceError):
    """Raised when username/email/provider-subject already exists."""


class InvalidInviteCodeError(ServiceError):
    """Raised when invite code is missing or expired."""


class InvalidCredentialsError(ServiceError):
    """Raised for failed authentication."""


class AccountNotFoundError(ServiceError):
    """Raised when account is not found."""


class InvalidAccountStateError(ServiceError):
    """Raised for account states that cannot perform requested action."""


async def create_bootstrap_account(username: str, email: EmailStr, password: str) -> Account:
    """Create an initial trusted account without an invite code."""
    async with get_connection() as connection:
        async with connection.transaction():
            await _ensure_unique_account(connection, username=username, email=email)
            account = await _insert_account(
                connection=connection,
                username=username,
                email=email,
                password_hash=get_password_hash(password),
                auth_provider=AuthProvider.EMAIL,
                auth_provider_subject=None,
                sponsor_id=None,
            )
            await _insert_event(connection, account.id, "bootstrap_account", {"username": username})
            return account


async def register_password_account(username: str, email: EmailStr, password: str, invite_code: str) -> Account:
    """Create account through invite code using password auth."""
    async with get_connection() as connection:
        async with connection.transaction():
            sponsor_id = await _consume_invite_code(connection, invite_code)
            await _ensure_active_sponsor(connection, sponsor_id)
            await _ensure_unique_account(connection, username=username, email=email)

            account = await _insert_account(
                connection=connection,
                username=username,
                email=email,
                password_hash=get_password_hash(password),
                auth_provider=AuthProvider.EMAIL,
                auth_provider_subject=None,
                sponsor_id=sponsor_id,
            )
            await _insert_event(connection, account.id, "registered_with_password", {"sponsor_id": str(sponsor_id)})
            return account


async def register_google_account(
    username: str,
    email: EmailStr,
    google_subject: str,
    invite_code: str,
) -> Account:
    """Create account through invite code using Google OAuth subject."""
    async with get_connection() as connection:
        async with connection.transaction():
            sponsor_id = await _consume_invite_code(connection, invite_code)
            await _ensure_active_sponsor(connection, sponsor_id)
            await _ensure_unique_account(connection, username=username, email=email, google_subject=google_subject)

            account = await _insert_account(
                connection=connection,
                username=username,
                email=email,
                password_hash=None,
                auth_provider=AuthProvider.GOOGLE,
                auth_provider_subject=google_subject,
                sponsor_id=sponsor_id,
            )
            await _insert_event(connection, account.id, "registered_with_google", {"sponsor_id": str(sponsor_id)})
            return account


async def get_account_by_id(account_id: UUID) -> Account | None:
    """Load account by UUID."""
    async with get_connection() as connection:
        row = await connection.fetchrow("SELECT * FROM accounts WHERE id = $1", account_id)
    if row is None:
        return None
    return _account_from_record(row)


async def get_account_by_username(username: str) -> Account | None:
    """Load account by username."""
    async with get_connection() as connection:
        row = await connection.fetchrow("SELECT * FROM accounts WHERE username = $1", username)
    if row is None:
        return None
    return _account_from_record(row)


async def get_account_by_google_subject(google_subject: str) -> Account | None:
    """Load account by Google subject id."""
    async with get_connection() as connection:
        row = await connection.fetchrow(
            "SELECT * FROM accounts WHERE auth_provider = 'google' AND auth_provider_subject = $1",
            google_subject,
        )
    if row is None:
        return None
    return _account_from_record(row)


async def authenticate_password_account(username_or_email: str, password: str) -> Account:
    """Authenticate email/password account."""
    async with get_connection() as connection:
        row = await connection.fetchrow(
            "SELECT * FROM accounts WHERE username = $1 OR email = $1",
            username_or_email,
        )

    if row is None:
        raise InvalidCredentialsError("Unknown username/email")

    account = _account_from_record(row)
    if account.password_hash is None:
        raise InvalidCredentialsError("Account does not use password authentication")
    if not verify_password(password, account.password_hash):
        raise InvalidCredentialsError("Password does not match")
    return account


async def touch_last_active(account_id: UUID) -> None:
    """Update last_active_at timestamp."""
    async with get_connection() as connection:
        await connection.execute(
            """
            UPDATE accounts
            SET last_active_at = NOW(), updated_at = NOW()
            WHERE id = $1
            """,
            account_id,
        )


async def create_invite(account_id: UUID, max_uses: int, expires_in_days: int | None) -> InviteCode:
    """Create a new invite code for an active account."""
    account = await get_account_by_id(account_id)
    if account is None:
        raise AccountNotFoundError("Account not found")
    if account.status is not AccountStatus.ACTIVE:
        raise InvalidAccountStateError("Only active accounts can generate invites")

    expires_at: datetime | None = None
    if expires_in_days is not None:
        expires_at = datetime.now(UTC).replace(tzinfo=None) + timedelta(days=expires_in_days)

    invite_code = secrets.token_urlsafe(10)
    async with get_connection() as connection:
        await connection.execute(
            """
            INSERT INTO invite_codes (code, sponsor_id, max_uses, uses, expires_at, is_active)
            VALUES ($1, $2, $3, 0, $4, TRUE)
            """,
            invite_code,
            account_id,
            max_uses,
            expires_at,
        )
        await _insert_event(connection, account_id, "invite_created", {"code": invite_code, "max_uses": max_uses})
        row = await connection.fetchrow("SELECT * FROM invite_codes WHERE code = $1", invite_code)

    if row is None:
        raise ServiceError("Invite creation failed")
    return _invite_from_record(row)


async def list_invites_for_account(account_id: UUID) -> list[InviteCode]:
    """Return invite codes for one account."""
    async with get_connection() as connection:
        rows = await connection.fetch(
            """
            SELECT *
            FROM invite_codes
            WHERE sponsor_id = $1
            ORDER BY created_at DESC
            """,
            account_id,
        )
    return [_invite_from_record(row) for row in rows]


async def list_social_identities(account_id: UUID) -> list[SocialIdentity]:
    """Return linked social identities for one account."""
    async with get_connection() as connection:
        rows = await connection.fetch(
            """
            SELECT *
            FROM social_identities
            WHERE account_id = $1
            ORDER BY created_at DESC
            """,
            account_id,
        )
    return [_social_from_record(row) for row in rows]


async def link_social_identity(account_id: UUID, provider: str, handle: str, provider_user_id: str) -> SocialIdentity:
    """Upsert one verified social identity for an account."""
    account = await get_account_by_id(account_id)
    if account is None:
        raise AccountNotFoundError("Account not found")
    if account.status is AccountStatus.BANNED:
        raise InvalidAccountStateError("Banned accounts cannot link social identities")

    identity_id = uuid4()
    normalized_provider = provider.strip().lower()
    normalized_handle = handle.strip()
    normalized_user_id = provider_user_id.strip()

    async with get_connection() as connection:
        row = await connection.fetchrow(
            """
            INSERT INTO social_identities (id, account_id, provider, handle, provider_user_id, verified_at)
            VALUES ($1, $2, $3, $4, $5, NOW())
            ON CONFLICT (account_id, provider)
            DO UPDATE SET
                handle = EXCLUDED.handle,
                provider_user_id = EXCLUDED.provider_user_id,
                verified_at = NOW()
            RETURNING *
            """,
            identity_id,
            account_id,
            normalized_provider,
            normalized_handle,
            normalized_user_id,
        )
        await _insert_event(
            connection,
            account_id,
            "social_identity_linked",
            {
                "provider": normalized_provider,
                "handle": normalized_handle,
                "provider_user_id": normalized_user_id,
            },
        )

    if row is None:
        raise ServiceError("Social identity linkage failed")
    return _social_from_record(row)


async def revouch_account(account_id: UUID, invite_code: str) -> Account:
    """Assign a new sponsor and reset trust timer for revouch-required accounts."""
    async with get_connection() as connection:
        async with connection.transaction():
            account_row = await connection.fetchrow("SELECT * FROM accounts WHERE id = $1 FOR UPDATE", account_id)
            if account_row is None:
                raise AccountNotFoundError("Account not found")
            account = _account_from_record(account_row)
            if account.status is AccountStatus.BANNED:
                raise InvalidAccountStateError("Banned accounts cannot revouch")
            if account.status is not AccountStatus.REVOUCH_REQUIRED:
                raise InvalidAccountStateError("Revouch is only available for accounts that require revouch")

            sponsor_id = await _consume_invite_code(connection, invite_code)
            if sponsor_id == account_id:
                raise InvalidAccountStateError("Self-vouch is not allowed")
            sponsor = await _ensure_active_sponsor(connection, sponsor_id)
            await _validate_recovery_sponsor(
                connection=connection,
                account=account,
                sponsor=sponsor,
            )

            row = await connection.fetchrow(
                """
                UPDATE accounts
                SET sponsor_id = $1,
                    status = 'active',
                    trust_started_at = NOW(),
                    recovery_eligible_at = NULL,
                    updated_at = NOW()
                WHERE id = $2
                RETURNING *
                """,
                sponsor_id,
                account_id,
            )
            if row is None:
                raise ServiceError("Failed to revouch account")

            await _insert_event(connection, account_id, "revouched", {"sponsor_id": str(sponsor_id)})
            return _account_from_record(row)


async def convict_and_ban_tree(account_id: UUID, reason: str) -> tuple[UUID, list[UUID], UUID | None]:
    """Ban convicted root account, mark downstream as revouch_required, and penalize direct sponsor."""
    async with get_connection() as connection:
        async with connection.transaction():
            convicted_row = await connection.fetchrow("SELECT * FROM accounts WHERE id = $1 FOR UPDATE", account_id)
            if convicted_row is None:
                raise AccountNotFoundError("Account not found")

            convicted_account = _account_from_record(convicted_row)
            subtree_rows = await connection.fetch(
                """
                WITH RECURSIVE referral_tree AS (
                    SELECT id, sponsor_id
                    FROM accounts
                    WHERE id = $1
                    UNION ALL
                    SELECT child.id, child.sponsor_id
                    FROM accounts child
                    INNER JOIN referral_tree parent ON child.sponsor_id = parent.id
                )
                SELECT id
                FROM referral_tree
                """,
                account_id,
            )

            subtree_ids = [row["id"] for row in subtree_rows]
            downstream_ids = [candidate_id for candidate_id in subtree_ids if candidate_id != account_id]
            recovery_eligible_at = datetime.now(UTC).replace(tzinfo=None) + timedelta(hours=RECOVERY_COOLDOWN_HOURS)

            await connection.execute(
                """
                UPDATE accounts
                SET status = 'banned',
                    trust_started_at = NULL,
                    recovery_eligible_at = NULL,
                    updated_at = NOW()
                WHERE id = $1
                """,
                account_id,
            )
            if downstream_ids:
                await connection.execute(
                    """
                    UPDATE accounts
                    SET status = 'revouch_required',
                        trust_started_at = NULL,
                        recovery_eligible_at = $2,
                        updated_at = NOW()
                    WHERE id = ANY($1::uuid[]) AND status != 'banned'
                    """,
                    downstream_ids,
                    recovery_eligible_at,
                )

            await connection.execute(
                """
                UPDATE invite_codes
                SET is_active = FALSE
                WHERE sponsor_id = ANY($1::uuid[])
                """,
                subtree_ids,
            )

            penalized_sponsor_id: UUID | None = None
            if convicted_account.sponsor_id is not None:
                penalized_sponsor_id = convicted_account.sponsor_id
                await connection.execute(
                    """
                    UPDATE accounts
                    SET demerit_count = demerit_count + 1, updated_at = NOW()
                    WHERE id = $1
                    """,
                    penalized_sponsor_id,
                )
                await _insert_event(
                    connection,
                    penalized_sponsor_id,
                    "demerit_assessed",
                    {"convicted_account_id": str(account_id), "reason": reason},
                )

            await _insert_event(
                connection,
                account_id,
                "account_banned",
                {"root_convicted_account_id": str(account_id), "reason": reason},
            )

            for downstream_id in downstream_ids:
                await _insert_event(
                    connection,
                    downstream_id,
                    "revouch_required_due_to_upstream_ban",
                    {
                        "root_convicted_account_id": str(account_id),
                        "reason": reason,
                        "recovery_eligible_at": recovery_eligible_at.isoformat(),
                    },
                )

            return account_id, downstream_ids, penalized_sponsor_id


async def expire_inactive_sponsor_trees(inactivity_days: int) -> list[UUID]:
    """Mark descendants as revouch_required when sponsor has been inactive too long."""
    cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=inactivity_days)

    async with get_connection() as connection:
        async with connection.transaction():
            rows = await connection.fetch(
                """
                WITH RECURSIVE inactive_roots AS (
                    SELECT id
                    FROM accounts
                    WHERE status = 'active' AND last_active_at < $1
                ),
                affected AS (
                    SELECT child.id
                    FROM accounts child
                    INNER JOIN inactive_roots root ON child.sponsor_id = root.id
                    UNION
                    SELECT grandchild.id
                    FROM accounts grandchild
                    INNER JOIN affected parent ON grandchild.sponsor_id = parent.id
                ),
                updated AS (
                    UPDATE accounts
                    SET status = 'revouch_required',
                        trust_started_at = NULL,
                        recovery_eligible_at = NULL,
                        updated_at = NOW()
                    WHERE id IN (SELECT id FROM affected) AND status = 'active'
                    RETURNING id
                )
                SELECT id FROM updated
                """,
                cutoff,
            )

            marked_ids = [row["id"] for row in rows]
            for account_id in marked_ids:
                await _insert_event(
                    connection,
                    account_id,
                    "revouch_required_due_to_inactive_sponsor",
                    {"inactive_days": inactivity_days},
                )
            return marked_ids


def account_trust_days(account: Account) -> int:
    """Compute trust age in whole days for an account."""
    if account.trust_started_at is None:
        return 0
    now = datetime.now(UTC).replace(tzinfo=None)
    delta = now - account.trust_started_at
    return max(delta.days, 0)


async def _ensure_unique_account(
    connection: Connection,
    username: str,
    email: EmailStr,
    google_subject: str | None = None,
) -> None:
    row = await connection.fetchrow(
        """
        SELECT id
        FROM accounts
        WHERE username = $1 OR email = $2
        """,
        username,
        str(email),
    )
    if row is not None:
        raise DuplicateAccountError("Username or email already exists")

    if google_subject is not None:
        google_row = await connection.fetchrow(
            """
            SELECT id
            FROM accounts
            WHERE auth_provider = 'google' AND auth_provider_subject = $1
            """,
            google_subject,
        )
        if google_row is not None:
            raise DuplicateAccountError("Google account already exists")


async def _consume_invite_code(connection: Connection, invite_code: str) -> UUID:
    normalized = invite_code.strip()
    invite_row = await connection.fetchrow(
        """
        SELECT *
        FROM invite_codes
        WHERE code = $1
        FOR UPDATE
        """,
        normalized,
    )
    if invite_row is None:
        raise InvalidInviteCodeError("Invite code does not exist")

    invite = _invite_from_record(invite_row)
    now = datetime.now(UTC).replace(tzinfo=None)
    if not invite.is_active:
        raise InvalidInviteCodeError("Invite code is inactive")
    if invite.expires_at is not None and invite.expires_at < now:
        raise InvalidInviteCodeError("Invite code has expired")
    if invite.uses >= invite.max_uses:
        raise InvalidInviteCodeError("Invite code is fully used")

    await connection.execute(
        """
        UPDATE invite_codes
        SET uses = uses + 1,
            is_active = CASE WHEN uses + 1 >= max_uses THEN FALSE ELSE is_active END
        WHERE code = $1
        """,
        normalized,
    )
    return invite.sponsor_id


async def _ensure_active_sponsor(connection: Connection, sponsor_id: UUID) -> Account:
    sponsor_row = await connection.fetchrow(
        """
        SELECT *
        FROM accounts
        WHERE id = $1
        """,
        sponsor_id,
    )
    if sponsor_row is None:
        raise InvalidInviteCodeError("Invite sponsor account not found")

    sponsor = _account_from_record(sponsor_row)
    if sponsor.status is not AccountStatus.ACTIVE:
        raise InvalidInviteCodeError("Sponsor is not active")
    return sponsor


async def _validate_recovery_sponsor(connection: Connection, account: Account, sponsor: Account) -> None:
    if account.sponsor_id is not None and sponsor.id == account.sponsor_id:
        raise InvalidAccountStateError("Recovery requires a different sponsor")

    now = datetime.now(UTC).replace(tzinfo=None)
    if account.recovery_eligible_at is not None and now < account.recovery_eligible_at:
        raise InvalidAccountStateError("Recovery cooldown has not elapsed")

    sponsor_trust_days = account_trust_days(sponsor)
    if sponsor_trust_days < RECOVERY_SPONSOR_MIN_TRUST_DAYS:
        raise InvalidAccountStateError("Sponsor trust age is too low for recovery")
    if sponsor.demerit_count > RECOVERY_SPONSOR_MAX_DEMERITS:
        raise InvalidAccountStateError("Sponsor has too many demerits for recovery")


async def _insert_account(
    connection: Connection,
    username: str,
    email: EmailStr,
    password_hash: str | None,
    auth_provider: AuthProvider,
    auth_provider_subject: str | None,
    sponsor_id: UUID | None,
) -> Account:
    account_id = uuid4()
    row = await connection.fetchrow(
        """
        INSERT INTO accounts (
            id,
            username,
            email,
            password_hash,
            auth_provider,
            auth_provider_subject,
            sponsor_id,
            status,
            demerit_count,
            trust_started_at,
            last_active_at,
            created_at,
            updated_at
        )
        VALUES (
            $1, $2, $3, $4, $5, $6, $7,
            'active',
            0,
            NOW(),
            NOW(),
            NOW(),
            NOW()
        )
        RETURNING *
        """,
        account_id,
        username,
        str(email),
        password_hash,
        auth_provider.value,
        auth_provider_subject,
        sponsor_id,
    )
    if row is None:
        raise ServiceError("Account insert failed")
    return _account_from_record(row)


async def _insert_event(connection: Connection, account_id: UUID, event_type: str, payload: dict[str, str | int]) -> None:
    await connection.execute(
        """
        INSERT INTO account_events (id, account_id, event_type, payload)
        VALUES ($1, $2, $3, $4::jsonb)
        """,
        uuid4(),
        account_id,
        event_type,
        json.dumps(payload),
    )


def _account_from_record(row: Record) -> Account:
    return Account(
        id=row["id"],
        username=row["username"],
        email=EmailStr(row["email"]),
        password_hash=row["password_hash"],
        auth_provider=AuthProvider(row["auth_provider"]),
        auth_provider_subject=row["auth_provider_subject"],
        sponsor_id=row["sponsor_id"],
        status=AccountStatus(row["status"]),
        demerit_count=row["demerit_count"],
        trust_started_at=row["trust_started_at"],
        recovery_eligible_at=row["recovery_eligible_at"],
        last_active_at=row["last_active_at"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _invite_from_record(row: Record) -> InviteCode:
    return InviteCode(
        code=row["code"],
        sponsor_id=row["sponsor_id"],
        max_uses=row["max_uses"],
        uses=row["uses"],
        expires_at=row["expires_at"],
        is_active=row["is_active"],
        created_at=row["created_at"],
    )


def _social_from_record(row: Record) -> SocialIdentity:
    return SocialIdentity(
        id=row["id"],
        account_id=row["account_id"],
        provider=row["provider"],
        handle=row["handle"],
        provider_user_id=row["provider_user_id"],
        verified_at=row["verified_at"],
        created_at=row["created_at"],
    )
