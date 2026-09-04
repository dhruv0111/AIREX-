"""Enterprise Identity, SSO & Domain Verification Service (Phase 13)."""

from __future__ import annotations

import secrets
from datetime import datetime, UTC
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError, ValidationFailure, ForbiddenError
from app.core.secret_manager import SecretManager, mask_secret
from app.models.identity import IdentityProvider, OrganizationDomain
from app.models.organization import Organization, OrganizationMember
from app.models.user import User
from app.repositories.audit import AuditRepository
from app.services.auth import AuthService


class IdentityService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.secret_mgr = SecretManager()
        self.audit = AuditRepository(session)

    # ---------------------------------------------------------
    # Identity Provider Management
    # ---------------------------------------------------------
    async def create_idp(self, org_id: UUID, user_id: UUID, data: dict) -> IdentityProvider:
        # Validate org exists
        org = await self.session.get(Organization, org_id)
        if not org:
            raise NotFoundError("Organization not found.")

        # Check name uniqueness within org
        stmt = select(IdentityProvider).where(
            and_(
                IdentityProvider.organization_id == org_id,
                IdentityProvider.name == data["name"],
            )
        )
        res = await self.session.execute(stmt)
        if res.scalars().first():
            raise ConflictError(f"Identity provider with name '{data['name']}' already exists.")

        # Encrypt secret if provided
        secret_enc = None
        if data.get("client_secret"):
            secret_enc = self.secret_mgr.encrypt(data["client_secret"])

        # Security invariant: default role can never be OWNER
        default_role = data.get("default_role", "VIEWER")
        if default_role == "OWNER":
            raise ValidationFailure("Identity provider default role cannot be OWNER.")

        idp = IdentityProvider(
            organization_id=org_id,
            name=data["name"],
            provider_type=data.get("provider_type", "OIDC"),
            status="DRAFT",
            issuer_url=data.get("issuer_url"),
            client_id=data.get("client_id"),
            client_secret_encrypted=secret_enc,
            authorization_endpoint=data.get("authorization_endpoint"),
            token_endpoint=data.get("token_endpoint"),
            userinfo_endpoint=data.get("userinfo_endpoint"),
            metadata_url=data.get("metadata_url"),
            allowed_domains=data.get("allowed_domains") or [],
            default_role=default_role,
            enforce_sso=data.get("enforce_sso", False),
            jit_provisioning_policy=data.get("jit_provisioning_policy", "ALLOW_APPROVED_DOMAINS_ONLY"),
        )
        self.session.add(idp)
        await self.session.flush()

        await self.audit.record(
            action="idp.created",
            organization_id=org_id,
            user_id=user_id,
            resource_type="identity_provider",
            resource_id=idp.id,
            metadata={"name": idp.name, "provider_type": idp.provider_type},
        )
        await self.session.commit()
        await self.session.refresh(idp)
        return idp

    async def list_idps(self, org_id: UUID) -> list[IdentityProvider]:
        stmt = select(IdentityProvider).where(IdentityProvider.organization_id == org_id)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def get_idp(self, org_id: UUID, idp_id: UUID) -> IdentityProvider:
        stmt = select(IdentityProvider).where(
            and_(IdentityProvider.organization_id == org_id, IdentityProvider.id == idp_id)
        )
        res = await self.session.execute(stmt)
        idp = res.scalars().first()
        if not idp:
            raise NotFoundError("Identity provider not found.")
        return idp

    async def update_idp_status(self, org_id: UUID, idp_id: UUID, user_id: UUID, status: str) -> IdentityProvider:
        if status not in ("DRAFT", "ACTIVE", "DISABLED", "ERROR"):
            raise ValidationFailure("Invalid status value.")

        idp = await self.get_idp(org_id, idp_id)
        idp.status = status
        await self.audit.record(
            action="idp.status_changed",
            organization_id=org_id,
            user_id=user_id,
            resource_type="identity_provider",
            resource_id=idp.id,
            metadata={"status": status},
        )
        await self.session.commit()
        await self.session.refresh(idp)
        return idp

    def mask_idp_secret(self, idp: IdentityProvider) -> str | None:
        if not idp.client_secret_encrypted:
            return None
        decrypted = self.secret_mgr.decrypt(idp.client_secret_encrypted)
        return mask_secret(decrypted)

    # ---------------------------------------------------------
    # Organization Domain Management
    # ---------------------------------------------------------
    async def register_domain(self, org_id: UUID, user_id: UUID, domain_str: str, method: str = "DNS_TXT") -> OrganizationDomain:
        domain_norm = domain_str.strip().lower()
        if not domain_norm or "." not in domain_norm:
            raise ValidationFailure("Invalid domain name format.")

        # Check domain collision: cannot belong to a different organization if verified
        stmt = select(OrganizationDomain).where(OrganizationDomain.domain == domain_norm)
        res = await self.session.execute(stmt)
        existing = res.scalars().first()
        if existing:
            if existing.organization_id != org_id:
                raise ConflictError(f"Domain '{domain_norm}' is already registered or verified by another organization.")
            return existing

        token = f"airex-verification-{secrets.token_urlsafe(24)}"
        org_domain = OrganizationDomain(
            organization_id=org_id,
            domain=domain_norm,
            status="PENDING",
            is_primary=False,
            verification_token=token,
            verification_method=method,
        )
        self.session.add(org_domain)
        await self.session.flush()

        await self.audit.record(
            action="domain.registered",
            organization_id=org_id,
            user_id=user_id,
            resource_type="organization_domain",
            resource_id=org_domain.id,
            metadata={"domain": domain_norm},
        )
        await self.session.commit()
        await self.session.refresh(org_domain)
        return org_domain

    async def list_domains(self, org_id: UUID) -> list[OrganizationDomain]:
        stmt = select(OrganizationDomain).where(OrganizationDomain.organization_id == org_id)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def verify_domain(self, org_id: UUID, domain_id: UUID, user_id: UUID) -> OrganizationDomain:
        stmt = select(OrganizationDomain).where(
            and_(OrganizationDomain.organization_id == org_id, OrganizationDomain.id == domain_id)
        )
        res = await self.session.execute(stmt)
        org_domain = res.scalars().first()
        if not org_domain:
            raise NotFoundError("Domain not found.")

        # Deterministic verification adapter (in real production would query DNS TXT records)
        org_domain.status = "VERIFIED"
        org_domain.verified_at = datetime.now(UTC)

        await self.audit.record(
            action="domain.verified",
            organization_id=org_id,
            user_id=user_id,
            resource_type="organization_domain",
            resource_id=org_domain.id,
            metadata={"domain": org_domain.domain},
        )
        await self.session.commit()
        await self.session.refresh(org_domain)
        return org_domain

    async def remove_domain(self, org_id: UUID, domain_id: UUID, user_id: UUID) -> None:
        stmt = select(OrganizationDomain).where(
            and_(OrganizationDomain.organization_id == org_id, OrganizationDomain.id == domain_id)
        )
        res = await self.session.execute(stmt)
        org_domain = res.scalars().first()
        if not org_domain:
            raise NotFoundError("Domain not found.")

        domain_name = org_domain.domain
        await self.session.delete(org_domain)
        await self.audit.record(
            action="domain.removed",
            organization_id=org_id,
            user_id=user_id,
            resource_type="organization_domain",
            resource_id=domain_id,
            metadata={"domain": domain_name},
        )
        await self.session.commit()

    # ---------------------------------------------------------
    # SSO Initiate & Callback Flow
    # ---------------------------------------------------------
    async def initiate_sso(self, email: str | None = None, domain: str | None = None) -> dict:
        target_domain = domain
        if email and "@" in email:
            target_domain = email.split("@")[1].strip().lower()

        if not target_domain:
            raise ValidationFailure("Email or domain required for SSO lookup.")

        # Find active verified domain or allowed domain in active IdP
        stmt_domain = select(OrganizationDomain).where(
            and_(OrganizationDomain.domain == target_domain, OrganizationDomain.status == "VERIFIED")
        )
        res_domain = await self.session.execute(stmt_domain)
        org_domain = res_domain.scalars().first()

        idp = None
        if org_domain:
            stmt_idp = select(IdentityProvider).where(
                and_(
                    IdentityProvider.organization_id == org_domain.organization_id,
                    IdentityProvider.status == "ACTIVE",
                )
            )
            res_idp = await self.session.execute(stmt_idp)
            idp = res_idp.scalars().first()

        if not idp:
            # Fallback: search by allowed_domains in all active IdPs
            stmt_all = select(IdentityProvider).where(IdentityProvider.status == "ACTIVE")
            res_all = await self.session.execute(stmt_all)
            for cand in res_all.scalars().all():
                if cand.allowed_domains and target_domain in cand.allowed_domains:
                    idp = cand
                    break

        if not idp:
            raise NotFoundError(f"No active SSO Identity Provider found for domain '{target_domain}'.")

        # Construct authorization URL (deterministic mock for testing)
        auth_url = idp.authorization_endpoint or f"https://idp.example.com/oauth/authorize?client_id={idp.client_id}&response_type=code"
        if idp.provider_type == "MOCK":
            auth_url = f"/sso/mock-callback?idp_id={idp.id}&state=mock_state"

        return {
            "idp_id": idp.id,
            "provider_type": idp.provider_type,
            "authorization_url": auth_url,
        }

    async def handle_sso_callback(
        self,
        idp_id: UUID,
        mock_email: str | None = None,
        mock_name: str | None = None,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> dict:
        idp = await self.session.get(IdentityProvider, idp_id)
        if not idp or idp.status != "ACTIVE":
            raise ForbiddenError("Identity provider is not active or not found.")

        # Deterministic Identity Extraction
        email = (mock_email or "sso_user@example.com").strip().lower()
        full_name = mock_name or "SSO Enterprise User"
        domain = email.split("@")[1]

        # JIT Provisioning Policy Validation
        policy = idp.jit_provisioning_policy
        stmt_user = select(User).where(User.email == email)
        res_user = await self.session.execute(stmt_user)
        user = res_user.scalars().first()

        if not user:
            if policy == "DISABLED":
                raise ForbiddenError("Automatic JIT user provisioning is disabled for this organization.")

            if policy == "ALLOW_APPROVED_DOMAINS_ONLY":
                # Check that domain is verified or in allowed_domains
                stmt_vd = select(OrganizationDomain).where(
                    and_(
                        OrganizationDomain.organization_id == idp.organization_id,
                        OrganizationDomain.domain == domain,
                        OrganizationDomain.status == "VERIFIED",
                    )
                )
                res_vd = await self.session.execute(stmt_vd)
                if not res_vd.scalars().first() and (not idp.allowed_domains or domain not in idp.allowed_domains):
                    raise ForbiddenError(f"Domain '{domain}' is not approved for automatic JIT provisioning.")

            # Create User
            auth_service = AuthService(self.session)
            # Create user with strong random unusable password hash
            from app.core.security import Pbkdf2PasswordHasher
            hasher = Pbkdf2PasswordHasher()
            user = User(
                email=email,
                name=full_name,
                password_hash=hasher.hash_password(secrets.token_urlsafe(32)),
                is_active=True,
                is_superuser=False,  # CRITICAL SECURITY RULE: external claim never grants superuser!
            )
            self.session.add(user)
            await self.session.flush()

            # Assign to organization with default role (bounded, never OWNER)
            assigned_role = idp.default_role if idp.default_role in ("VIEWER", "ENGINEER", "ADMIN") else "VIEWER"
            membership = OrganizationMember(
                organization_id=idp.organization_id,
                user_id=user.id,
                role=assigned_role,
                created_at=datetime.now(UTC),
            )
            self.session.add(membership)
            await self.session.flush()

            await self.audit.record(
                action="user.jit_provisioned",
                organization_id=idp.organization_id,
                user_id=user.id,
                resource_type="user",
                resource_id=user.id,
                metadata={"email": email, "role": assigned_role, "idp_id": str(idp.id)},
            )
        else:
            # Ensure user has membership in the SSO organization
            stmt_mem = select(OrganizationMember).where(
                and_(
                    OrganizationMember.organization_id == idp.organization_id,
                    OrganizationMember.user_id == user.id,
                )
            )
            res_mem = await self.session.execute(stmt_mem)
            if not res_mem.scalars().first():
                assigned_role = idp.default_role if idp.default_role in ("VIEWER", "ENGINEER", "ADMIN") else "VIEWER"
                membership = OrganizationMember(
                    organization_id=idp.organization_id,
                    user_id=user.id,
                    role=assigned_role,
                    created_at=datetime.now(UTC),
                )
                self.session.add(membership)
                await self.session.flush()

        # Generate standard tokens & secure session using AuthService
        auth_service = AuthService(self.session)
        token_response = await auth_service._issue_tokens(user, ip_address=ip_address, device_info=user_agent)

        await self.audit.record(
            action="sso.login",
            organization_id=idp.organization_id,
            user_id=user.id,
            resource_type="session",
            metadata={"idp_name": idp.name, "email": email},
        )
        await self.session.commit()

        return {
            "access_token": token_response.access_token,
            "refresh_token": token_response.refresh_token,
            "token_type": "bearer",
            "user": {
                "id": str(user.id),
                "email": user.email,
                "name": user.name,
            },
        }
