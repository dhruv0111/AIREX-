"""Provider, model and model-invocation repositories (tenant-scoped)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Model, ModelInvocation, Provider


class ProviderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        organization_id: UUID,
        provider_type: str,
        name: str,
        encrypted_credentials: str | None,
        base_url: str | None,
        configuration: dict,
        is_active: bool,
    ) -> Provider:
        provider = Provider(
            organization_id=organization_id,
            provider_type=provider_type,
            name=name,
            encrypted_credentials=encrypted_credentials,
            base_url=base_url,
            metadata_=configuration,
            status="ACTIVE",
            is_active=is_active,
        )
        self._session.add(provider)
        await self._session.flush()
        return provider

    async def get_by_id(self, provider_id: UUID) -> Provider | None:
        return await self._session.get(Provider, provider_id)

    async def get_for_organization(self, provider_id: UUID, org_id: UUID) -> Provider | None:
        result = await self._session.execute(
            select(Provider).where(Provider.id == provider_id, Provider.organization_id == org_id)
        )
        return result.scalar_one_or_none()

    async def list_for_organization(
        self,
        org_id: UUID,
        *,
        page: int = 1,
        page_size: int = 20,
        provider_type: str | None = None,
        status: str | None = None,
    ) -> tuple[list[Provider], int]:
        query = select(Provider).where(Provider.organization_id == org_id)
        count_query = (
            select(func.count()).select_from(Provider).where(Provider.organization_id == org_id)
        )
        if provider_type:
            query = query.where(Provider.provider_type == provider_type.upper())
            count_query = count_query.where(Provider.provider_type == provider_type.upper())
        if status:
            query = query.where(Provider.status == status.upper())
            count_query = count_query.where(Provider.status == status.upper())
        total = (await self._session.execute(count_query)).scalar_one()
        result = await self._session.execute(
            query.order_by(Provider.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), total


class ModelRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        project_id: UUID,
        provider_id: UUID,
        environment_id: UUID | None,
        name: str,
        model_identifier: str,
        configuration: dict,
    ) -> Model:
        model = Model(
            project_id=project_id,
            provider_id=provider_id,
            environment_id=environment_id,
            name=name,
            model_identifier=model_identifier,
            configuration=configuration,
            status="ACTIVE",
            is_active=True,
        )
        self._session.add(model)
        await self._session.flush()
        return model

    async def get_by_id(self, model_id: UUID) -> Model | None:
        return await self._session.get(Model, model_id)

    async def get_for_project(self, model_id: UUID, project_id: UUID) -> Model | None:
        result = await self._session.execute(
            select(Model).where(Model.id == model_id, Model.project_id == project_id)
        )
        return result.scalar_one_or_none()

    async def list_for_project(
        self,
        project_id: UUID,
        *,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
        provider: str | None = None,
    ) -> tuple[list[Model], int]:
        query = select(Model).where(Model.project_id == project_id)
        count_query = select(func.count()).select_from(Model).where(Model.project_id == project_id)
        if status:
            query = query.where(Model.status == status.upper())
            count_query = count_query.where(Model.status == status.upper())
        if provider:
            query = query.join(Provider, Model.provider_id == Provider.id).where(
                Provider.provider_type == provider.upper()
            )
            count_query = count_query.join(Provider, Model.provider_id == Provider.id).where(
                Provider.provider_type == provider.upper()
            )
        total = (await self._session.execute(count_query)).scalar_one()
        result = await self._session.execute(
            query.order_by(Model.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        )
        return list(result.scalars().all()), total


class ModelInvocationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(
        self,
        *,
        request_id: str,
        organization_id: UUID,
        project_id: UUID,
        model_id: UUID | None,
        provider: str,
        model: str,
        status: str,
        latency_ms: int | None,
        input_tokens: int | None,
        output_tokens: int | None,
        total_tokens: int | None,
        error_category: str | None,
    ) -> ModelInvocation:
        row = ModelInvocation(
            request_id=request_id,
            organization_id=organization_id,
            project_id=project_id,
            model_id=model_id,
            provider=provider,
            model=model,
            status=status,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            error_category=error_category,
            created_at=datetime.now(UTC),
        )
        self._session.add(row)
        await self._session.flush()
        return row
