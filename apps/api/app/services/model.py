"""Model service (spec §23–§31; AT-P1-007..015, 029)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import decrypt_credentials
from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.core.logging import get_logger, request_id_ctx
from app.core.permissions import CAP_INVOKE_MODELS, CAP_MANAGE_MODELS, require_capability
from app.integrations.gateway import ModelGatewayService
from app.integrations.provider import (
    ModelRequest,
    ProviderError,
    RetryPolicy,
)
from app.models import Provider
from app.repositories.audit import AuditRepository
from app.repositories.project import ProjectRepository
from app.repositories.provider import ModelInvocationRepository, ModelRepository, ProviderRepository
from app.schemas.provider import (
    ModelCreate,
    ModelHealthResponse,
    ModelInvokeRequest,
    ModelInvokeResponse,
    ModelResponse,
    ModelTestResult,
    ModelUpdate,
    ModelUsage,
)
from app.services.organization import OrganizationService

logger = get_logger("models")


class ModelService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._models = ModelRepository(session)
        self._providers = ProviderRepository(session)
        self._projects = ProjectRepository(session)
        self._invocations = ModelInvocationRepository(session)
        self._audit = AuditRepository(session)
        self._orgs = OrganizationService(session)
        self._gateway = ModelGatewayService()

    async def _require_member(self, org_id: UUID, user_id: UUID, capability: str):
        role = await self._orgs.resolve_membership(org_id, user_id)
        if role is None:
            raise ForbiddenError("You do not have access to this organization.")
        require_capability(role, capability)
        return role

    async def _get_project_org(self, project_id: UUID) -> UUID:
        project = await self._projects.get_by_id(project_id)
        if project is None:
            raise NotFoundError("Project was not found.")
        return project.organization_id

    async def _validate_provider_org(self, provider_id: UUID, org_id: UUID) -> Provider:
        provider = await self._providers.get_for_organization(provider_id, org_id)
        if provider is None:
            # Cross-organization provider is hidden (AT-P1-008).
            raise NotFoundError("Provider was not found.")
        return provider

    async def create(
        self,
        *,
        organization_id: UUID,
        project_id: UUID,
        user_id: UUID,
        payload: ModelCreate,
    ) -> ModelResponse:
        await self._require_member(organization_id, user_id, CAP_MANAGE_MODELS)
        project_org = await self._get_project_org(project_id)
        if project_org != organization_id:
            raise NotFoundError("Project was not found.")
        provider = await self._validate_provider_org(payload.provider_id, organization_id)

        try:
            model = await self._models.create(
                project_id=project_id,
                provider_id=provider.id,
                environment_id=payload.environment_id,
                name=payload.name,
                model_identifier=payload.model_identifier,
                configuration=payload.configuration or {},
            )
        except IntegrityError:
            raise ConflictError("A model with these details already exists.")
        await self._audit.record(
            action="MODEL_CREATED",
            organization_id=organization_id,
            user_id=user_id,
            resource_type="model",
            resource_id=model.id,
        )
        await self._session.commit()
        return self._to_response(model)

    async def list(
        self,
        *,
        organization_id: UUID,
        project_id: UUID,
        user_id: UUID,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
        provider: str | None = None,
    ) -> tuple[list[ModelResponse], int]:
        await self._require_member(organization_id, user_id, "view_all")
        project_org = await self._get_project_org(project_id)
        if project_org != organization_id:
            raise NotFoundError("Project was not found.")
        models, total = await self._models.list_for_project(
            project_id, page=page, page_size=page_size, status=status, provider=provider
        )
        return [self._to_response(m) for m in models], total

    async def get(self, *, organization_id: UUID, model_id: UUID, user_id: UUID) -> ModelResponse:
        await self._require_member(organization_id, user_id, "view_all")
        model = await self._models.get_by_id(model_id)
        if model is None or not await self._model_in_org(model, organization_id):
            raise NotFoundError("Model was not found.")
        return self._to_response(model)

    async def update(
        self,
        *,
        organization_id: UUID,
        model_id: UUID,
        user_id: UUID,
        payload: ModelUpdate,
    ) -> ModelResponse:
        await self._require_member(organization_id, user_id, CAP_MANAGE_MODELS)
        model = await self._models.get_by_id(model_id)
        if model is None or not await self._model_in_org(model, organization_id):
            raise NotFoundError("Model was not found.")
        if payload.name is not None:
            model.name = payload.name
        if payload.model_identifier is not None:
            model.model_identifier = payload.model_identifier
        if payload.environment_id is not None:
            model.environment_id = payload.environment_id
        if payload.configuration is not None:
            model.configuration = payload.configuration
        if payload.status is not None:
            model.status = payload.status
        await self._audit.record(
            action="MODEL_UPDATED",
            organization_id=organization_id,
            user_id=user_id,
            resource_type="model",
            resource_id=model_id,
        )
        await self._session.commit()
        return self._to_response(model)

    async def delete(self, *, organization_id: UUID, model_id: UUID, user_id: UUID) -> None:
        await self._require_member(organization_id, user_id, CAP_MANAGE_MODELS)
        model = await self._models.get_by_id(model_id)
        if model is None or not await self._model_in_org(model, organization_id):
            raise NotFoundError("Model was not found.")
        await self._audit.record(
            action="MODEL_DELETED",
            organization_id=organization_id,
            user_id=user_id,
            resource_type="model",
            resource_id=model_id,
        )
        await self._session.delete(model)
        await self._session.commit()

    async def test(
        self, *, organization_id: UUID, model_id: UUID, user_id: UUID
    ) -> ModelTestResult:
        await self._require_member(organization_id, user_id, CAP_MANAGE_MODELS)
        model = await self._models.get_by_id(model_id)
        if model is None or not await self._model_in_org(model, organization_id):
            raise NotFoundError("Model was not found.")
        provider = await self._providers.get_for_organization(model.provider_id, organization_id)
        if provider is None:
            raise NotFoundError("Provider was not found.")
        api_key = (
            decrypt_credentials(provider.encrypted_credentials)
            if provider.encrypted_credentials
            else None
        )

        request = ModelRequest(
            model=model.model_identifier,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=8,
            timeout=float((model.configuration or {}).get("timeout", 30)),
        )
        try:
            response = await self._gateway.invoke(
                provider_type=provider.provider_type,
                api_key=api_key,
                base_url=provider.base_url,
                configuration={**(provider.metadata_ or {}), **(model.configuration or {})},
                request=request,
                retry_policy=RetryPolicy(max_retries=0),
            )
            model.last_health_status = "healthy"
            model.last_latency_ms = response.latency_ms
            model.last_checked_at = datetime.now(UTC)
            await self._session.commit()
            return ModelTestResult(
                status="CONNECTED",
                provider=provider.provider_type,
                model=model.model_identifier,
                latency_ms=response.latency_ms,
            )
        except ProviderError as exc:
            model.last_health_status = "degraded"
            model.last_checked_at = datetime.now(UTC)
            model.last_latency_ms = 0
            await self._session.commit()
            return ModelTestResult(
                status="UNKNOWN",
                provider=provider.provider_type,
                model=model.model_identifier,
                error=exc.message,
            )

    async def invoke(
        self,
        *,
        organization_id: UUID,
        model_id: UUID,
        user_id: UUID,
        payload: ModelInvokeRequest,
        project_id: UUID | None = None,
    ) -> ModelInvokeResponse:
        await self._require_member(organization_id, user_id, CAP_INVOKE_MODELS)
        model = await self._models.get_by_id(model_id)
        if model is None or not await self._model_in_org(model, organization_id):
            raise NotFoundError("Model was not found.")
        if project_id is not None and model.project_id != project_id:
            raise NotFoundError("Model was not found.")
        project_id = project_id or model.project_id
        provider = await self._providers.get_for_organization(model.provider_id, organization_id)
        if provider is None:
            raise NotFoundError("Provider was not found.")
        api_key = (
            decrypt_credentials(provider.encrypted_credentials)
            if provider.encrypted_credentials
            else None
        )

        request = ModelRequest(
            model=model.model_identifier,
            messages=payload.messages,
            temperature=payload.temperature,
            max_tokens=payload.max_tokens,
            top_p=payload.top_p,
            timeout=float((model.configuration or {}).get("timeout", 30)),
        )
        request_id = request_id_ctx.get() or "req_unknown"
        try:
            response = await self._gateway.invoke(
                provider_type=provider.provider_type,
                api_key=api_key,
                base_url=provider.base_url,
                configuration={**(provider.metadata_ or {}), **(model.configuration or {})},
                request=request,
                retry_policy=self._retry_policy(model),
            )
        except ProviderError as exc:
            await self._invocations.record(
                request_id=request_id,
                organization_id=organization_id,
                project_id=project_id,
                model_id=model.id,
                provider=provider.provider_type,
                model=model.model_identifier,
                status="error",
                latency_ms=0,
                input_tokens=None,
                output_tokens=None,
                total_tokens=None,
                error_category=exc.category.value,
            )
            await self._session.commit()
            logger.warning(
                "model invocation failed",
                extra={"category": exc.category.value, "model_id": str(model_id)},
            )
            raise

        await self._invocations.record(
            request_id=request_id,
            organization_id=organization_id,
            project_id=project_id,
            model_id=model.id,
            provider=provider.provider_type,
            model=model.model_identifier,
            status="success",
            latency_ms=response.latency_ms,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            total_tokens=response.usage.total_tokens,
            error_category=None,
        )
        model.last_health_status = "healthy"
        model.last_checked_at = datetime.now(UTC)
        model.last_latency_ms = response.latency_ms
        await self._audit.record(
            action="MODEL_INVOKED",
            organization_id=organization_id,
            user_id=user_id,
            resource_type="model",
            resource_id=model_id,
        )
        await self._session.commit()
        return ModelInvokeResponse(
            id=response.id,
            provider=response.provider,
            model=response.model,
            content=response.content,
            finish_reason=response.finish_reason,
            usage=ModelUsage(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                total_tokens=response.usage.total_tokens,
            ),
            latency_ms=response.latency_ms,
            metadata=response.metadata,
            created_at=response.created_at,
        )

    async def health(
        self, *, organization_id: UUID, model_id: UUID, user_id: UUID
    ) -> ModelHealthResponse:
        await self._require_member(organization_id, user_id, "view_all")
        model = await self._models.get_by_id(model_id)
        if model is None or not await self._model_in_org(model, organization_id):
            raise NotFoundError("Model was not found.")
        provider = await self._providers.get_for_organization(model.provider_id, organization_id)
        if provider is None:
            raise NotFoundError("Provider was not found.")
        api_key = (
            decrypt_credentials(provider.encrypted_credentials)
            if provider.encrypted_credentials
            else None
        )
        health = await self._gateway.health(
            provider_type=provider.provider_type,
            api_key=api_key,
            base_url=provider.base_url,
            configuration=provider.metadata_,
            model=model.model_identifier,
        )
        model.last_health_status = health.status
        model.last_checked_at = datetime.now(UTC)
        await self._session.commit()
        return ModelHealthResponse(
            status=health.status,
            provider=health.provider,
            model=model.model_identifier,
            last_checked_at=datetime.fromisoformat(health.last_checked_at),
            latency_ms=health.latency_ms or None,
            error=health.error,
        )

    def _retry_policy(self, model) -> RetryPolicy:
        cfg = model.configuration or {}
        rp = cfg.get("retry_policy") or {}
        return RetryPolicy(
            max_retries=int(rp.get("max_retries", 2)),
            initial_delay_ms=int(rp.get("initial_delay_ms", 250)),
            max_delay_ms=int(rp.get("max_delay_ms", 5000)),
            backoff_multiplier=float(rp.get("backoff_multiplier", 2.0)),
        )

    async def _model_in_org(self, model, organization_id: UUID) -> bool:
        project = await self._projects.get_by_id(model.project_id)
        return bool(project and project.organization_id == organization_id)

    def _to_response(self, model) -> ModelResponse:
        return ModelResponse(
            id=model.id,
            project_id=model.project_id,
            provider_id=model.provider_id,
            environment_id=model.environment_id,
            name=model.name,
            model_identifier=model.model_identifier,
            configuration=model.configuration,
            status=model.status,
            last_health_status=model.last_health_status,
            last_checked_at=model.last_checked_at,
            last_latency_ms=model.last_latency_ms,
            is_active=model.is_active,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
