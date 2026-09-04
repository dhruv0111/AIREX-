"""REST API endpoints for Identity Providers, Domains, and SSO (Phase 13)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_active_organization, get_current_user
from app.core.permissions import Role, require_capability, CAP_MANAGE_IDENTITY, CAP_MANAGE_DOMAINS
from app.db.session import get_db
from app.models.user import User
from app.schemas.identity import (
    DomainCreate,
    DomainResponse,
    IdentityProviderCreate,
    IdentityProviderResponse,
    SSOCallbackRequest,
    SSOInitiateRequest,
    SSOInitiateResponse,
)
from app.services.identity_service import IdentityService
from app.services.organization import OrganizationService

router = APIRouter(tags=["identity"])


def _serialize_idp(service: IdentityService, idp) -> IdentityProviderResponse:
    masked = service.mask_idp_secret(idp)
    return IdentityProviderResponse(
        id=idp.id,
        organization_id=idp.organization_id,
        name=idp.name,
        provider_type=idp.provider_type,
        status=idp.status,
        issuer_url=idp.issuer_url,
        client_id=idp.client_id,
        masked_client_secret=masked,
        authorization_endpoint=idp.authorization_endpoint,
        token_endpoint=idp.token_endpoint,
        userinfo_endpoint=idp.userinfo_endpoint,
        allowed_domains=idp.allowed_domains or [],
        default_role=idp.default_role,
        enforce_sso=idp.enforce_sso,
        jit_provisioning_policy=idp.jit_provisioning_policy,
        created_at=idp.created_at,
        updated_at=idp.updated_at,
    )


# ---------------------------------------------------------------------------
# Identity Providers
# ---------------------------------------------------------------------------
@router.post("/identity-providers", response_model=IdentityProviderResponse, status_code=status.HTTP_201_CREATED)
async def create_identity_provider(
    payload: IdentityProviderCreate,
    user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> IdentityProviderResponse:
    org_service = OrganizationService(session)
    role = await org_service.resolve_membership(org_id, user.id)
    require_capability(role or Role.VIEWER, CAP_MANAGE_IDENTITY)

    service = IdentityService(session)
    idp = await service.create_idp(org_id, user.id, payload.model_dump())
    return _serialize_idp(service, idp)


@router.get("/identity-providers", response_model=list[IdentityProviderResponse])
async def list_identity_providers(
    user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> list[IdentityProviderResponse]:
    service = IdentityService(session)
    idps = await service.list_idps(org_id)
    return [_serialize_idp(service, i) for i in idps]


@router.get("/identity-providers/{idp_id}", response_model=IdentityProviderResponse)
async def get_identity_provider(
    idp_id: UUID,
    user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> IdentityProviderResponse:
    service = IdentityService(session)
    idp = await service.get_idp(org_id, idp_id)
    return _serialize_idp(service, idp)


@router.patch("/identity-providers/{idp_id}/status", response_model=IdentityProviderResponse)
async def update_identity_provider_status(
    idp_id: UUID,
    status_val: str,
    user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> IdentityProviderResponse:
    org_service = OrganizationService(session)
    role = await org_service.resolve_membership(org_id, user.id)
    require_capability(role or Role.VIEWER, CAP_MANAGE_IDENTITY)

    service = IdentityService(session)
    idp = await service.update_idp_status(org_id, idp_id, user.id, status_val)
    return _serialize_idp(service, idp)


# ---------------------------------------------------------------------------
# Organization Domains
# ---------------------------------------------------------------------------
@router.post("/domains", response_model=DomainResponse, status_code=status.HTTP_201_CREATED)
async def register_domain(
    payload: DomainCreate,
    user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> DomainResponse:
    org_service = OrganizationService(session)
    role = await org_service.resolve_membership(org_id, user.id)
    require_capability(role or Role.VIEWER, CAP_MANAGE_DOMAINS)

    service = IdentityService(session)
    domain = await service.register_domain(org_id, user.id, payload.domain, payload.verification_method)
    return DomainResponse.model_validate(domain)


@router.get("/domains", response_model=list[DomainResponse])
async def list_domains(
    user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> list[DomainResponse]:
    service = IdentityService(session)
    domains = await service.list_domains(org_id)
    return [DomainResponse.model_validate(d) for d in domains]


@router.post("/domains/{domain_id}/verify", response_model=DomainResponse)
async def verify_domain(
    domain_id: UUID,
    user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> DomainResponse:
    org_service = OrganizationService(session)
    role = await org_service.resolve_membership(org_id, user.id)
    require_capability(role or Role.VIEWER, CAP_MANAGE_DOMAINS)

    service = IdentityService(session)
    domain = await service.verify_domain(org_id, domain_id, user.id)
    return DomainResponse.model_validate(domain)


@router.delete("/domains/{domain_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_domain(
    domain_id: UUID,
    user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> None:
    org_service = OrganizationService(session)
    role = await org_service.resolve_membership(org_id, user.id)
    require_capability(role or Role.VIEWER, CAP_MANAGE_DOMAINS)

    service = IdentityService(session)
    await service.remove_domain(org_id, domain_id, user.id)


# ---------------------------------------------------------------------------
# SSO Initiate & Callback (Public auth flow)
# ---------------------------------------------------------------------------
@router.post("/identity-providers/sso/initiate", response_model=SSOInitiateResponse)
async def initiate_sso(
    payload: SSOInitiateRequest,
    session: AsyncSession = Depends(get_db),
) -> SSOInitiateResponse:
    service = IdentityService(session)
    res = await service.initiate_sso(email=payload.email, domain=payload.domain)
    return SSOInitiateResponse(**res)


@router.post("/identity-providers/{idp_id}/sso/callback")
async def sso_callback(
    idp_id: UUID,
    payload: SSOCallbackRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
):
    service = IdentityService(session)
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    res = await service.handle_sso_callback(
        idp_id,
        mock_email=payload.mock_email,
        mock_name=payload.mock_name,
        user_agent=user_agent,
        ip_address=client_ip,
    )
    return res
