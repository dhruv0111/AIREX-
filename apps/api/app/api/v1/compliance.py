"""Compliance, Audit Intelligence & Data Governance REST APIs (spec Phase 14)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_active_organization, get_current_user, get_db
from app.core.permissions import (
    CAP_MANAGE_COMPLIANCE,
    CAP_RUN_COMPLIANCE_ASSESSMENTS,
    CAP_MANAGE_RETENTION,
    CAP_MANAGE_LEGAL_HOLDS,
    CAP_VIEW_AUDIT,
    CAP_EXPORT_COMPLIANCE_REPORTS,
    Role,
    require_capability,
)
from app.core.sensitive_data import enforce_sensitive_data_policy
from app.models.user import User
from app.schemas.compliance import (
    ComplianceFrameworkCreate,
    ComplianceFrameworkResponse,
    ComplianceControlCreate,
    ComplianceControlResponse,
    ComplianceEvidenceCreate,
    ComplianceEvidenceResponse,
    EvidenceVerifyResponse,
    RetentionPolicyCreate,
    RetentionPolicyResponse,
    RetentionCleanupRequest,
    RetentionCleanupResponse,
    LegalHoldCreate,
    LegalHoldResponse,
    ComplianceAssessmentCreate,
    ComplianceAssessmentResponse,
    ComplianceAssessmentDetailResponse,
    AssessmentActionRequest,
    ComplianceRemediationCreate,
    ComplianceRemediationResponse,
    RemediationResolveRequest,
    RemediationAcceptRiskRequest,
    SensitiveDataInspectRequest,
    SensitiveDataInspectResponse,
    AuditTimelineResponse,
)
from app.services.compliance_service import ComplianceService
from app.services.evidence_service import EvidenceService
from app.services.retention_service import RetentionService
from app.services.audit_intelligence_service import AuditIntelligenceService
from app.services.organization import OrganizationService

router = APIRouter(prefix="/compliance", tags=["compliance"])


# --- Frameworks ---

@router.get("/frameworks", response_model=list[ComplianceFrameworkResponse])
async def list_frameworks(
    user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> list[ComplianceFrameworkResponse]:
    service = ComplianceService(session)
    return await service.list_frameworks(org_id)


@router.post("/frameworks", response_model=ComplianceFrameworkResponse, status_code=status.HTTP_201_CREATED)
async def create_framework(
    payload: ComplianceFrameworkCreate,
    user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> ComplianceFrameworkResponse:
    org_service = OrganizationService(session)
    role = await org_service.resolve_membership(org_id, user.id)
    require_capability(role or Role.VIEWER, CAP_MANAGE_COMPLIANCE)

    service = ComplianceService(session)
    return await service.create_framework(
        organization_id=org_id,
        name=payload.name,
        description=payload.description,
        applicability=payload.applicability,
        owner_id=user.id,
    )


@router.post("/frameworks/{framework_id}/activate", response_model=ComplianceFrameworkResponse)
async def activate_framework(
    framework_id: UUID,
    user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> ComplianceFrameworkResponse:
    org_service = OrganizationService(session)
    role = await org_service.resolve_membership(org_id, user.id)
    require_capability(role or Role.VIEWER, CAP_MANAGE_COMPLIANCE)

    service = ComplianceService(session)
    return await service.activate_framework(org_id, framework_id)


# --- Controls ---

@router.get("/frameworks/{framework_id}/controls", response_model=list[ComplianceControlResponse])
async def list_controls(
    framework_id: UUID,
    user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> list[ComplianceControlResponse]:
    service = ComplianceService(session)
    return await service.list_controls(org_id, framework_id)


@router.post("/frameworks/{framework_id}/controls", response_model=ComplianceControlResponse, status_code=status.HTTP_201_CREATED)
async def create_control(
    framework_id: UUID,
    payload: ComplianceControlCreate,
    user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> ComplianceControlResponse:
    org_service = OrganizationService(session)
    role = await org_service.resolve_membership(org_id, user.id)
    require_capability(role or Role.VIEWER, CAP_MANAGE_COMPLIANCE)

    service = ComplianceService(session)
    return await service.create_control(
        organization_id=org_id,
        framework_id=framework_id,
        control_id=payload.control_id,
        title=payload.title,
        description=payload.description,
        category=payload.category,
        risk_level=payload.risk_level,
        applicability=payload.applicability,
        required_evidence_types=payload.required_evidence_types,
        evaluation_frequency=payload.evaluation_frequency,
        owner_id=user.id,
    )


# --- Evidence ---

@router.get("/evidence", response_model=list[ComplianceEvidenceResponse])
async def list_evidence(
    project_id: UUID | None = Query(None),
    source_type: str | None = Query(None),
    user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> list[ComplianceEvidenceResponse]:
    service = EvidenceService(session)
    return await service.list_evidence(org_id, project_id, source_type)


@router.post("/evidence", response_model=ComplianceEvidenceResponse, status_code=status.HTTP_201_CREATED)
async def record_evidence(
    payload: ComplianceEvidenceCreate,
    user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> ComplianceEvidenceResponse:
    org_service = OrganizationService(session)
    role = await org_service.resolve_membership(org_id, user.id)
    require_capability(role or Role.VIEWER, CAP_MANAGE_COMPLIANCE)

    service = EvidenceService(session)
    return await service.record_evidence(
        organization_id=org_id,
        source_type=payload.source_type,
        source_id=payload.source_id,
        project_id=payload.project_id,
        data_classification=payload.data_classification,
        validity_window_days=payload.validity_window_days,
        metadata_summary=payload.metadata_summary,
    )


@router.post("/evidence/{evidence_id}/verify", response_model=EvidenceVerifyResponse)
async def verify_evidence(
    evidence_id: UUID,
    user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> EvidenceVerifyResponse:
    service = EvidenceService(session)
    res = await service.verify_evidence_integrity(org_id, evidence_id)
    return EvidenceVerifyResponse(**res)


# --- Retention ---

@router.get("/retention", response_model=list[RetentionPolicyResponse])
async def list_retention_policies(
    user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> list[RetentionPolicyResponse]:
    service = RetentionService(session)
    return await service.list_policies(org_id)


@router.post("/retention", response_model=RetentionPolicyResponse, status_code=status.HTTP_201_CREATED)
async def create_retention_policy(
    payload: RetentionPolicyCreate,
    user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> RetentionPolicyResponse:
    org_service = OrganizationService(session)
    role = await org_service.resolve_membership(org_id, user.id)
    require_capability(role or Role.VIEWER, CAP_MANAGE_RETENTION)

    service = RetentionService(session)
    return await service.create_policy(
        organization_id=org_id,
        resource_type=payload.resource_type,
        retention_days=payload.retention_days,
        description=payload.description,
    )


@router.post("/retention/cleanup", response_model=RetentionCleanupResponse)
async def execute_retention_cleanup(
    payload: RetentionCleanupRequest,
    user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> RetentionCleanupResponse:
    org_service = OrganizationService(session)
    role = await org_service.resolve_membership(org_id, user.id)
    require_capability(role or Role.VIEWER, CAP_MANAGE_RETENTION)

    service = RetentionService(session)
    res = await service.execute_retention_cleanup(
        organization_id=org_id,
        dry_run=payload.dry_run,
        resource_types=payload.resource_types,
    )
    return RetentionCleanupResponse(**res)


# --- Legal Holds ---

@router.get("/legal-holds", response_model=list[LegalHoldResponse])
async def list_legal_holds(
    active_only: bool = Query(True),
    user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> list[LegalHoldResponse]:
    service = RetentionService(session)
    return await service.list_legal_holds(org_id, active_only=active_only)


@router.post("/legal-holds", response_model=LegalHoldResponse, status_code=status.HTTP_201_CREATED)
async def create_legal_hold(
    payload: LegalHoldCreate,
    user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> LegalHoldResponse:
    org_service = OrganizationService(session)
    role = await org_service.resolve_membership(org_id, user.id)
    require_capability(role or Role.VIEWER, CAP_MANAGE_LEGAL_HOLDS)

    service = RetentionService(session)
    return await service.create_legal_hold(
        organization_id=org_id,
        title=payload.title,
        reason=payload.reason,
        resource_type=payload.resource_type,
        target_resource_id=payload.target_resource_id,
        placed_by_id=user.id,
    )


@router.post("/legal-holds/{hold_id}/release", response_model=LegalHoldResponse)
async def release_legal_hold(
    hold_id: UUID,
    user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> LegalHoldResponse:
    org_service = OrganizationService(session)
    role = await org_service.resolve_membership(org_id, user.id)
    require_capability(role or Role.VIEWER, CAP_MANAGE_LEGAL_HOLDS)

    service = RetentionService(session)
    return await service.release_legal_hold(org_id, hold_id, released_by_id=user.id)


# --- Assessments ---

@router.get("/assessments", response_model=list[ComplianceAssessmentResponse])
async def list_assessments(
    user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> list[ComplianceAssessmentResponse]:
    service = ComplianceService(session)
    return await service.list_assessments(org_id)


@router.post("/assessments", response_model=ComplianceAssessmentResponse, status_code=status.HTTP_201_CREATED)
async def create_assessment(
    payload: ComplianceAssessmentCreate,
    user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> ComplianceAssessmentResponse:
    org_service = OrganizationService(session)
    role = await org_service.resolve_membership(org_id, user.id)
    require_capability(role or Role.VIEWER, CAP_RUN_COMPLIANCE_ASSESSMENTS)

    service = ComplianceService(session)
    return await service.create_assessment(
        organization_id=org_id,
        framework_id=payload.framework_id,
        title=payload.title,
        assessed_by_id=user.id,
    )


@router.post("/assessments/{assessment_id}/run", response_model=ComplianceAssessmentResponse)
async def run_assessment(
    assessment_id: UUID,
    user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> ComplianceAssessmentResponse:
    org_service = OrganizationService(session)
    role = await org_service.resolve_membership(org_id, user.id)
    require_capability(role or Role.VIEWER, CAP_RUN_COMPLIANCE_ASSESSMENTS)

    service = ComplianceService(session)
    return await service.execute_assessment(org_id, assessment_id)


@router.post("/assessments/{assessment_id}/action", response_model=ComplianceAssessmentResponse)
async def act_on_assessment(
    assessment_id: UUID,
    payload: AssessmentActionRequest,
    user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> ComplianceAssessmentResponse:
    org_service = OrganizationService(session)
    role = await org_service.resolve_membership(org_id, user.id)
    require_capability(role or Role.VIEWER, CAP_MANAGE_COMPLIANCE)

    service = ComplianceService(session)
    return await service.act_on_assessment(
        organization_id=org_id,
        assessment_id=assessment_id,
        action=payload.action,
        user_id=user.id,
        comment=payload.comment,
    )


# --- Remediations ---

@router.get("/remediations", response_model=list[ComplianceRemediationResponse])
async def list_remediations(
    status: str | None = Query(None),
    user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> list[ComplianceRemediationResponse]:
    service = ComplianceService(session)
    return await service.list_remediations(org_id, status=status)


@router.post("/remediations", response_model=ComplianceRemediationResponse, status_code=status.HTTP_201_CREATED)
async def create_remediation(
    payload: ComplianceRemediationCreate,
    user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> ComplianceRemediationResponse:
    org_service = OrganizationService(session)
    role = await org_service.resolve_membership(org_id, user.id)
    require_capability(role or Role.VIEWER, CAP_MANAGE_COMPLIANCE)

    service = ComplianceService(session)
    return await service.create_remediation(
        organization_id=org_id,
        control_id=payload.control_id,
        title=payload.title,
        description=payload.description,
        severity=payload.severity,
        assessment_id=payload.assessment_id,
        owner_id=user.id,
        due_date=payload.due_date,
    )


@router.post("/remediations/{remediation_id}/resolve", response_model=ComplianceRemediationResponse)
async def resolve_remediation(
    remediation_id: UUID,
    payload: RemediationResolveRequest,
    user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> ComplianceRemediationResponse:
    org_service = OrganizationService(session)
    role = await org_service.resolve_membership(org_id, user.id)
    require_capability(role or Role.VIEWER, CAP_MANAGE_COMPLIANCE)

    service = ComplianceService(session)
    return await service.resolve_remediation(
        organization_id=org_id,
        remediation_id=remediation_id,
        resolution_notes=payload.resolution_notes,
        user_id=user.id,
    )


@router.post("/remediations/{remediation_id}/accept-risk", response_model=ComplianceRemediationResponse)
async def accept_risk(
    remediation_id: UUID,
    payload: RemediationAcceptRiskRequest,
    user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> ComplianceRemediationResponse:
    org_service = OrganizationService(session)
    role = await org_service.resolve_membership(org_id, user.id)
    require_capability(role or Role.VIEWER, CAP_MANAGE_COMPLIANCE)

    service = ComplianceService(session)
    return await service.accept_risk(
        organization_id=org_id,
        remediation_id=remediation_id,
        justification=payload.justification,
        approver_id=user.id,
        expires_at=payload.expires_at,
    )


# --- Sensitive Data Inspection ---

@router.post("/sensitive-data/inspect", response_model=SensitiveDataInspectResponse)
async def inspect_sensitive_data(
    payload: SensitiveDataInspectRequest,
    user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_active_organization),
) -> SensitiveDataInspectResponse:
    out_text, findings, is_blocked = enforce_sensitive_data_policy(
        text=payload.text,
        action=payload.action,
        custom_patterns=payload.custom_patterns,
    )
    return SensitiveDataInspectResponse(
        output_text=out_text,
        findings=findings,
        is_blocked=is_blocked,
    )


# --- Audit Intelligence Timeline ---

@router.get("/audit/timeline", response_model=AuditTimelineResponse)
async def get_audit_timeline(
    project_id: UUID | None = Query(None),
    user_id: UUID | None = Query(None),
    resource_type: str | None = Query(None),
    action: str | None = Query(None),
    category: str | None = Query(None),
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> AuditTimelineResponse:
    org_service = OrganizationService(session)
    role = await org_service.resolve_membership(org_id, user.id)
    require_capability(role or Role.VIEWER, CAP_VIEW_AUDIT)

    service = AuditIntelligenceService(session)
    events, total = await service.query_timeline(
        organization_id=org_id,
        project_id=project_id,
        user_id=user_id,
        resource_type=resource_type,
        action=action,
        category=category,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )
    return AuditTimelineResponse(total_events=total, events=events)


# --- Reports Export ---

@router.get("/reports/export")
async def export_compliance_report(
    assessment_id: UUID = Query(...),
    format: str = Query("json", pattern="^(json|csv)$"),
    user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> Response:
    org_service = OrganizationService(session)
    role = await org_service.resolve_membership(org_id, user.id)
    require_capability(role or Role.VIEWER, CAP_EXPORT_COMPLIANCE_REPORTS)

    service = ComplianceService(session)
    content, media_type = await service.export_report(
        organization_id=org_id, assessment_id=assessment_id, format=format
    )

    filename = f"compliance_report_{assessment_id}.{format}"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
