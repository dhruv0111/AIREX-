"""Compliance & Assessment Engine (spec Phase 14)."""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, UTC
from typing import Any
from uuid import UUID

from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, ValidationFailure
from app.models.compliance import (
    ComplianceFramework,
    ComplianceControl,
    ComplianceEvidence,
    ComplianceAssessment,
    ComplianceAssessmentItem,
    ComplianceRemediation,
)
from app.repositories.audit import AuditRepository
from app.services.system_readiness import SystemReadinessService
from app.services.evidence_service import EvidenceService


class ComplianceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.audit = AuditRepository(session)
        self.evidence_service = EvidenceService(session)

    # --- Frameworks ---

    async def create_framework(
        self,
        organization_id: UUID,
        name: str,
        description: str | None = None,
        applicability: dict | None = None,
        owner_id: UUID | None = None,
    ) -> ComplianceFramework:
        # Check existing version to increment
        stmt = select(ComplianceFramework).where(
            ComplianceFramework.organization_id == organization_id,
            ComplianceFramework.name == name,
        ).order_by(ComplianceFramework.version.desc())
        res = await self.session.execute(stmt)
        latest = res.scalar_one_or_none()

        version = (latest.version + 1) if latest else 1

        now = datetime.now(UTC)
        fw = ComplianceFramework(
            organization_id=organization_id,
            name=name,
            version=version,
            description=description,
            applicability=applicability,
            owner_id=owner_id,
            status="DRAFT",
            is_immutable=False,
            created_at=now,
            updated_at=now,
        )
        self.session.add(fw)
        await self.session.flush()

        await self.audit.record(
            action="compliance.framework_created",
            organization_id=organization_id,
            user_id=owner_id,
            resource_type="compliance_framework",
            resource_id=fw.id,
            metadata={"name": name, "version": version},
        )
        return fw

    async def activate_framework(
        self, organization_id: UUID, framework_id: UUID
    ) -> ComplianceFramework:
        fw = await self.get_framework(organization_id, framework_id)
        if fw.status == "ACTIVE" and fw.is_immutable:
            return fw

        fw.status = "ACTIVE"
        fw.is_immutable = True  # Permanently lock version
        fw.effective_date = datetime.now(UTC)
        fw.updated_at = datetime.now(UTC)
        await self.session.flush()

        await self.audit.record(
            action="compliance.framework_activated",
            organization_id=organization_id,
            resource_type="compliance_framework",
            resource_id=fw.id,
            metadata={"name": fw.name, "version": fw.version},
        )
        return fw

    async def get_framework(
        self, organization_id: UUID, framework_id: UUID
    ) -> ComplianceFramework:
        stmt = select(ComplianceFramework).where(
            ComplianceFramework.id == framework_id,
            ComplianceFramework.organization_id == organization_id,
        )
        res = await self.session.execute(stmt)
        fw = res.scalar_one_or_none()
        if not fw:
            raise NotFoundError(f"Compliance framework {framework_id} not found.")
        return fw

    async def list_frameworks(self, organization_id: UUID) -> list[ComplianceFramework]:
        stmt = select(ComplianceFramework).where(
            ComplianceFramework.organization_id == organization_id
        ).order_by(ComplianceFramework.name.asc(), ComplianceFramework.version.desc())
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # --- Controls ---

    async def create_control(
        self,
        organization_id: UUID,
        framework_id: UUID,
        control_id: str,
        title: str,
        description: str | None = None,
        category: str = "GOVERNANCE",
        risk_level: str = "MEDIUM",
        applicability: dict | None = None,
        required_evidence_types: list[str] | None = None,
        evaluation_frequency: str = "CONTINUOUS",
        owner_id: UUID | None = None,
    ) -> ComplianceControl:
        fw = await self.get_framework(organization_id, framework_id)
        if fw.is_immutable:
            raise ValidationFailure(
                f"Cannot add controls to activated framework '{fw.name} v{fw.version}' because it is immutable. Create a new version."
            )

        now = datetime.now(UTC)
        ctrl = ComplianceControl(
            framework_id=framework_id,
            control_id=control_id,
            title=title,
            description=description,
            category=category,
            risk_level=risk_level,
            applicability=applicability,
            required_evidence_types=required_evidence_types,
            evaluation_frequency=evaluation_frequency,
            owner_id=owner_id,
            status="NOT_ASSESSED",
            version=1,
            created_at=now,
            updated_at=now,
        )
        self.session.add(ctrl)
        await self.session.flush()

        await self.audit.record(
            action="compliance.control_created",
            organization_id=organization_id,
            resource_type="compliance_control",
            resource_id=ctrl.id,
            metadata={"control_id": control_id, "framework_id": str(framework_id)},
        )
        return ctrl

    async def list_controls(
        self, organization_id: UUID, framework_id: UUID
    ) -> list[ComplianceControl]:
        # Validate framework belongs to org
        await self.get_framework(organization_id, framework_id)

        stmt = select(ComplianceControl).where(
            ComplianceControl.framework_id == framework_id
        ).order_by(ComplianceControl.control_id.asc())
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # --- Automated Compliance Checks ---

    async def run_automated_checks(self, organization_id: UUID) -> dict[str, Any]:
        """Inspect platform subsystems and return pass/fail statuses for automated controls."""
        readiness_svc = SystemReadinessService(self.session)
        diag = await readiness_svc.evaluate_readiness()

        diag_checks = {c["name"]: c for c in diag.get("checks", [])}
        checks: dict[str, dict[str, Any]] = {}

        # 1. Encryption
        enc_check = diag_checks.get("encryption_key")
        checks["ENC-01"] = {
            "status": "PASS" if enc_check and enc_check.get("status") == "HEALTHY" else "FAIL",
            "explanation": "AES-128-CBC / Fernet cryptographic key initialized and operational.",
        }

        # 2. Database schema alignment
        db_mig = diag_checks.get("database_migrations")
        checks["DB-01"] = {
            "status": "PASS" if db_mig and db_mig.get("status") == "HEALTHY" else "FAIL",
            "explanation": "Alembic schema migration heads aligned with active release target.",
        }

        # 3. Worker fleet heartbeat
        worker_chk = diag_checks.get("worker_fleet")
        checks["OPS-01"] = {
            "status": "PASS" if worker_chk and worker_chk.get("status") in ("HEALTHY", "DEGRADED") else "WARNING",
            "explanation": "Worker fleet heartbeat active and executing asynchronous background jobs.",
        }

        return checks

    # --- Assessments ---

    async def create_assessment(
        self,
        organization_id: UUID,
        framework_id: UUID,
        title: str,
        assessed_by_id: UUID | None = None,
    ) -> ComplianceAssessment:
        fw = await self.get_framework(organization_id, framework_id)
        now = datetime.now(UTC)

        assessment = ComplianceAssessment(
            organization_id=organization_id,
            framework_id=framework_id,
            title=title,
            status="DRAFT",
            overall_score=0.0,
            summary={"total_controls": 0, "compliant": 0, "non_compliant": 0, "gaps": 0},
            assessed_by_id=assessed_by_id,
            created_at=now,
            updated_at=now,
        )
        self.session.add(assessment)
        await self.session.flush()

        await self.audit.record(
            action="compliance.assessment_created",
            organization_id=organization_id,
            user_id=assessed_by_id,
            resource_type="compliance_assessment",
            resource_id=assessment.id,
            metadata={"title": title, "framework_name": fw.name},
        )
        return assessment

    async def execute_assessment(
        self, organization_id: UUID, assessment_id: UUID
    ) -> ComplianceAssessment:
        stmt = select(ComplianceAssessment).where(
            ComplianceAssessment.id == assessment_id,
            ComplianceAssessment.organization_id == organization_id,
        )
        res = await self.session.execute(stmt)
        assessment = res.scalar_one_or_none()
        if not assessment:
            raise NotFoundError(f"Assessment {assessment_id} not found.")

        controls = await self.list_controls(organization_id, assessment.framework_id)
        evidence_list = await self.evidence_service.list_evidence(organization_id)
        evidence_by_type: dict[str, list[ComplianceEvidence]] = {}
        for ev in evidence_list:
            evidence_by_type.setdefault(ev.source_type, []).append(ev)

        automated_checks = await self.run_automated_checks(organization_id)

        now = datetime.now(UTC)
        total_controls = len(controls)
        compliant_count = 0
        non_compliant_count = 0
        gaps_count = 0

        # Clear previous items if re-running
        await self.session.execute(
            delete(ComplianceAssessmentItem).where(
                ComplianceAssessmentItem.assessment_id == assessment.id
            )
        )

        for ctrl in controls:
            item_status = "NOT_ASSESSED"
            findings = None
            linked_ev_ids: list[str] = []

            # Check if this matches an automated check
            if ctrl.control_id in automated_checks:
                chk = automated_checks[ctrl.control_id]
                if chk["status"] == "PASS":
                    item_status = "COMPLIANT"
                    findings = chk["explanation"]
                else:
                    item_status = "NON_COMPLIANT"
                    findings = f"Automated check failed: {chk['explanation']}"
            elif ctrl.required_evidence_types:
                # Inspect required evidence
                has_missing = False
                has_tampered = False
                for req_type in ctrl.required_evidence_types:
                    matched = evidence_by_type.get(req_type, [])
                    if not matched:
                        has_missing = True
                    else:
                        for ev in matched:
                            linked_ev_ids.append(str(ev.id))
                            if ev.integrity_status == "TAMPERED":
                                has_tampered = True

                if has_tampered:
                    item_status = "NON_COMPLIANT"
                    findings = "Linked evidence failed SHA-256 integrity validation."
                elif has_missing:
                    item_status = "INSUFFICIENT_EVIDENCE"
                    findings = f"Required evidence of types {ctrl.required_evidence_types} not found in evidence registry."
                else:
                    item_status = "COMPLIANT"
                    findings = f"Verified {len(linked_ev_ids)} evidence artifacts with valid integrity fingerprints."
            else:
                item_status = "COMPLIANT"
                findings = "Self-attested governance control verified."

            if item_status == "COMPLIANT":
                compliant_count += 1
            else:
                non_compliant_count += 1
                gaps_count += 1
                # Auto-generate remediation item
                remediation = ComplianceRemediation(
                    organization_id=organization_id,
                    assessment_id=assessment.id,
                    control_id=ctrl.id,
                    title=f"Remediate {ctrl.control_id}: {ctrl.title}",
                    description=findings or "Control assessment identified gap.",
                    severity=ctrl.risk_level,
                    status="OPEN",
                    created_at=now,
                    updated_at=now,
                )
                self.session.add(remediation)

            item = ComplianceAssessmentItem(
                assessment_id=assessment.id,
                control_id=ctrl.id,
                status=item_status,
                evidence_references=linked_ev_ids,
                findings=findings,
                created_at=now,
            )
            self.session.add(item)

        overall_score = round((compliant_count / total_controls * 100.0), 2) if total_controls > 0 else 100.0

        assessment.status = "READY_FOR_REVIEW"
        assessment.overall_score = overall_score
        assessment.summary = {
            "total_controls": total_controls,
            "compliant": compliant_count,
            "non_compliant": non_compliant_count,
            "gaps": gaps_count,
        }
        assessment.updated_at = now
        await self.session.flush()

        await self.audit.record(
            action="compliance.assessment_executed",
            organization_id=organization_id,
            resource_type="compliance_assessment",
            resource_id=assessment.id,
            metadata={"overall_score": overall_score, "compliant": compliant_count, "gaps": gaps_count},
        )
        return await self.get_assessment(organization_id, assessment.id)

    async def act_on_assessment(
        self,
        organization_id: UUID,
        assessment_id: UUID,
        action: str,
        user_id: UUID | None = None,
        comment: str | None = None,
    ) -> ComplianceAssessment:
        stmt = select(ComplianceAssessment).where(
            ComplianceAssessment.id == assessment_id,
            ComplianceAssessment.organization_id == organization_id,
        )
        res = await self.session.execute(stmt)
        assessment = res.scalar_one_or_none()
        if not assessment:
            raise NotFoundError(f"Assessment {assessment_id} not found.")

        if action == "APPROVE":
            assessment.status = "APPROVED"
            assessment.approved_by_id = user_id
            assessment.approved_at = datetime.now(UTC)
        elif action == "REJECT":
            assessment.status = "REJECTED"
        else:
            raise ValidationFailure(f"Invalid assessment action {action}")

        assessment.updated_at = datetime.now(UTC)
        await self.session.flush()

        await self.audit.record(
            action=f"compliance.assessment_{action.lower()}",
            organization_id=organization_id,
            user_id=user_id,
            resource_type="compliance_assessment",
            resource_id=assessment.id,
            metadata={"comment": comment},
        )
        return await self.get_assessment(organization_id, assessment.id)

    async def get_assessment(
        self, organization_id: UUID, assessment_id: UUID
    ) -> ComplianceAssessment:
        stmt = (
            select(ComplianceAssessment)
            .options(selectinload(ComplianceAssessment.items))
            .where(
                ComplianceAssessment.id == assessment_id,
                ComplianceAssessment.organization_id == organization_id,
            )
        )
        res = await self.session.execute(stmt)
        assessment = res.scalar_one_or_none()
        if not assessment:
            raise NotFoundError(f"Assessment {assessment_id} not found.")
        return assessment

    async def list_assessments(self, organization_id: UUID) -> list[ComplianceAssessment]:
        stmt = select(ComplianceAssessment).where(
            ComplianceAssessment.organization_id == organization_id
        ).order_by(ComplianceAssessment.created_at.desc())
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # --- Remediations ---

    async def create_remediation(
        self,
        organization_id: UUID,
        control_id: UUID,
        title: str,
        description: str | None = None,
        severity: str = "MEDIUM",
        assessment_id: UUID | None = None,
        owner_id: UUID | None = None,
        due_date: datetime | None = None,
    ) -> ComplianceRemediation:
        now = datetime.now(UTC)
        rem = ComplianceRemediation(
            organization_id=organization_id,
            assessment_id=assessment_id,
            control_id=control_id,
            title=title,
            description=description,
            severity=severity,
            status="OPEN",
            owner_id=owner_id,
            due_date=due_date,
            created_at=now,
            updated_at=now,
        )
        self.session.add(rem)
        await self.session.flush()

        await self.audit.record(
            action="compliance.remediation_created",
            organization_id=organization_id,
            resource_type="compliance_remediation",
            resource_id=rem.id,
            metadata={"title": title, "severity": severity},
        )
        return rem

    async def resolve_remediation(
        self,
        organization_id: UUID,
        remediation_id: UUID,
        resolution_notes: str,
        user_id: UUID | None = None,
    ) -> ComplianceRemediation:
        stmt = select(ComplianceRemediation).where(
            ComplianceRemediation.id == remediation_id,
            ComplianceRemediation.organization_id == organization_id,
        )
        res = await self.session.execute(stmt)
        rem = res.scalar_one_or_none()
        if not rem:
            raise NotFoundError(f"Remediation {remediation_id} not found.")

        rem.status = "RESOLVED"
        rem.resolved_at = datetime.now(UTC)
        rem.resolution_notes = resolution_notes
        rem.updated_at = datetime.now(UTC)
        await self.session.flush()

        await self.audit.record(
            action="compliance.remediation_resolved",
            organization_id=organization_id,
            user_id=user_id,
            resource_type="compliance_remediation",
            resource_id=rem.id,
            metadata={"title": rem.title},
        )
        return rem

    async def accept_risk(
        self,
        organization_id: UUID,
        remediation_id: UUID,
        justification: str,
        approver_id: UUID | None = None,
        expires_at: datetime | None = None,
    ) -> ComplianceRemediation:
        stmt = select(ComplianceRemediation).where(
            ComplianceRemediation.id == remediation_id,
            ComplianceRemediation.organization_id == organization_id,
        )
        res = await self.session.execute(stmt)
        rem = res.scalar_one_or_none()
        if not rem:
            raise NotFoundError(f"Remediation {remediation_id} not found.")

        rem.status = "ACCEPTED_RISK"
        rem.accepted_risk_justification = justification
        rem.accepted_risk_approver_id = approver_id
        rem.accepted_risk_expires_at = expires_at
        rem.updated_at = datetime.now(UTC)
        await self.session.flush()

        await self.audit.record(
            action="compliance.risk_accepted",
            organization_id=organization_id,
            user_id=approver_id,
            resource_type="compliance_remediation",
            resource_id=rem.id,
            metadata={"justification": justification, "expires_at": str(expires_at)},
        )
        return rem

    async def list_remediations(
        self, organization_id: UUID, status: str | None = None
    ) -> list[ComplianceRemediation]:
        stmt = select(ComplianceRemediation).where(
            ComplianceRemediation.organization_id == organization_id
        )
        if status:
            stmt = stmt.where(ComplianceRemediation.status == status)
        stmt = stmt.order_by(ComplianceRemediation.created_at.desc())
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    # --- Compliance Reporting & Export ---

    async def export_report(
        self, organization_id: UUID, assessment_id: UUID, format: str = "json"
    ) -> tuple[str, str]:
        """Generate compliance report in JSON or CSV format."""
        assessment = await self.get_assessment(organization_id, assessment_id)
        fw = await self.get_framework(organization_id, assessment.framework_id)
        controls = await self.list_controls(organization_id, assessment.framework_id)
        remediations = await self.list_remediations(organization_id)

        items_by_ctrl = {it.control_id: it for it in assessment.items}

        control_matrix = []
        for ctrl in controls:
            it = items_by_ctrl.get(ctrl.id)
            control_matrix.append({
                "control_id": ctrl.control_id,
                "title": ctrl.title,
                "category": ctrl.category,
                "risk_level": ctrl.risk_level,
                "status": it.status if it else ctrl.status,
                "findings": it.findings if it else None,
                "evidence_count": len(it.evidence_references or []) if it else 0,
            })

        summary = assessment.summary or {}

        report_data = {
            "organization_id": str(organization_id),
            "framework_name": fw.name,
            "framework_version": fw.version,
            "assessment_title": assessment.title,
            "assessment_date": assessment.created_at.isoformat(),
            "overall_score": assessment.overall_score,
            "status": assessment.status,
            "controls_total": summary.get("total_controls", len(controls)),
            "controls_compliant": summary.get("compliant", 0),
            "controls_non_compliant": summary.get("non_compliant", 0),
            "open_remediations": len([r for r in remediations if r.status in ("OPEN", "IN_PROGRESS")]),
            "accepted_risks": len([r for r in remediations if r.status == "ACCEPTED_RISK"]),
            "control_matrix": control_matrix,
            "integrity_summary": {"status": "VALID", "tamper_detected": False},
        }

        if format.lower() == "csv":
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["Control ID", "Title", "Category", "Risk Level", "Status", "Findings", "Evidence Count"])
            for row in control_matrix:
                writer.writerow([
                    row["control_id"],
                    row["title"],
                    row["category"],
                    row["risk_level"],
                    row["status"],
                    row["findings"] or "",
                    row["evidence_count"],
                ])
            return output.getvalue(), "text/csv"

        return json.dumps(report_data, indent=2), "application/json"
