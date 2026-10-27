"""Authentication and user registration services."""

from __future__ import annotations

import re
from uuid import UUID, uuid4

from app.application.exceptions import (
    AccountDisabledError,
    AuthenticationError,
    DuplicateUserError,
    EmailNotRegisteredError,
    InvalidCredentialsError,
    InvalidEmailError,
    TooManyLoginAttemptsError,
    UserNotFoundError,
    WrongPasswordError,
)
from app.application.login_throttle import login_throttle
from app.application.password_service import DUMMY_PASSWORD_HASH, hash_password, verify_password
from app.application.token_service import create_access_token, decode_access_token
from app.domain.models.user import AuthenticatedAccount, AuthMethod, User
from app.infrastructure.config import Settings, get_settings
from app.infrastructure.repositories.postgres_user_repository import PostgresUserRepository

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AuthService:
    def __init__(
        self,
        *,
        user_repository: PostgresUserRepository,
        settings: Settings | None = None,
    ) -> None:
        self._users = user_repository
        self._settings = settings or get_settings()

    def register_user(
        self,
        *,
        email: str,
        password: str,
        display_name: str | None = None,
    ) -> tuple[User, str]:
        normalized_email = email.strip().lower()
        self._validate_email(normalized_email)
        self._validate_password(password)
        if self._users.get_by_email(normalized_email) is not None:
            raise DuplicateUserError(normalized_email)

        user_id = uuid4()
        account_id = str(user_id)
        user = self._users.create(
            email=normalized_email,
            password_hash=hash_password(password),
            account_id=account_id,
            display_name=display_name,
        )
        token = self._issue_token(user)
        return user, token

    def login(self, *, email: str, password: str, ip: str = "unknown", remember: bool = False) -> tuple[User, str]:
        """Sign in with specific, user-facing failure reasons (invalid format / not registered / wrong password / locked)."""
        normalized_email = email.strip().lower()
        if not _EMAIL_PATTERN.match(normalized_email):
            raise InvalidEmailError()
        limit = max(1, self._settings.auth_max_login_failures)
        lockout = max(1, self._settings.auth_lockout_seconds)
        wait = login_throttle.retry_after(normalized_email, ip)
        if wait:
            raise TooManyLoginAttemptsError(wait)
        user = self._users.get_by_email(normalized_email)
        if user is None:
            verify_password(password, DUMMY_PASSWORD_HASH)  # keep timing similar
            self._fail(normalized_email, ip, limit, lockout)
            raise EmailNotRegisteredError()
        if not user.is_active:
            raise AccountDisabledError()
        if not verify_password(password, user.password_hash):
            left = self._fail(normalized_email, ip, limit, lockout, wrong_password=True)
            raise WrongPasswordError(left)
        login_throttle.success(normalized_email, ip)
        hours = self._settings.auth_remember_expiry_hours if remember else None
        return user, self._issue_token(user, expires_in_hours=hours)

    @staticmethod
    def _fail(email: str, ip: str, limit: int, lockout: int, *, wrong_password: bool = False) -> int | None:
        left = login_throttle.failure(email, ip, limit=limit, lockout=lockout)
        if left is None and login_throttle.retry_after(email, ip):
            raise TooManyLoginAttemptsError(login_throttle.retry_after(email, ip))
        return left

    def session_token(self, token: str) -> tuple[User, str, bool]:
        """Exchange a still-valid session (cookie) token for a fresh one; a "remember me" session stays a remember session."""
        try:
            payload = decode_access_token(token, secret=self._jwt_secret())
        except ValueError as exc:
            raise AuthenticationError(str(exc)) from exc
        user = self._users.get_by_id(UUID(str(payload["sub"])))
        if user is None or not user.is_active:
            raise AuthenticationError("User account is not active")
        import time

        remember = float(payload.get("exp", 0)) - time.time() > self._settings.auth_token_expiry_hours * 3600
        hours = self._settings.auth_remember_expiry_hours if remember else None
        return user, self._issue_token(user, expires_in_hours=hours), remember

    def login_with_google(self, *, email: str, display_name: str | None, remember: bool = False) -> tuple[User, str]:
        """Link a verified Google email to an existing user, or create a new one (caller has checked email_verified)."""
        import secrets

        normalized_email = email.strip().lower()
        self._validate_email(normalized_email)
        user = self._users.get_by_email(normalized_email)
        if user is None:
            user_id = uuid4()
            # Random unusable password; the user can still sign in with Google.
            user = self._users.create(
                email=normalized_email,
                password_hash=hash_password(secrets.token_urlsafe(32)),
                account_id=str(user_id),
                display_name=display_name,
            )
        elif not user.is_active:
            raise AccountDisabledError()
        hours = self._settings.auth_remember_expiry_hours if remember else None
        return user, self._issue_token(user, expires_in_hours=hours)

    def authenticate_bearer(self, token: str) -> AuthenticatedAccount:
        secret = self._jwt_secret()
        try:
            payload = decode_access_token(token, secret=secret)
        except ValueError as exc:
            raise AuthenticationError(str(exc)) from exc

        user_id = UUID(str(payload["sub"]))
        user = self._users.get_by_id(user_id)
        if user is None or not user.is_active:
            raise AuthenticationError("User account is not active")
        return AuthenticatedAccount(
            account_id=user.account_id,
            auth_method=AuthMethod.BEARER_TOKEN,
            user_id=user.id,
            email=user.email,
            display_name=user.display_name,
        )

    def get_user(self, user_id: UUID) -> User:
        user = self._users.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError(user_id)
        return user

    def resolve_legacy_actor(self, actor_id: str) -> AuthenticatedAccount:
        user = self._users.get_by_account_id(actor_id)
        if user is not None and user.is_active:
            return AuthenticatedAccount(
                account_id=user.account_id,
                auth_method=AuthMethod.LEGACY_ACTOR,
                user_id=user.id,
                email=user.email,
                display_name=user.display_name,
            )
        return AuthenticatedAccount(
            account_id=actor_id,
            auth_method=AuthMethod.LEGACY_ACTOR,
        )

    def _issue_token(self, user: User, *, expires_in_hours: int | None = None) -> str:
        return create_access_token(
            secret=self._jwt_secret(),
            account_id=user.account_id,
            user_id=user.id,
            email=user.email,
            display_name=user.display_name,
            expires_in_hours=expires_in_hours or self._settings.auth_token_expiry_hours,
        )

    def _jwt_secret(self) -> str:
        if self._settings.auth_jwt_secret is None:
            if self._settings.app_env.strip().lower() == "production":
                raise AuthenticationError("AUTH_JWT_SECRET must be configured in production")
            return "dev-only-auth-secret-change-me"
        return self._settings.auth_jwt_secret.get_secret_value()

    @staticmethod
    def _validate_email(email: str) -> None:
        if not _EMAIL_PATTERN.match(email):
            raise AuthenticationError("Email address is invalid")

    @staticmethod
    def _validate_password(password: str) -> None:
        if len(password) < 8:
            raise AuthenticationError("Password must be at least 8 characters")
