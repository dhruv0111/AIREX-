"""Dataset lifecycle, immutable versioning and test-case management (Phase 2).

Design invariants (ADR-012):
- A dataset version is an immutable, reproducible snapshot: ``version_number``,
  ``checksum``, ``record_count``, ``storage_reference`` and test-case membership
  are set at creation and NEVER mutated.
- Test cases inside a version are content-immutable (PATCH rejected with
  DATASET_VERSION_IMMUTABLE); only status (PENDING/APPROVED/REJECTED) may change.
- Import follows: parse → validate → canonicalize → checksum → store → DB
  transaction. Any failure leaves no official partial version (§36–§37).
- Archived datasets remain readable but cannot receive new versions.
"""

from __future__ import annotations

import json
import logging
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import (
    DatasetArchivedError,
    DatasetNotFoundError,
    DatasetTooLargeError,
    DatasetVersionImmutableError,
    DatasetVersionNotFoundError,
    DuplicateDatasetVersionError,
    ForbiddenError,
    InvalidDatasetEncodingError,
    InvalidDatasetFormatError,
    InvalidDatasetSchemaError,
    InvalidTestCaseError,
    NotFoundError,
)
from app.core.permissions import CAP_MANAGE_DATASETS, require_capability
from app.datasets import (
    SUPPORTED_FORMATS,
    canonicalize,
    checksum,
    parse_dataset,
    parse_format_from_filename,
    validate_records,
)
from app.models import Dataset, DatasetVersion
from app.repositories.audit import AuditRepository
from app.repositories.dataset import (
    DatasetRepository,
    DatasetVersionRepository,
    TestCaseRepository,
)
from app.repositories.project import ProjectRepository
from app.schemas.dataset import (
    DatasetCreate,
    DatasetResponse,
    DatasetUpdate,
    DatasetVersionResponse,
    TestCaseResponse,
    ValidationIssueSchema,
    ValidationResultSchema,
)
from app.services.organization import OrganizationService
from app.storage import LocalStorageProvider, StorageProvider

logger = logging.getLogger("airex.datasets")

_MAX_IMPORT_ATTEMPTS = 3


def _records_to_csv(records: list[dict]) -> str:
    """Serialize records to CSV (context/metadata JSON-encoded in columns).

    JSONL/JSON are the canonical round-trip formats; CSV is provided for human
    consumption and may not reproduce nested ``context`` exactly.
    """
    import csv as _csv
    import io as _io

    buffer = _io.StringIO()
    writer = _csv.writer(buffer)
    writer.writerow(["input", "expected_output", "context", "category", "difficulty", "metadata"])
    for record in records:
        writer.writerow(
            [
                record.get("input") or "",
                record.get("expected_output") or "",
                (
                    json.dumps(record["context"], ensure_ascii=False)
                    if record.get("context") is not None
                    else ""
                ),
                record.get("category") or "",
                record.get("difficulty") or "",
                (
                    json.dumps(record["metadata"], ensure_ascii=False)
                    if record.get("metadata") is not None
                    else ""
                ),
            ]
        )
    return buffer.getvalue()


