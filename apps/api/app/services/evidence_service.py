"""Evidence Registry & Lineage Service (spec Phase 14)."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, UTC
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.classification import DataClassification, enforce_classification_inheritance
from app.core.errors import NotFoundError, ValidationFailure
from app.models.compliance import ComplianceEvidence
from app.models.evaluation import EvaluationRun
from app.models.release_decision import ReleaseDecision
from app.models.governance import GovernancePolicy, ApprovalRequest, AccessReview
from app.models.agent import AgentRun
from app.models.dataset import DatasetVersion
from app.models.experiment import ExperimentRun
from app.models.benchmark import BenchmarkRun
from app.models.alert import Alert
from app.models.worker import TaskFailure, WorkerHeartbeat
from app.repositories.audit import AuditRepository


class EvidenceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.audit = AuditRepository(session)

    @staticmethod
    def compute_fingerprint(data: Any) -> str:
        """Deterministically compute SHA-256 fingerprint from data."""
        if isinstance(data, str):
            payload = data.encode("utf-8")
        else:
            payload = json.dumps(data, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    async def _resolve_source_data(self, source_type: str, source_id: str) -> dict[str, Any] | None:
        """Fetch canonical source record data to verify or compute fingerprint."""
        try:
            source_uuid = UUID(source_id)
        except (ValueError, TypeError):
            source_uuid = None

        if source_uuid:
            if source_type in ("EvaluationRun", "evaluation", "evaluation_run"):
                record = await self.session.get(EvaluationRun, source_uuid)
                if record:
                    return {"id": str(record.id), "status": record.status, "created_at": record.created_at}
            elif source_type in ("ReleaseDecision", "release_decision"):
                record = await self.session.get(ReleaseDecision, source_uuid)
                if record:
                    return {"id": str(record.id), "status": record.status, "outcome": record.outcome, "score": record.readiness_score}
            elif source_type in ("GovernancePolicy", "governance_policy"):
                record = await self.session.get(GovernancePolicy, source_uuid)
                if record:
                    return {"id": str(record.id), "status": record.status, "version": record.version}
            elif source_type in ("ApprovalRequest", "approval_request"):
                record = await self.session.get(ApprovalRequest, source_uuid)
                if record:
                    return {"id": str(record.id), "status": record.status, "title": record.title}
            elif source_type in ("AccessReview", "access_review"):
                record = await self.session.get(AccessReview, source_uuid)
                if record:
                    return {"id": str(record.id), "status": record.status, "title": record.title}
            elif source_type in ("AgentRun", "agent_run"):
                record = await self.session.get(AgentRun, source_uuid)
                if record:
                    return {"id": str(record.id), "status": record.status, "created_at": record.created_at}
            elif source_type in ("DatasetVersion", "dataset_version"):
                record = await self.session.get(DatasetVersion, source_uuid)
                if record:
                    return {"id": str(record.id), "version": record.version, "checksum": getattr(record, "checksum", "")}
            elif source_type in ("ExperimentRun", "experiment_run"):
                record = await self.session.get(ExperimentRun, source_uuid)
                if record:
                    return {"id": str(record.id), "status": record.status}
            elif source_type in ("BenchmarkRun", "benchmark_run"):
                record = await self.session.get(BenchmarkRun, source_uuid)
                if record:
                    return {"id": str(record.id), "status": record.status}
            elif source_type in ("Alert", "alert"):
                record = await self.session.get(Alert, source_uuid)
                if record:
                    return {"id": str(record.id), "status": record.status, "severity": record.severity}
            elif source_type in ("TaskFailure", "task_failure"):
                record = await self.session.get(TaskFailure, source_uuid)
                if record:
                    return {"id": str(record.id), "job_id": record.job_id}

        # Fallback for synthetic, diagnostic, or externally referenced sources
        return {"source_type": source_type, "source_id": source_id}

    async def record_evidence(
        self,
        organization_id: UUID,
        source_type: str,
        source_id: str,
        project_id: UUID | None = None,
        data_classification: DataClassification = DataClassification.INTERNAL,
        validity_window_days: int = 90,
        metadata_summary: dict | None = None,
        parent_classification: DataClassification | None = None,
    ) -> ComplianceEvidence:
        """Create a canonical evidence record with SHA-256 fingerprint and classification bounds."""
        now = datetime.now(UTC)
        expires_at = now + timedelta(days=validity_window_days)

        # Enforce classification inheritance if parent is provided
        if parent_classification:
            data_classification = enforce_classification_inheritance(
                parent_classification, data_classification
            )

        # Resolve source data to compute canonical fingerprint
        src_data = await self._resolve_source_data(source_type, source_id)
        if metadata_summary:
            src_payload = {"source": src_data, "metadata": metadata_summary}
        else:
            src_payload = src_data or {"source_type": source_type, "source_id": source_id}

        fingerprint = self.compute_fingerprint(src_payload)

        # Check existing evidence for idempotency
        stmt_existing = select(ComplianceEvidence).where(
            ComplianceEvidence.organization_id == organization_id,
            ComplianceEvidence.source_type == source_type,
            ComplianceEvidence.source_id == str(source_id),
        )
        existing = (await self.session.execute(stmt_existing)).scalars().first()
        if existing:
            existing.sha256_fingerprint = fingerprint
            existing.metadata_summary = metadata_summary
            existing.freshness_status = "FRESH"
            existing.integrity_status = "VALID"
            existing.collected_at = now
            existing.expires_at = expires_at
            if project_id:
                existing.project_id = project_id
            await self.session.flush()
            return existing

        evidence = ComplianceEvidence(
            organization_id=organization_id,
            project_id=project_id,
            source_type=source_type,
            source_id=source_id,
            sha256_fingerprint=fingerprint,
            data_classification=data_classification.value if isinstance(data_classification, DataClassification) else str(data_classification),
            validity_window_days=validity_window_days,
            collected_at=now,
            expires_at=expires_at,
            freshness_status="FRESH",
            integrity_status="VALID",
            metadata_summary=metadata_summary,
            created_at=now,
        )

        self.session.add(evidence)
        await self.session.flush()

        await self.audit.record(
            action="compliance.evidence_recorded",
            organization_id=organization_id,
            resource_type="compliance_evidence",
            resource_id=evidence.id,
            metadata={"source_type": source_type, "source_id": source_id, "fingerprint": fingerprint},
        )
        return evidence

    async def verify_evidence_integrity(
        self, organization_id: UUID, evidence_id: UUID
    ) -> dict[str, Any]:
        """Validate SHA-256 fingerprint, source existence, and freshness."""
        stmt = select(ComplianceEvidence).where(
            ComplianceEvidence.id == evidence_id,
            ComplianceEvidence.organization_id == organization_id,
        )
        res = await self.session.execute(stmt)
        evidence = res.scalar_one_or_none()
        if not evidence:
            raise NotFoundError(f"Evidence {evidence_id} not found.")

        def _to_utc(dt: datetime | None) -> datetime | None:
            if dt is None:
                return None
            if dt.tzinfo is None:
                return dt.replace(tzinfo=UTC)
            return dt

        now = datetime.now(UTC)
        exp = _to_utc(evidence.expires_at)
        coll = _to_utc(evidence.collected_at)

        # 1. Freshness check
        if exp and now > exp:
            freshness = "EXPIRED"
        elif coll and now > (coll + timedelta(days=evidence.validity_window_days * 0.8)):
            freshness = "STALE"
        else:
            freshness = "FRESH"
        evidence.freshness_status = freshness

        # 2. Source resolution & fingerprint re-computation
        src_data = await self._resolve_source_data(evidence.source_type, evidence.source_id)
        source_found = src_data is not None

        if not source_found:
            integrity = "MISSING_SOURCE"
            computed_fp = "SOURCE_NOT_FOUND"
        else:
            if evidence.metadata_summary:
                src_payload = {"source": src_data, "metadata": evidence.metadata_summary}
            else:
                src_payload = src_data
            computed_fp = self.compute_fingerprint(src_payload)

            if computed_fp == evidence.sha256_fingerprint:
                integrity = "VALID"
            else:
                integrity = "TAMPERED"

        evidence.integrity_status = integrity
        await self.session.flush()

        return {
            "id": evidence.id,
            "integrity_status": integrity,
            "freshness_status": freshness,
            "verified_at": now,
            "computed_fingerprint": computed_fp,
            "expected_fingerprint": evidence.sha256_fingerprint,
            "source_found": source_found,
        }

    async def list_evidence(
        self,
        organization_id: UUID,
        project_id: UUID | None = None,
        source_type: str | None = None,
    ) -> list[ComplianceEvidence]:
        stmt = select(ComplianceEvidence).where(
            ComplianceEvidence.organization_id == organization_id
        )
        if project_id:
            stmt = stmt.where(ComplianceEvidence.project_id == project_id)
        if source_type:
            stmt = stmt.where(ComplianceEvidence.source_type == source_type)
        stmt = stmt.order_by(ComplianceEvidence.created_at.desc())
        res = await self.session.execute(stmt)
        return list(res.scalars().all())


async def publish_canonical_evidence(
    session: AsyncSession,
    organization_id: UUID,
    source_type: str,
    source_id: str,
    project_id: UUID | None = None,
    metadata_summary: dict | None = None,
    classification: DataClassification = DataClassification.INTERNAL,
) -> ComplianceEvidence | None:
    """Convenience helper to safely and idempotently publish canonical compliance evidence."""
    try:
        service = EvidenceService(session)
        return await service.record_evidence(
            organization_id=organization_id,
            source_type=source_type,
            source_id=str(source_id),
            project_id=project_id,
            data_classification=classification,
            metadata_summary=metadata_summary,
        )
    except Exception as exc:
        logger.warning(
            "Failed to publish canonical compliance evidence: %s",
            exc,
            extra={"source_type": source_type, "source_id": str(source_id)},
        )
        return None

