from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from fastapi.security.api_key import APIKeyHeader
from jose import JWTError, jwt
from passlib.context import CryptContext

from src.config_secrets import ADMIN_BOOTSTRAP_KEY, JWT_ACCESS_TOKEN_EXPIRE_MINUTES, JWT_ALGORITHM, JWT_SECRET_KEY
from src.models.models import Account, AccountStatus

SECRET_KEY = JWT_SECRET_KEY
ALGORITHM = JWT_ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = JWT_ACCESS_TOKEN_EXPIRE_MINUTES

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login/password")
admin_key_header = APIKeyHeader(name="X-Admin-Key", auto_error=False)


class AuthError(HTTPException):
    """Authentication exception with WWW-Authenticate header."""

    def __init__(self, detail: str = "Could not validate credentials") -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a bcrypt hash."""
    return cast(bool, pwd_context.verify(plain_password, hashed_password))


def get_password_hash(password: str) -> str:
    """Hash a plain password with bcrypt."""
    return cast(str, pwd_context.hash(password))


def create_access_token(subject_account_id: UUID, expires_delta: timedelta | None = None) -> str:
    """Create signed JWT token for one account id."""
    expire_at = datetime.now(UTC) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode: dict[str, Any] = {
        "sub": str(subject_account_id),
        "exp": expire_at,
    }
    return cast(str, jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM))


async def get_current_account(token: Annotated[str, Depends(oauth2_scheme)]) -> Account:
    """Resolve current account from bearer JWT token."""
    from src.services.account_service import get_account_by_id

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise AuthError() from exc

    subject = payload.get("sub")
    if not isinstance(subject, str):
        raise AuthError()

    try:
        account_id = UUID(subject)
    except ValueError as exc:
        raise AuthError("Invalid token subject") from exc

    account = await get_account_by_id(account_id)
    if account is None:
        raise AuthError()
    if account.status is AccountStatus.BANNED:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is banned")
    return account


async def get_active_account(current_account: Annotated[Account, Depends(get_current_account)]) -> Account:
    """Require an active account to access endpoint."""
    if current_account.status is not AccountStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account must be active")
    return current_account


async def require_admin_key(admin_key: Annotated[str | None, Depends(admin_key_header)]) -> None:
    """Validate admin key for moderation/bootstrap endpoints."""
    if admin_key is None or admin_key != ADMIN_BOOTSTRAP_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin key")