class DatasetService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._datasets = DatasetRepository(session)
        self._versions = DatasetVersionRepository(session)
        self._cases = TestCaseRepository(session)
        self._projects = ProjectRepository(session)
        self._audit = AuditRepository(session)
        self._orgs = OrganizationService(session)
        self._settings = get_settings()
        self._storage: StorageProvider = LocalStorageProvider(self._settings.dataset_storage_dir)

    # ------------------------------------------------------------------ authz
    async def _require_member(self, org_id: UUID, user_id: UUID, capability: str):
        role = await self._orgs.resolve_membership(org_id, user_id)
        if role is None:
            raise ForbiddenError("You do not have access to this organization.")
        require_capability(role, capability)
        return role

    async def _require_project_access(self, org_id: UUID, project_id: UUID, user_id: UUID, capability: str):
        from app.core.permissions import resolve_user_project_access
        role, _ = await resolve_user_project_access(self._session, user_id, project_id, org_id)
        if role is None:
            raise ForbiddenError("You do not have access to this project.")
        require_capability(role, capability)
        return role

    async def _project_in_org(self, project_id: UUID, org_id: UUID) -> bool:
        project = await self._projects.get_by_id(project_id)
        return bool(project and project.organization_id == org_id)

    async def _dataset_in_org(self, dataset, org_id: UUID) -> bool:
        return await self._project_in_org(dataset.project_id, org_id)

    async def _get_dataset_in_org(self, dataset_id: UUID, org_id: UUID):
        dataset = await self._datasets.get_by_id(dataset_id)
        if dataset is None or not await self._dataset_in_org(dataset, org_id):
            raise DatasetNotFoundError("Dataset was not found.")
        return dataset

    async def _get_version_in_org(self, version_id: UUID, org_id: UUID):
        version = await self._versions.get_by_id(version_id)
        if version is None:
            raise DatasetVersionNotFoundError("Dataset version was not found.")
        dataset = await self._datasets.get_by_id(version.dataset_id)
        if dataset is None or not await self._dataset_in_org(dataset, org_id):
            raise DatasetVersionNotFoundError("Dataset version was not found.")
        return version

    async def _get_test_case_in_org(self, test_case_id: UUID, org_id: UUID):
        test_case = await self._cases.get_by_id(test_case_id)
        if test_case is None:
            raise NotFoundError("Test case was not found.")
        version = await self._versions.get_by_id(test_case.dataset_version_id)
        if version is None:
            raise NotFoundError("Test case was not found.")
        dataset = await self._datasets.get_by_id(version.dataset_id)
        if dataset is None or not await self._dataset_in_org(dataset, org_id):
            raise NotFoundError("Test case was not found.")
        return test_case

    # -------------------------------------------------------------- datasets
    async def create(
        self,
        *,
        organization_id: UUID,
        project_id: UUID,
        user_id: UUID,
        payload: DatasetCreate,
    ) -> DatasetResponse:
        await self._require_project_access(organization_id, project_id, user_id, CAP_MANAGE_DATASETS)
        if not await self._project_in_org(project_id, organization_id):
            raise NotFoundError("Project was not found.")
        dataset = await self._datasets.create(
            project_id=project_id,
            name=payload.name,
            description=payload.description,
            created_by=user_id,
            metadata=payload.metadata,
        )
        await self._audit.record(
            action="DATASET_CREATED",
            organization_id=organization_id,
            user_id=user_id,
            resource_type="dataset",
            resource_id=dataset.id,
        )
        await self._session.commit()
        return await self._to_dataset_response(dataset, organization_id)

    async def list_datasets(
        self,
        *,
        organization_id: UUID,
        project_id: UUID,
        user_id: UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[DatasetResponse], int]:
        await self._require_project_access(organization_id, project_id, user_id, "view_all")
        if not await self._project_in_org(project_id, organization_id):
            raise NotFoundError("Project was not found.")
        datasets, total = await self._datasets.list_for_project(
            project_id, page=page, page_size=page_size
        )
        responses = [await self._to_dataset_response(d, organization_id) for d in datasets]
        return responses, total

    async def get(
        self, *, organization_id: UUID, dataset_id: UUID, user_id: UUID
    ) -> DatasetResponse:
        dataset = await self._get_dataset_in_org(dataset_id, organization_id)
        await self._require_project_access(organization_id, dataset.project_id, user_id, "view_all")
        return await self._to_dataset_response(dataset, organization_id)

    async def update(
        self,
        *,
        organization_id: UUID,
        dataset_id: UUID,
        user_id: UUID,
        payload: DatasetUpdate,
    ) -> DatasetResponse:
        dataset = await self._get_dataset_in_org(dataset_id, organization_id)
        await self._require_project_access(organization_id, dataset.project_id, user_id, CAP_MANAGE_DATASETS)
        if payload.name is not None:
            dataset.name = payload.name
        if payload.description is not None:
            dataset.description = payload.description
        if payload.metadata is not None:
            dataset.metadata_ = payload.metadata
        if payload.status is not None:
            dataset.status = payload.status
        await self._audit.record(
            action="DATASET_UPDATED",
            organization_id=organization_id,
            user_id=user_id,
            resource_type="dataset",
            resource_id=dataset_id,
        )
        await self._session.commit()
        return await self._to_dataset_response(dataset, organization_id)

    async def archive(
        self, *, organization_id: UUID, dataset_id: UUID, user_id: UUID
    ) -> DatasetResponse:
        """DELETE is implemented as a safe archive operation (Phase 2 §17).

        Historical data and versions are retained and remain readable; an
        archived dataset cannot receive new versions.
        """
        dataset = await self._get_dataset_in_org(dataset_id, organization_id)
        await self._require_project_access(organization_id, dataset.project_id, user_id, CAP_MANAGE_DATASETS)
        dataset.status = "ARCHIVED"
        await self._audit.record(
            action="DATASET_ARCHIVED",
            organization_id=organization_id,
            user_id=user_id,
            resource_type="dataset",
            resource_id=dataset_id,
        )
        await self._session.commit()
        return await self._to_dataset_response(dataset, organization_id)

    # -------------------------------------------------------------- versions
    async def create_version(
        self,
        *,
        organization_id: UUID,
        dataset_id: UUID,
        user_id: UUID,
        file_bytes: bytes,
        filename: str | None,
        fmt: str | None,
    ) -> DatasetVersionResponse:
        await self._require_member(organization_id, user_id, CAP_MANAGE_DATASETS)
        dataset = await self._get_dataset_in_org(dataset_id, organization_id)
        if dataset.status == "ARCHIVED":
            raise DatasetArchivedError("Archived datasets cannot receive new versions.")

        max_bytes = self._settings.dataset_max_file_size_mb * 1024 * 1024
        if len(file_bytes) > max_bytes:
            raise DatasetTooLargeError(
                "Uploaded file exceeds the maximum size of "
                f"{self._settings.dataset_max_file_size_mb} MB."
            )
        try:
            text = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            raise InvalidDatasetEncodingError("Dataset file is not valid UTF-8.")

        # Never trust the uploaded filename (spec §42–§43): reject traversal
        # segments or absolute paths. Storage keys are generated IDs regardless.
        if filename:
            normalized_name = filename.replace("\\", "/")
            if ".." in normalized_name.split("/") or normalized_name.startswith("/"):
                raise InvalidDatasetSchemaError("Unsafe filename.")

        resolved_fmt = (fmt or "").lower().lstrip(".")
        if not resolved_fmt:
            resolved_fmt = parse_format_from_filename(filename) or ""
        if resolved_fmt not in SUPPORTED_FORMATS:
            raise InvalidDatasetFormatError(f"Unsupported dataset format: {fmt or filename!r}.")

        records = parse_dataset(text, resolved_fmt)
        result = validate_records(records, max_records=self._settings.dataset_max_records)
        if not result.valid:
            raise InvalidDatasetSchemaError(
                "Dataset failed validation.",
                details={"validation": self._validation_payload(result)},
            )

        version = await self._finalize_version(
            organization_id=organization_id,
            dataset=dataset,
            records=records,
            fmt=resolved_fmt,
            user_id=user_id,
        )
        return self._to_version_response(version)

    async def create_version_from_records(
        self,
        *,
        organization_id: UUID,
        dataset_id: UUID,
        user_id: UUID,
        records: list[dict],
    ) -> DatasetVersionResponse:
        """Create an immutable dataset version directly from validated records.

        Phase 5: APPROVED generated candidates enter a dataset version through the
        exact same canonicalize → checksum → store → DB pipeline as a file upload,
        preserving the reproducibility invariants of ADR-012/ADR-014.
        """
        await self._require_member(organization_id, user_id, CAP_MANAGE_DATASETS)
        dataset = await self._get_dataset_in_org(dataset_id, organization_id)
        if dataset.status == "ARCHIVED":
            raise DatasetArchivedError("Archived datasets cannot receive new versions.")
        result = validate_records(records, max_records=self._settings.dataset_max_records)
        if not result.valid:
            raise InvalidDatasetSchemaError(
                "Dataset failed validation.",
                details={"validation": self._validation_payload(result)},
            )
        version = await self._finalize_version(
            organization_id=organization_id,
            dataset=dataset,
            records=records,
            fmt="jsonl",
            user_id=user_id,
        )
        return self._to_version_response(version)

    async def _finalize_version(
        self,
        *,
        organization_id: UUID,
        dataset: Dataset,
        records: list[dict],
        fmt: str,
        user_id: UUID,
    ) -> DatasetVersion:
        """Canonicalize → checksum → store → version row → test cases → audit.

        Shared by file uploads (:meth:`create_version`) and generated-candidate
        imports (:meth:`create_version_from_records`). Retried on concurrent
        version-creation conflicts (Phase 2 §36–§37).
        """
        # Capture the plain UUID once: after a rollback the ORM ``dataset``
        # object is expired, so referencing ``dataset.id`` again would trigger a
        # lazy refresh that is illegal in the async concurrency path.
        dataset_id = dataset.id
        canonical_bytes = canonicalize(records)
        digest = checksum(records)

        for attempt in range(_MAX_IMPORT_ATTEMPTS):
            version_number = await self._versions.max_version_number(dataset_id) + 1
            storage_key = f"datasets/{dataset_id}/versions/{version_number}/dataset.jsonl"
            self._storage.put(storage_key, canonical_bytes)
            try:
                version = await self._versions.create(
                    dataset_id=dataset_id,
                    version_number=version_number,
                    storage_reference=storage_key,
                    record_count=len(records),
                    checksum=digest,
                    fmt=fmt,
                    status="COMPLETED",
                    created_by=user_id,
                )
                await self._cases.bulk_create(version.id, records)
                await self._audit.record(
                    action="DATASET_VERSION_CREATED",
                    organization_id=organization_id,
                    user_id=user_id,
                    resource_type="dataset_version",
                    resource_id=version.id,
                    metadata={"version_number": version_number, "record_count": len(records)},
                )
                await self._session.commit()
                return version
            except IntegrityError:
                self._storage.delete(storage_key)
                await self._session.rollback()
                if attempt == _MAX_IMPORT_ATTEMPTS - 1:
                    raise DuplicateDatasetVersionError(
                        "Concurrent version creation conflict; please retry."
                    )
                continue
        raise DuplicateDatasetVersionError("Concurrent version creation conflict.")

    async def list_versions(
        self,
        *,
        organization_id: UUID,
        dataset_id: UUID,
        user_id: UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[DatasetVersionResponse], int]:
        await self._require_member(organization_id, user_id, "view_all")
        await self._get_dataset_in_org(dataset_id, organization_id)
        versions, total = await self._versions.list_for_dataset(
            dataset_id, page=page, page_size=page_size
        )
        return [self._to_version_response(v) for v in versions], total

    async def get_version(
        self, *, organization_id: UUID, version_id: UUID, user_id: UUID
    ) -> DatasetVersionResponse:
        await self._require_member(organization_id, user_id, "view_all")
        version = await self._get_version_in_org(version_id, organization_id)
        return self._to_version_response(version)

    async def export_version(
        self, *, organization_id: UUID, version_id: UUID, user_id: UUID, fmt: str = "jsonl"
    ) -> tuple[bytes, str]:
        await self._require_member(organization_id, user_id, "view_all")
        version = await self._get_version_in_org(version_id, organization_id)
        canonical_bytes = self._storage.get(version.storage_reference)
        normalized = (fmt or "jsonl").lower().lstrip(".")
        if normalized == "jsonl":
            content, media_type = canonical_bytes, "application/x-ndjson"
        elif normalized == "json":
            records = parse_dataset(canonical_bytes.decode("utf-8"), "jsonl")
            content = json.dumps(records, ensure_ascii=False, indent=2).encode("utf-8")
            media_type = "application/json"
        elif normalized == "csv":
            records = parse_dataset(canonical_bytes.decode("utf-8"), "jsonl")
            content = _records_to_csv(records).encode("utf-8")
            media_type = "text/csv"
        else:
            raise InvalidDatasetFormatError(f"Unsupported export format: {fmt!r}.")
        await self._audit.record(
            action="DATASET_VERSION_EXPORT",
            organization_id=organization_id,
            user_id=user_id,
            resource_type="dataset_version",
            resource_id=version_id,
            metadata={"format": normalized},
        )
        return content, media_type

    # ----------------------------------------------------------- test cases
    async def list_test_cases(
        self,
        *,
        organization_id: UUID,
        version_id: UUID,
        user_id: UUID,
        page: int = 1,
        page_size: int = 20,
        search: str | None = None,
        category: str | None = None,
        status: str | None = None,
        difficulty: str | None = None,
    ) -> tuple[list[TestCaseResponse], int]:
        await self._require_member(organization_id, user_id, "view_all")
        await self._get_version_in_org(version_id, organization_id)
        cases, total = await self._cases.list_for_version(
            version_id,
            page=page,
            page_size=page_size,
            search=search,
            category=category,
            status=status,
            difficulty=difficulty,
        )
        return [self._to_test_case_response(c) for c in cases], total

    async def get_test_case(
        self, *, organization_id: UUID, test_case_id: UUID, user_id: UUID
    ) -> TestCaseResponse:
        await self._require_member(organization_id, user_id, "view_all")
        test_case = await self._get_test_case_in_org(test_case_id, organization_id)
        return self._to_test_case_response(test_case)

    async def set_test_case_status(
        self, *, organization_id: UUID, test_case_id: UUID, user_id: UUID, status: str
    ) -> TestCaseResponse:
        await self._require_member(organization_id, user_id, CAP_MANAGE_DATASETS)
        test_case = await self._get_test_case_in_org(test_case_id, organization_id)
        if status not in ("APPROVED", "REJECTED"):
            raise InvalidTestCaseError("Invalid test-case status.")
        await self._cases.set_status(test_case, status)
        await self._audit.record(
            action="TEST_CASE_APPROVED" if status == "APPROVED" else "TEST_CASE_REJECTED",
            organization_id=organization_id,
            user_id=user_id,
            resource_type="test_case",
            resource_id=test_case_id,
        )
        await self._session.commit()
        return self._to_test_case_response(test_case)

    async def reject_immutable_change(
        self, *, organization_id: UUID, version_id: UUID, user_id: UUID
    ) -> None:
        """Version content mutation is forbidden (Phase 2 §26–§27)."""
        await self._require_member(organization_id, user_id, CAP_MANAGE_DATASETS)
        await self._get_version_in_org(version_id, organization_id)
        raise DatasetVersionImmutableError(
            "Dataset versions are immutable. Create a new version instead."
        )

    async def reject_test_case_change(
        self, *, organization_id: UUID, test_case_id: UUID, user_id: UUID
    ) -> None:
        """Test-case content mutation is forbidden for immutable versions (Phase 2 §26–§27)."""
        await self._require_member(organization_id, user_id, CAP_MANAGE_DATASETS)
        await self._get_test_case_in_org(test_case_id, organization_id)
        raise DatasetVersionImmutableError(
            "Test cases are immutable inside a dataset version. Create a new version instead."
        )

    # ------------------------------------------------------------- response
    async def _to_dataset_response(self, dataset, organization_id: UUID) -> DatasetResponse:
        version_count = await self._versions.count_for_dataset(dataset.id)
        latest = await self._versions.latest(dataset.id)
        return DatasetResponse(
            id=dataset.id,
            project_id=dataset.project_id,
            name=dataset.name,
            description=dataset.description,
            status=dataset.status,
            metadata=dataset.metadata_,
            version_count=version_count,
            latest_version=latest.version_number if latest else None,
            record_count=latest.record_count if latest else 0,
            created_at=dataset.created_at,
            updated_at=dataset.updated_at,
        )

    def _to_version_response(self, version) -> DatasetVersionResponse:
        return DatasetVersionResponse(
            id=version.id,
            dataset_id=version.dataset_id,
            version_number=version.version_number,
            record_count=version.record_count,
            checksum=version.checksum,
            format=version.format,
            status=version.status,
            created_by=version.created_by,
            created_at=version.created_at,
        )

    def _to_test_case_response(self, case) -> TestCaseResponse:
        return TestCaseResponse(
            id=case.id,
            dataset_version_id=case.dataset_version_id,
            row_number=case.row_number,
            input=case.input,
            expected_output=case.expected_output,
            context=case.context,
            category=case.category,
            difficulty=case.difficulty,
            metadata=case.metadata_,
            status=case.status,
            created_at=case.created_at,
        )

    def _validation_payload(self, result) -> dict:
        return ValidationResultSchema(
            valid=result.valid,
            record_count=result.record_count,
            errors=[
                ValidationIssueSchema(row=i.row, field=i.field, code=i.code, message=i.message)
                for i in result.errors
            ],
            warnings=[
                ValidationIssueSchema(row=i.row, field=i.field, code=i.code, message=i.message)
                for i in result.warnings
            ],
        ).model_dump()
