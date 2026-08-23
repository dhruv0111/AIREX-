"""Authentication service (spec §33, §45; AT-004..AT-008)."""

from __future__ import annotations

from uuid import UUID

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
from app.models import User
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

    async def register(self, *, name: str, email: str, password: str) -> TokenResponse:
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
        await self._session.commit()
        return self._issue_tokens(user)

    async def login(self, *, email: str, password: str) -> TokenResponse:
        email_norm = email.strip().lower()
        user = await self._users.get_by_email(email_norm)
        # Same error for unknown email / wrong password (AT-007).
        if user is None or not self._hasher.verify_password(password, user.password_hash):
            raise AuthError("Invalid email or password.")
        await self._audit.record(
            action="user.login", user_id=user.id, resource_type="user", resource_id=user.id
        )
        await self._session.commit()
        return self._issue_tokens(user)

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

    def _issue_tokens(self, user: User) -> TokenResponse:
        access = create_access_token(self._settings, str(user.id))
        refresh = create_refresh_token(self._settings, str(user.id))
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
