"""Login, refresh-token rotation with reuse detection, and logout."""

import uuid
from datetime import timedelta

from sqlalchemy.orm import Session

from app.audit.models import AuditOutcome
from app.audit.service import AuditService
from app.auth.models import RefreshToken
from app.auth.repository import RefreshTokenRepository
from app.auth.schemas import TokenResponse
from app.core.clock import utcnow
from app.core.config import Settings
from app.core.errors import InvalidCredentials, InvalidToken
from app.core.security import (
    create_access_token,
    hash_password,
    hash_refresh_token,
    new_refresh_token,
    password_needs_rehash,
    verify_against_dummy,
    verify_password,
)
from app.users.models import User
from app.users.repository import UserRepository, normalize_email


class AuthService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.users = UserRepository(session)
        self.tokens = RefreshTokenRepository(session)
        self.audit = AuditService(session)

    def login(self, email: str, password: str) -> TokenResponse:
        email = normalize_email(email)
        user = self.users.get_by_email(email)
        if user is None:
            verify_against_dummy(password, self.settings)
            valid = False
        else:
            valid = verify_password(user.password_hash, password, self.settings) and user.is_active

        if not valid or user is None:
            # Same error for unknown email, wrong password and deactivated account.
            self.audit.record_security_event(
                "auth.login",
                outcome=AuditOutcome.FAILURE,
                target_type="user" if user is not None else None,
                target_id=user.id if user is not None else None,
                details={"email": email},
            )
            raise InvalidCredentials()

        if password_needs_rehash(user.password_hash, self.settings):
            user.password_hash = hash_password(password, self.settings)

        tokens = self._issue(user, family_id=uuid.uuid4())
        self.audit.record("auth.login", actor=user, target_type="user", target_id=user.id)
        return tokens

    def refresh(self, raw_token: str) -> TokenResponse:
        now = utcnow()
        token = self.tokens.get_by_hash(hash_refresh_token(raw_token), for_update=True)
        if token is None:
            raise InvalidToken()

        if token.revoked_at is not None:
            # A rotated token came back: assume theft and kill the whole family.
            self.tokens.revoke_family(token.family_id, now)
            self.audit.record_security_event(
                "auth.refresh_reuse_detected",
                outcome=AuditOutcome.DENIED,
                target_type="user",
                target_id=token.user_id,
                details={"family_id": str(token.family_id)},
            )
            raise InvalidToken()

        user = self.users.get(token.user_id)
        if token.expires_at <= now or user is None or not user.is_active:
            raise InvalidToken()

        new_tokens, new_record = self._issue_with_record(user, family_id=token.family_id)
        token.revoked_at = now
        token.replaced_by_id = new_record.id
        return new_tokens

    def logout(self, user: User, raw_token: str) -> None:
        token = self.tokens.get_by_hash(hash_refresh_token(raw_token))
        if token is None or token.user_id != user.id:
            raise InvalidToken()
        self.tokens.revoke_family(token.family_id, utcnow())
        self.audit.record(
            "auth.logout",
            actor=user,
            target_type="user",
            target_id=user.id,
            details={"family_id": str(token.family_id)},
        )

    def revoke_all(self, user_id: uuid.UUID) -> None:
        self.tokens.revoke_all_for_user(user_id, utcnow())

    def _issue(self, user: User, family_id: uuid.UUID) -> TokenResponse:
        return self._issue_with_record(user, family_id)[0]

    def _issue_with_record(
        self, user: User, family_id: uuid.UUID
    ) -> tuple[TokenResponse, RefreshToken]:
        now = utcnow()
        access_token, expires_in = create_access_token(user.id, user.role, self.settings, now)
        raw, digest = new_refresh_token()
        record = self.tokens.add(
            RefreshToken(
                user_id=user.id,
                family_id=family_id,
                token_hash=digest,
                expires_at=now + timedelta(days=self.settings.refresh_token_ttl_days),
            )
        )
        response = TokenResponse(
            access_token=access_token, refresh_token=raw, expires_in=expires_in
        )
        return response, record
