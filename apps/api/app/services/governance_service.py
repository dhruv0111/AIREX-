"""Governance Policies, Multi-Step Approvals & Access Review Service (Phase 13)."""

from __future__ import annotations

from datetime import datetime, UTC
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, ForbiddenError, NotFoundError, ValidationFailure
from app.models.ci import ServiceToken
from app.models.governance import (
    AccessReview,
    AccessReviewItem,
    ApprovalDecision,
    ApprovalRequest,
    ApprovalStep,
    GovernancePolicy,
)
from app.models.organization import OrganizationMember
from app.models.release_decision import ReleaseDecision
from app.models.team import TeamMember, TeamProjectAccess, UserProjectAccess
from app.models.user import User
from app.repositories.audit import AuditRepository


class GovernanceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.audit = AuditRepository(session)

    # ---------------------------------------------------------
    # Governance Policies
    # ---------------------------------------------------------
    async def create_policy(self, org_id: UUID, user_id: UUID, data: dict) -> GovernancePolicy:
        # Determine version number
        stmt = select(GovernancePolicy.version).where(
            and_(GovernancePolicy.organization_id == org_id, GovernancePolicy.name == data["name"])
        ).order_by(GovernancePolicy.version.desc())
        res = await self.session.execute(stmt)
        latest_ver = res.scalars().first()
        next_ver = (latest_ver or 0) + 1

        policy = GovernancePolicy(
            organization_id=org_id,
            name=data["name"],
            description=data.get("description"),
            version=next_ver,
            status="DRAFT",
            rules=data.get("rules") or {},
            created_by=user_id,
        )
        self.session.add(policy)
        await self.session.flush()

        await self.audit.record(
            action="policy.created",
            organization_id=org_id,
            user_id=user_id,
            resource_type="governance_policy",
            resource_id=policy.id,
            metadata={"name": policy.name, "version": policy.version},
        )
        await self.session.commit()
        await self.session.refresh(policy)
        return policy

    async def list_policies(self, org_id: UUID) -> list[GovernancePolicy]:
        stmt = select(GovernancePolicy).where(GovernancePolicy.organization_id == org_id).order_by(GovernancePolicy.name, GovernancePolicy.version.desc())
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def get_policy(self, org_id: UUID, policy_id: UUID) -> GovernancePolicy:
        stmt = select(GovernancePolicy).where(and_(GovernancePolicy.organization_id == org_id, GovernancePolicy.id == policy_id))
        res = await self.session.execute(stmt)
        policy = res.scalars().first()
        if not policy:
            raise NotFoundError("Governance policy not found.")
        return policy

    async def activate_policy(self, org_id: UUID, policy_id: UUID, user_id: UUID) -> GovernancePolicy:
        policy = await self.get_policy(org_id, policy_id)
        # Archive previous versions of the same policy
        stmt_prev = select(GovernancePolicy).where(
            and_(
                GovernancePolicy.organization_id == org_id,
                GovernancePolicy.name == policy.name,
                GovernancePolicy.id != policy.id,
                GovernancePolicy.status == "ACTIVE",
            )
        )
        res_prev = await self.session.execute(stmt_prev)
        for p in res_prev.scalars().all():
            p.status = "ARCHIVED"

        policy.status = "ACTIVE"
        await self.audit.record(
            action="policy.activated",
            organization_id=org_id,
            user_id=user_id,
            resource_type="governance_policy",
            resource_id=policy.id,
            metadata={"name": policy.name, "version": policy.version},
        )
        await self.session.commit()
        await self.session.refresh(policy)
        return policy

    async def disable_policy(self, org_id: UUID, policy_id: UUID, user_id: UUID) -> GovernancePolicy:
        policy = await self.get_policy(org_id, policy_id)
        policy.status = "DISABLED"
        await self.audit.record(
            action="policy.disabled",
            organization_id=org_id,
            user_id=user_id,
            resource_type="governance_policy",
            resource_id=policy.id,
            metadata={"name": policy.name, "version": policy.version},
        )
        await self.session.commit()
        await self.session.refresh(policy)
        return policy

    # ---------------------------------------------------------
    # Approval Workflows
    # ---------------------------------------------------------
    async def create_approval_request(self, org_id: UUID, requester_id: UUID, data: dict) -> ApprovalRequest:
        req = ApprovalRequest(
            organization_id=org_id,
            project_id=data.get("project_id"),
            target_type=data["target_type"],
            target_id=data["target_id"],
            title=data["title"],
            description=data.get("description"),
            status="PENDING",
            requester_id=requester_id,
            required_role=data.get("required_role", "ADMIN"),
            expires_at=data.get("expires_at"),
        )
        self.session.add(req)
        await self.session.flush()

        step = ApprovalStep(
            request_id=req.id,
            step_number=1,
            approver_role=req.required_role,
            status="PENDING",
        )
        self.session.add(step)
        await self.session.flush()

        await self.audit.record(
            action="approval.requested",
            organization_id=org_id,
            user_id=requester_id,
            resource_type="approval_request",
            resource_id=req.id,
            metadata={"target_type": req.target_type, "target_id": req.target_id, "title": req.title},
        )
        await self.session.commit()
        await self.session.refresh(req)
        return req

    async def list_approval_requests(self, org_id: UUID, status: str | None = None) -> list[ApprovalRequest]:
        stmt = select(ApprovalRequest).where(ApprovalRequest.organization_id == org_id)
        if status:
            stmt = stmt.where(ApprovalRequest.status == status)
        stmt = stmt.order_by(ApprovalRequest.created_at.desc())
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def get_approval_request(self, org_id: UUID, request_id: UUID) -> ApprovalRequest:
        stmt = select(ApprovalRequest).where(and_(ApprovalRequest.organization_id == org_id, ApprovalRequest.id == request_id))
        res = await self.session.execute(stmt)
        req = res.scalars().first()
        if not req:
            raise NotFoundError("Approval request not found.")
        return req

    async def act_on_approval(self, org_id: UUID, request_id: UUID, approver_id: UUID, outcome: str, comments: str | None = None) -> ApprovalRequest:
        req = await self.get_approval_request(org_id, request_id)
        if req.status != "PENDING":
            raise ConflictError(f"Approval request is already {req.status}.")

        # CRITICAL SECURITY INVARIANT: Self-approval is strictly prohibited!
        if req.requester_id == approver_id:
            raise ForbiddenError("Self-approval is prohibited. An independent approver must decide this request.")

        decision = ApprovalDecision(
            request_id=req.id,
            decided_by=approver_id,
            outcome=outcome,
            comments=comments,
            decided_at=datetime.now(UTC),
        )
        self.session.add(decision)
        await self.session.flush()

        req.status = outcome  # APPROVED or REJECTED

        # If this is for a release decision, update the release decision state!
        if req.target_type == "RELEASE_DECISION":
            try:
                rel_uuid = UUID(req.target_id)
                rel_decision = await self.session.get(ReleaseDecision, rel_uuid)
                if rel_decision:
                    if outcome == "APPROVED":
                        rel_decision.outcome = "APPROVED"
                        rel_decision.status = "READY"
                    else:
                        rel_decision.outcome = "REJECTED"
                        rel_decision.status = "DECIDED"
            except (ValueError, TypeError):
                pass

        await self.audit.record(
            action=f"approval.{outcome.lower()}",
            organization_id=org_id,
            user_id=approver_id,
            resource_type="approval_request",
            resource_id=req.id,
            metadata={"outcome": outcome, "comments": comments},
        )

        # Automatically publish canonical compliance evidence (Phase 15)
        from app.services.evidence_service import publish_canonical_evidence
        await publish_canonical_evidence(
            session=self.session,
            organization_id=org_id,
            source_type="approval_request",
            source_id=str(req.id),
            project_id=req.project_id,
            metadata_summary={"outcome": outcome, "comments": comments, "title": req.title},
        )

        await self.session.commit()
        await self.session.refresh(req)
        return req

    # ---------------------------------------------------------
    # Access Review System
    # ---------------------------------------------------------
    async def create_access_review(self, org_id: UUID, user_id: UUID, title: str, due_date: datetime | None = None) -> AccessReview:
        review = AccessReview(
            organization_id=org_id,
            title=title,
            status="OPEN",
            due_date=due_date,
            created_by=user_id,
        )
        self.session.add(review)
        await self.session.flush()

        # Collect current organization memberships
        stmt_mems = select(OrganizationMember, User).join(User, User.id == OrganizationMember.user_id).where(OrganizationMember.organization_id == org_id)
        res_mems = await self.session.execute(stmt_mems)
        for mem, user in res_mems.all():
            item = AccessReviewItem(
                review_id=review.id,
                item_type="USER_MEMBERSHIP",
                subject_id=str(user.id),
                subject_name=f"{user.name} ({user.email})",
                context_info={"role": mem.role, "member_id": str(mem.id)},
                decision="NO_ACTION",
            )
            self.session.add(item)

        # Collect active service tokens
        stmt_tokens = select(ServiceToken).where(
            and_(ServiceToken.organization_id == org_id, ServiceToken.revoked_at.is_(None))
        )
        res_tokens = await self.session.execute(stmt_tokens)
        for token in res_tokens.scalars().all():
            item = AccessReviewItem(
                review_id=review.id,
                item_type="SERVICE_TOKEN",
                subject_id=str(token.id),
                subject_name=f"Token: {token.name} ({token.token_prefix}...)",
                context_info={"project_id": str(token.project_id), "scopes": token.scopes},
                decision="NO_ACTION",
            )
            self.session.add(item)

        await self.session.flush()
        await self.audit.record(
            action="access_review.created",
            organization_id=org_id,
            user_id=user_id,
            resource_type="access_review",
            resource_id=review.id,
            metadata={"title": review.title},
        )
        await self.session.commit()
        await self.session.refresh(review)
        return review

    async def list_access_reviews(self, org_id: UUID) -> list[AccessReview]:
        stmt = select(AccessReview).where(AccessReview.organization_id == org_id).order_by(AccessReview.created_at.desc())
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def get_access_review(self, org_id: UUID, review_id: UUID) -> AccessReview:
        stmt = select(AccessReview).where(and_(AccessReview.organization_id == org_id, AccessReview.id == review_id))
        res = await self.session.execute(stmt)
        review = res.scalars().first()
        if not review:
            raise NotFoundError("Access review campaign not found.")
        return review

    async def decide_item(self, org_id: UUID, review_id: UUID, item_id: UUID, user_id: UUID, decision: str, notes: str | None = None) -> AccessReviewItem:
        await self.get_access_review(org_id, review_id)
        stmt = select(AccessReviewItem).where(and_(AccessReviewItem.review_id == review_id, AccessReviewItem.id == item_id))
        res = await self.session.execute(stmt)
        item = res.scalars().first()
        if not item:
            raise NotFoundError("Access review item not found.")

        item.decision = decision
        item.decided_by = user_id
        item.decided_at = datetime.now(UTC)
        item.notes = notes

        await self.session.commit()
        await self.session.refresh(item)
        return item

    async def complete_access_review(self, org_id: UUID, review_id: UUID, user_id: UUID) -> AccessReview:
        review = await self.get_access_review(org_id, review_id)
        if review.status == "COMPLETED":
            raise ConflictError("Access review is already completed.")

        # Execute revocations for items marked REVOKE
        stmt_revokes = select(AccessReviewItem).where(
            and_(AccessReviewItem.review_id == review_id, AccessReviewItem.decision == "REVOKE")
        )
        res_revokes = await self.session.execute(stmt_revokes)
        for item in res_revokes.scalars().all():
            if item.item_type == "SERVICE_TOKEN":
                try:
                    tok_uuid = UUID(item.subject_id)
                    token = await self.session.get(ServiceToken, tok_uuid)
                    if token:
                        token.revoked_at = datetime.now(UTC)
                        await self.audit.record(
                            action="service_token.revoked",
                            organization_id=org_id,
                            user_id=user_id,
                            resource_type="service_token",
                            resource_id=token.id,
                            metadata={"reason": "Revoked via Access Review", "review_id": str(review_id)},
                        )
                except (ValueError, TypeError):
                    pass
            elif item.item_type == "USER_MEMBERSHIP":
                try:
                    target_user_id = UUID(item.subject_id)
                    stmt_mem = select(OrganizationMember).where(
                        and_(OrganizationMember.organization_id == org_id, OrganizationMember.user_id == target_user_id)
                    )
                    res_mem = await self.session.execute(stmt_mem)
                    mem = res_mem.scalars().first()
                    # Cannot revoke org OWNER
                    if mem and mem.role != "OWNER":
                        await self.session.delete(mem)
                        await self.audit.record(
                            action="organization_member.revoked",
                            organization_id=org_id,
                            user_id=user_id,
                            resource_type="organization_member",
                            resource_id=mem.id,
                            metadata={"target_user_id": str(target_user_id), "review_id": str(review_id)},
                        )
                except (ValueError, TypeError):
                    pass

        review.status = "COMPLETED"
        review.completed_at = datetime.now(UTC)
        await self.audit.record(
            action="access_review.completed",
            organization_id=org_id,
            user_id=user_id,
            resource_type="access_review",
            resource_id=review.id,
            metadata={"title": review.title},
        )
        await self.session.commit()
        await self.session.refresh(review)
        return review
