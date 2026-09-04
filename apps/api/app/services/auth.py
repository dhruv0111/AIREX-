"""Authentication service (spec §33, §45; AT-004..AT-008; Phase 12)."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.errors import AuthError, ConflictError, NotFoundError
from app.core.events import DomainEvent, get_event_bus
from app.core.permissions import Role
from app.core.security import (
    Pbkdf2PasswordHasher,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.models import User, UserSession
from app.repositories.audit import AuditRepository
from app.repositories.organization import OrganizationRepository
from app.repositories.user import UserRepository
from app.schemas.auth import MeResponse, OrganizationMembership, TokenResponse, UserResponse


class AuthService:
    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._users = UserRepository(session)
        self._orgs = OrganizationRepository(session)
        self._audit = AuditRepository(session)
        self._hasher = Pbkdf2PasswordHasher()

    async def register(
        self,
        *,
        name: str,
        email: str,
        password: str,
        ip_address: str | None = None,
        device_info: str | None = None,
    ) -> TokenResponse:
        email_norm = email.strip().lower()
        if await self._users.get_by_email(email_norm):
            raise ConflictError(
                "A user with this email already exists.",
                details={"code": "USER_ALREADY_EXISTS"},
            )
        password_hash = self._hasher.hash_password(password)
        user = await self._users.create(email=email_norm, password_hash=password_hash, name=name)
        # Default organization + OWNER membership (spec §45).
        slug = self._org_slug(email_norm)
        org = await self._orgs.create(name=f"{name}'s Organization", slug=slug)
        await self._orgs.add_member(organization_id=org.id, user_id=user.id, role=Role.OWNER)
        get_event_bus().publish(
            DomainEvent(
                event_type="user.registered",
                aggregate_type="user",
                aggregate_id=str(user.id),
                payload={"email": user.email},
            )
        )
        await self._session.commit()
        await self._audit.record(
            action="user.registered",
            organization_id=org.id,
            user_id=user.id,
            resource_type="user",
            resource_id=user.id,
        )
        tokens = await self._issue_tokens(user, ip_address=ip_address, device_info=device_info)
        await self._session.commit()
        return tokens

    async def login(
        self,
        *,
        email: str,
        password: str,
        ip_address: str | None = None,
        device_info: str | None = None,
    ) -> TokenResponse:
        email_norm = email.strip().lower()
        user = await self._users.get_by_email(email_norm)
        # Same error for unknown email / wrong password (AT-007).
        if user is None or not self._hasher.verify_password(password, user.password_hash):
            raise AuthError("Invalid email or password.")
        await self._audit.record(
            action="user.login", user_id=user.id, resource_type="user", resource_id=user.id
        )
        tokens = await self._issue_tokens(user, ip_address=ip_address, device_info=device_info)
        await self._session.commit()
        return tokens

    async def logout(self, user_id: UUID | None) -> None:
        if user_id:
            await self._audit.record(
                action="user.logout", user_id=user_id, resource_type="user", resource_id=user_id
            )
            await self._session.commit()

    async def me(self, user_id: UUID) -> MeResponse:
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User was not found.")
        memberships = await self._orgs.list_memberships(user_id)
        return MeResponse(
            user=UserResponse.model_validate(user, from_attributes=True),
            memberships=[
                OrganizationMembership(organization_id=m.organization_id, role=m.role)
                for m in memberships
            ],
        )

    async def user_from_token(self, token: str) -> User:
        try:
            payload = decode_token(self._settings, token)
        except Exception:
            raise AuthError("Authentication failed.")
        if payload.get("type") != "access":
            raise AuthError("Authentication failed.")
        try:
            user = await self._users.get_by_id(UUID(payload["sub"]))
        except (ValueError, TypeError):
            raise AuthError("Authentication failed.")
        if user is None or not user.is_active:
            raise AuthError("User is not active.")
        return user

    # ------------------------------------------------------------- Session Management & Refresh Rotation
    async def refresh_tokens(
        self,
        refresh_token: str,
        ip_address: str | None = None,
        device_info: str | None = None,
    ) -> TokenResponse:
        """Rotate refresh token, invalidate old token, and detect replay/reuse."""
        try:
            payload = decode_token(self._settings, refresh_token)
        except Exception:
            raise AuthError("Invalid or expired refresh token.")
        if payload.get("type") != "refresh":
            raise AuthError("Token is not a valid refresh token.")

        try:
            user_id = UUID(payload["sub"])
        except (ValueError, TypeError):
            raise AuthError("Invalid token subject.")

        user = await self._users.get_by_id(user_id)
        if user is None or not user.is_active:
            raise AuthError("User is inactive or not found.")

        token_hash = hashlib.sha256(refresh_token.encode("utf-8")).hexdigest()
        stmt = select(UserSession).where(UserSession.refresh_token_hash == token_hash)
        res = await self._session.execute(stmt)
        user_sess = res.scalars().first()

        # Replay/Reuse Detection: if token was already revoked, revoke all sessions
        if user_sess is not None and user_sess.is_revoked:
            revoke_all_stmt = (
                update(UserSession)
                .where(UserSession.user_id == user_id)
                .values(is_revoked=True)
            )
            await self._session.execute(revoke_all_stmt)
            await self._audit.record(
                action="security.token_reuse_detected",
                user_id=user_id,
                resource_type="user_session",
                resource_id=user_sess.id,
            )
            await self._session.commit()
            raise AuthError("Token reuse detected. All active sessions have been revoked for security.")

        if user_sess is None:
            raise AuthError("Session not found or has expired.")

        # Check expiration
        now = datetime.now(UTC)
        if user_sess.expires_at.tzinfo is None:
            user_sess_expires = user_sess.expires_at.replace(tzinfo=UTC)
        else:
            user_sess_expires = user_sess.expires_at

        if user_sess_expires < now:
            user_sess.is_revoked = True
            await self._session.commit()
            raise AuthError("Refresh token has expired.")

        # Rotate: invalidate old session
        user_sess.is_revoked = True
        user_sess.last_used_at = now

        # Issue new token pair and record new session
        tokens = await self._issue_tokens(user, ip_address=ip_address, device_info=device_info)
        await self._audit.record(
            action="auth.token_refreshed",
            user_id=user.id,
            resource_type="user_session",
            resource_id=user_sess.id,
        )
        await self._session.commit()
        return tokens

    async def list_sessions(self, user_id: UUID) -> list[UserSession]:
        """List active/recent sessions for an authenticated user."""
        stmt = (
            select(UserSession)
            .where(UserSession.user_id == user_id)
            .order_by(desc(UserSession.last_used_at))
            .limit(50)
        )
        res = await self._session.execute(stmt)
        return list(res.scalars().all())

    async def revoke_session(self, user_id: UUID, session_id: UUID) -> bool:
        """Revoke a specific session."""
        stmt = select(UserSession).where(
            UserSession.id == session_id, UserSession.user_id == user_id
        )
        res = await self._session.execute(stmt)
        sess = res.scalars().first()
        if not sess:
            raise NotFoundError("Session not found.")
        sess.is_revoked = True
        await self._audit.record(
            action="auth.session_revoked",
            user_id=user_id,
            resource_type="user_session",
            resource_id=session_id,
        )
        await self._session.commit()
        return True

    async def revoke_all_sessions(self, user_id: UUID) -> int:
        """Revoke all sessions for a user."""
        stmt = (
            update(UserSession)
            .where(UserSession.user_id == user_id)
            .values(is_revoked=True)
        )
        res = await self._session.execute(stmt)
        await self._audit.record(
            action="auth.all_sessions_revoked",
            user_id=user_id,
            resource_type="user_session",
            resource_id=user_id,
        )
        await self._session.commit()
        return res.rowcount

    async def _issue_tokens(
        self,
        user: User,
        ip_address: str | None = None,
        device_info: str | None = None,
    ) -> TokenResponse:
        access = create_access_token(self._settings, str(user.id))
        refresh = create_refresh_token(self._settings, str(user.id))

        # Store SHA-256 hash of refresh token in user_sessions
        token_hash = hashlib.sha256(refresh.encode("utf-8")).hexdigest()
        now = datetime.now(UTC)
        expires_at = now + timedelta(minutes=self._settings.refresh_token_expire_minutes)

        session_entry = UserSession(
            user_id=user.id,
            refresh_token_hash=token_hash,
            device_info=device_info,
            ip_address=ip_address,
            is_revoked=False,
            created_at=now,
            expires_at=expires_at,
            last_used_at=now,
        )
        self._session.add(session_entry)

        return TokenResponse(
            access_token=access,
            refresh_token=refresh,
            token_type="bearer",
            expires_in=self._settings.access_token_expire_minutes * 60,
        )

    @staticmethod
    def _org_slug(email: str) -> str:
        local = email.split("@")[0]
        cleaned = "".join(c if c.isalnum() else "-" for c in local).strip("-").lower()
        return (cleaned or "org")[:60]
