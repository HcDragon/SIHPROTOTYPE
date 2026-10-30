"""Password hashing (Argon2id), access tokens (HS256 JWT), and refresh-token values."""

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import lru_cache

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.clock import utcnow
from app.core.config import Settings
from app.core.errors import InvalidToken

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_TYPE = "access"  # noqa: S105 (JWT "typ" claim value, not a secret)
_REQUIRED_CLAIMS = ["exp", "iat", "sub", "jti", "typ"]


# --- Passwords -------------------------------------------------------------------------------


@lru_cache(maxsize=4)
def _hasher(time_cost: int, memory_cost: int, parallelism: int) -> PasswordHasher:
    # argon2-cffi's PasswordHasher uses Argon2id by default.
    return PasswordHasher(time_cost=time_cost, memory_cost=memory_cost, parallelism=parallelism)


def password_hasher(settings: Settings) -> PasswordHasher:
    return _hasher(
        settings.argon2_time_cost, settings.argon2_memory_cost, settings.argon2_parallelism
    )


def hash_password(password: str, settings: Settings) -> str:
    return password_hasher(settings).hash(password)


def verify_password(password_hash: str, password: str, settings: Settings) -> bool:
    try:
        return password_hasher(settings).verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str, settings: Settings) -> bool:
    return password_hasher(settings).check_needs_rehash(password_hash)


@lru_cache(maxsize=4)
def _dummy_hash(time_cost: int, memory_cost: int, parallelism: int) -> str:
    return _hasher(time_cost, memory_cost, parallelism).hash(secrets.token_urlsafe(16))


def verify_against_dummy(password: str, settings: Settings) -> None:
    """Spend the same effort as a real check, so unknown emails are not faster to reject."""
    dummy = _dummy_hash(
        settings.argon2_time_cost, settings.argon2_memory_cost, settings.argon2_parallelism
    )
    verify_password(dummy, password, settings)


# --- Access tokens ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AccessClaims:
    user_id: uuid.UUID
    role: str
    token_id: str
    expires_at: datetime


def create_access_token(
    user_id: uuid.UUID, role: str, settings: Settings, now: datetime | None = None
) -> tuple[str, int]:
    """Return (token, lifetime in seconds)."""
    issued = now or utcnow()
    lifetime = timedelta(minutes=settings.access_token_ttl_minutes)
    payload = {
        "sub": str(user_id),
        "role": role,
        "iat": issued,
        "exp": issued + lifetime,
        "jti": uuid.uuid4().hex,
        "typ": ACCESS_TOKEN_TYPE,
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM)
    return token, int(lifetime.total_seconds())


def decode_access_token(token: str, settings: Settings) -> AccessClaims:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[JWT_ALGORITHM],
            options={"require": _REQUIRED_CLAIMS},
            leeway=0,
        )
        if payload["typ"] != ACCESS_TOKEN_TYPE:
            raise InvalidToken()
        return AccessClaims(
            user_id=uuid.UUID(payload["sub"]),
            role=str(payload.get("role", "")),
            token_id=str(payload["jti"]),
            expires_at=datetime.fromtimestamp(payload["exp"], tz=utcnow().tzinfo),
        )
    except (jwt.PyJWTError, ValueError, TypeError, KeyError):
        raise InvalidToken() from None


# --- Refresh tokens --------------------------------------------------------------------------


def new_refresh_token() -> tuple[str, str]:
    """Return (opaque token for the client, SHA-256 hex digest to store)."""
    raw = secrets.token_urlsafe(32)
    return raw, hash_refresh_token(raw)


def hash_refresh_token(raw: str) -> str:
    # A fast hash is appropriate: the token is 256 bits of randomness, not a password.
    return hashlib.sha256(raw.encode()).hexdigest()
