"""Provider service (spec §17–§22; AT-P1-001..006, 026..028)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import decrypt_credentials, encrypt_credentials, mask_secret
from app.core.errors import ConflictError, ForbiddenError, NotFoundError, ValidationFailure
from app.core.permissions import CAP_MANAGE_PROVIDERS, require_capability
from app.integrations.gateway import ModelGatewayService
from app.integrations.provider import (
    ProviderType,
    build_adapter,
)
from app.repositories.audit import AuditRepository
from app.repositories.provider import ProviderRepository
from app.schemas.provider import (
    ProviderCreate,
    ProviderResponse,
    ProviderTestResult,
    ProviderUpdate,
)
from app.services.organization import OrganizationService


class ProviderService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._providers = ProviderRepository(session)
        self._audit = AuditRepository(session)
        self._orgs = OrganizationService(session)
        self._gateway = ModelGatewayService()

    async def _require_member(self, org_id: UUID, user_id: UUID, capability: str):
        role = await self._orgs.resolve_membership(org_id, user_id)
        if role is None:
            raise ForbiddenError("You do not have access to this organization.")
        require_capability(role, capability)
        return role

    def _adapter_config(self, provider: object, api_key: str | None, base_url: str | None) -> dict:
        cfg = dict(getattr(provider, "metadata_", None) or {})
        if api_key:
            cfg["api_key"] = api_key
        if base_url:
            cfg["base_url"] = base_url
        return cfg

    async def create(
        self, *, organization_id: UUID, user_id: UUID, payload: ProviderCreate
    ) -> ProviderResponse:
        await self._require_member(organization_id, user_id, CAP_MANAGE_PROVIDERS)
        try:
            pt = ProviderType(payload.provider_type)
        except ValueError:
            raise ValidationFailure("Unsupported provider type.")

        # Validate credentials before encrypting (no plaintext ever stored on failure).
        if pt != ProviderType.LOCAL:
            if not payload.api_key:
                raise ValidationFailure("api_key is required for this provider type.")
            adapter = build_adapter(
                pt.value, {"api_key": payload.api_key, "base_url": payload.base_url}
            )
            await adapter.validate_configuration(
                {"api_key": payload.api_key, "base_url": payload.base_url}
            )

        encrypted = encrypt_credentials(payload.api_key) if payload.api_key else None
        try:
            provider = await self._providers.create(
                organization_id=organization_id,
                provider_type=pt.value,
                name=payload.name,
                encrypted_credentials=encrypted,
                base_url=payload.base_url,
                configuration=payload.configuration or {},
                is_active=payload.is_active,
            )
        except IntegrityError:
            raise ConflictError("A provider with these details already exists.")

        await self._audit.record(
            action="PROVIDER_CREATED",
            organization_id=organization_id,
            user_id=user_id,
            resource_type="provider",
            resource_id=provider.id,
        )
        await self._session.commit()
        return self._to_response(provider)

    async def list(
        self,
        *,
        organization_id: UUID,
        user_id: UUID,
        page: int = 1,
        page_size: int = 20,
        provider_type: str | None = None,
        status: str | None = None,
    ) -> tuple[list[ProviderResponse], int]:
        await self._require_member(organization_id, user_id, "view_all")
        providers, total = await self._providers.list_for_organization(
            organization_id,
            page=page,
            page_size=page_size,
            provider_type=provider_type,
            status=status,
        )
        return [self._to_response(p) for p in providers], total

    async def get(
        self, *, organization_id: UUID, provider_id: UUID, user_id: UUID
    ) -> ProviderResponse:
        await self._require_member(organization_id, user_id, "view_all")
        provider = await self._providers.get_for_organization(provider_id, organization_id)
        if provider is None:
            raise NotFoundError("Provider was not found.")
        return self._to_response(provider)

    async def update(
        self,
        *,
        organization_id: UUID,
        provider_id: UUID,
        user_id: UUID,
        payload: ProviderUpdate,
    ) -> ProviderResponse:
        await self._require_member(organization_id, user_id, CAP_MANAGE_PROVIDERS)
        provider = await self._providers.get_for_organization(provider_id, organization_id)
        if provider is None:
            raise NotFoundError("Provider was not found.")
        if payload.name is not None:
            provider.name = payload.name
        if payload.base_url is not None:
            provider.base_url = payload.base_url
        if payload.configuration is not None:
            provider.metadata_ = payload.configuration
        if payload.status is not None:
            provider.status = payload.status
        if payload.is_active is not None:
            provider.is_active = payload.is_active
        await self._audit.record(
            action="PROVIDER_UPDATED",
            organization_id=organization_id,
            user_id=user_id,
            resource_type="provider",
            resource_id=provider_id,
        )
        await self._session.commit()
        return self._to_response(provider)

    async def delete(self, *, organization_id: UUID, provider_id: UUID, user_id: UUID) -> None:
        await self._require_member(organization_id, user_id, CAP_MANAGE_PROVIDERS)
        provider = await self._providers.get_for_organization(provider_id, organization_id)
        if provider is None:
            raise NotFoundError("Provider was not found.")
        await self._audit.record(
            action="PROVIDER_DELETED",
            organization_id=organization_id,
            user_id=user_id,
            resource_type="provider",
            resource_id=provider_id,
        )
        await self._session.delete(provider)
        await self._session.commit()

    async def test(
        self, *, organization_id: UUID, provider_id: UUID, user_id: UUID
    ) -> ProviderTestResult:
        await self._require_member(organization_id, user_id, CAP_MANAGE_PROVIDERS)
        provider = await self._providers.get_for_organization(provider_id, organization_id)
        if provider is None:
            raise NotFoundError("Provider was not found.")
        api_key = (
            decrypt_credentials(provider.encrypted_credentials)
            if provider.encrypted_credentials
            else None
        )
        cfg = self._adapter_config(provider, api_key, provider.base_url)
        adapter = build_adapter(provider.provider_type, cfg)
        now = datetime.now(UTC)
        try:
            await adapter.validate_configuration(cfg)
            health = await adapter.health_check()
            provider.last_connection_status = _to_connection_status(health.status)
            provider.last_checked_at = now
            provider.last_error = health.error
            await self._session.commit()
            return ProviderTestResult(
                status=provider.last_connection_status,
                provider=provider.provider_type,
                latency_ms=health.latency_ms or 0,
                error=health.error,
            )
        except Exception as exc:
            provider.last_connection_status = "UNKNOWN"
            provider.last_checked_at = now
            provider.last_error = str(exc)[:1000]
            await self._session.commit()
            return ProviderTestResult(
                status="UNKNOWN",
                provider=provider.provider_type,
                error=str(exc)[:1000],
            )

    async def rotate(
        self,
        *,
        organization_id: UUID,
        provider_id: UUID,
        user_id: UUID,
        new_api_key: str,
    ) -> ProviderResponse:
        await self._require_member(organization_id, user_id, CAP_MANAGE_PROVIDERS)
        provider = await self._providers.get_for_organization(provider_id, organization_id)
        if provider is None:
            raise NotFoundError("Provider was not found.")
        if provider.provider_type == ProviderType.LOCAL.value:
            raise ValidationFailure("Local provider has no credentials to rotate.")

        # Validate the new credential BEFORE replacing (spec §19 / AT-P1-027).
        adapter = build_adapter(
            provider.provider_type, {"api_key": new_api_key, "base_url": provider.base_url}
        )
        await adapter.validate_configuration(
            {"api_key": new_api_key, "base_url": provider.base_url}
        )

        provider.encrypted_credentials = encrypt_credentials(new_api_key)
        provider.credential_version = (provider.credential_version or 1) + 1
        await self._audit.record(
            action="PROVIDER_CREDENTIAL_ROTATED",
            organization_id=organization_id,
            user_id=user_id,
            resource_type="provider",
            resource_id=provider_id,
            metadata={"credential_version": provider.credential_version},
        )
        await self._session.commit()
        return self._to_response(provider)

    def _to_response(self, provider) -> ProviderResponse:
        return ProviderResponse(
            id=provider.id,
            organization_id=provider.organization_id,
            provider_type=provider.provider_type,
            name=provider.name,
            masked_key=(
                mask_secret(decrypt_credentials(provider.encrypted_credentials))
                if provider.encrypted_credentials
                else None
            ),
            base_url=provider.base_url,
            status=provider.status,
            last_connection_status=provider.last_connection_status,
            last_checked_at=provider.last_checked_at,
            last_error=provider.last_error,
            created_at=provider.created_at,
            updated_at=provider.updated_at,
        )


def _to_connection_status(health_status: str) -> str:
    # Connection tests report CONNECTED or UNKNOWN (AT-P1-005/006). Any
    # non-healthy outcome (degraded, unavailable, unknown) normalizes to UNKNOWN.
    return "CONNECTED" if health_status == "healthy" else "UNKNOWN"
