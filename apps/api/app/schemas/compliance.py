"""Pydantic schemas for Compliance, Audit Intelligence & Data Governance (spec Phase 14)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

from app.core.classification import DataClassification
from app.core.sensitive_data import SensitiveDataAction


# --- Compliance Framework ---

class ComplianceFrameworkCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: str | None = None
    applicability: dict | None = None


class ComplianceFrameworkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    name: str
    version: int
    description: str | None = None
    applicability: dict | None = None
    owner_id: UUID | None = None
    status: str
    is_immutable: bool
    effective_date: datetime | None = None
    deprecated_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


# --- Compliance Control ---

class ComplianceControlCreate(BaseModel):
    control_id: str = Field(..., min_length=1, max_length=64)
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    category: str = "GOVERNANCE"
    risk_level: str = "MEDIUM"
    applicability: dict | None = None
    required_evidence_types: list[str] | None = None
    evaluation_frequency: str = "CONTINUOUS"


class ComplianceControlResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    framework_id: UUID
    control_id: str
    title: str
    description: str | None = None
    category: str
    risk_level: str
    applicability: dict | None = None
    required_evidence_types: list[str] | None = None
    evaluation_frequency: str
    owner_id: UUID | None = None
    status: str
    version: int
    created_at: datetime
    updated_at: datetime


# --- Compliance Evidence ---

class ComplianceEvidenceCreate(BaseModel):
    source_type: str
    source_id: str
    project_id: UUID | None = None
    data_classification: DataClassification = DataClassification.INTERNAL
    validity_window_days: int = 90
    metadata_summary: dict | None = None


class ComplianceEvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    project_id: UUID | None = None
    source_type: str
    source_id: str
    sha256_fingerprint: str
    data_classification: str
    validity_window_days: int
    collected_at: datetime
    expires_at: datetime
    freshness_status: str
    integrity_status: str
    metadata_summary: dict | None = None
    created_at: datetime


class EvidenceVerifyResponse(BaseModel):
    id: UUID
    integrity_status: str
    freshness_status: str
    verified_at: datetime
    computed_fingerprint: str
    expected_fingerprint: str
    source_found: bool


# --- Centralized Retention ---

class RetentionPolicyCreate(BaseModel):
    resource_type: str = Field(..., min_length=1, max_length=64)
    retention_days: int = Field(..., gt=0)
    description: str | None = None


class RetentionPolicyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    resource_type: str
    retention_days: int
    policy_version: int
    is_active: bool
    description: str | None = None
    created_at: datetime
    updated_at: datetime


class RetentionCleanupRequest(BaseModel):
    dry_run: bool = True
    resource_types: list[str] | None = None


class RetentionCleanupResponse(BaseModel):
    dry_run: bool
    scanned_records: int
    eligible_for_deletion: int
    protected_by_legal_hold: int
    deleted_records: int
    details: dict[str, int]


# --- Legal Holds ---

class LegalHoldCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    reason: str | None = None
    resource_type: str = Field(..., min_length=1, max_length=64)
    target_resource_id: str = Field(..., min_length=1, max_length=255)


class LegalHoldResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    title: str
    reason: str | None = None
    resource_type: str
    target_resource_id: str
    is_active: bool
    placed_by_id: UUID | None = None
    created_at: datetime
    released_at: datetime | None = None
    released_by_id: UUID | None = None


# --- Compliance Assessments ---

class ComplianceAssessmentCreate(BaseModel):
    framework_id: UUID
    title: str = Field(..., min_length=1, max_length=255)


class ComplianceAssessmentItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    assessment_id: UUID
    control_id: UUID
    status: str
    evidence_references: list[str] | None = None
    findings: str | None = None
    created_at: datetime


class ComplianceAssessmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    framework_id: UUID
    title: str
    status: str
    overall_score: float
    summary: dict | None = None
    assessed_by_id: UUID | None = None
    approved_by_id: UUID | None = None
    approved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ComplianceAssessmentDetailResponse(ComplianceAssessmentResponse):
    items: list[ComplianceAssessmentItemResponse] = []


class AssessmentActionRequest(BaseModel):
    action: str = Field(..., pattern="^(APPROVE|REJECT)$")
    comment: str | None = None


# --- Remediations ---

class ComplianceRemediationCreate(BaseModel):
    control_id: UUID
    assessment_id: UUID | None = None
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    severity: str = "MEDIUM"
    due_date: datetime | None = None


class ComplianceRemediationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    assessment_id: UUID | None = None
    control_id: UUID
    title: str
    description: str | None = None
    severity: str
    status: str
    owner_id: UUID | None = None
    due_date: datetime | None = None
    resolved_at: datetime | None = None
    resolution_notes: str | None = None
    accepted_risk_justification: str | None = None
    accepted_risk_approver_id: UUID | None = None
    accepted_risk_expires_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class RemediationResolveRequest(BaseModel):
    resolution_notes: str = Field(..., min_length=1)


class RemediationAcceptRiskRequest(BaseModel):
    justification: str = Field(..., min_length=1)
    expires_at: datetime | None = None


# --- Sensitive Data Inspection ---

class SensitiveDataInspectRequest(BaseModel):
    text: str
    action: SensitiveDataAction = SensitiveDataAction.REDACT
    custom_patterns: dict[str, str] | None = None


class SensitiveDataInspectResponse(BaseModel):
    output_text: str
    findings: list[dict]
    is_blocked: bool


# --- Audit Intelligence Timeline ---

class AuditTimelineItem(BaseModel):
    id: UUID
    timestamp: datetime
    category: str
    action: str
    actor_id: UUID | None = None
    actor_name: str | None = None
    organization_id: UUID | None = None
    project_id: UUID | None = None
    resource_type: str | None = None
    resource_id: str | None = None
    severity: str = "INFO"
    metadata: dict | None = None


class AuditTimelineResponse(BaseModel):
    total_events: int
    events: list[AuditTimelineItem]


# --- Compliance Reporting ---

class ComplianceReportResponse(BaseModel):
    organization_id: UUID
    framework_name: str
    framework_version: int
    assessment_title: str
    assessment_date: datetime
    overall_score: float
    status: str
    controls_total: int
    controls_compliant: int
    controls_non_compliant: int
    open_remediations: int
    accepted_risks: int
    control_matrix: list[dict]
    integrity_summary: dict
