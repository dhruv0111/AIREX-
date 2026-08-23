"""Dataset, dataset-version and test-case repositories (tenant-scoped).

Version immutability is enforced at the service layer; these repositories only
read and create rows for versions/test-cases — they never mutate an existing
version's immutable fields.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Dataset, DatasetVersion, TestCase


class DatasetRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        project_id: UUID,
        name: str,
        description: str | None,
        created_by: UUID | None,
        metadata: dict | None = None,
    ) -> Dataset:
        dataset = Dataset(
            project_id=project_id,
            name=name,
            description=description,
            created_by=created_by,
            status="ACTIVE",
            metadata_=metadata,
        )
        self._session.add(dataset)
        await self._session.flush()
        return dataset

    async def get_by_id(self, dataset_id: UUID) -> Dataset | None:
        return await self._session.get(Dataset, dataset_id)

    async def list_for_project(
        self, project_id: UUID, *, page: int, page_size: int
    ) -> tuple[list[Dataset], int]:
        base = select(Dataset).where(Dataset.project_id == project_id)
        total = (
            await self._session.execute(
                select(func.count()).select_from(Dataset).where(Dataset.project_id == project_id)
            )
        ).scalar_one()
        result = await self._session.execute(
            base.order_by(Dataset.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        )
        return list(result.scalars().all()), total


class DatasetVersionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        dataset_id: UUID,
        version_number: int,
        storage_reference: str,
        record_count: int,
        checksum: str,
        fmt: str,
        status: str,
        created_by: UUID | None,
    ) -> DatasetVersion:
        version = DatasetVersion(
            dataset_id=dataset_id,
            version_number=version_number,
            storage_reference=storage_reference,
            record_count=record_count,
            checksum=checksum,
            format=fmt,
            status=status,
            created_by=created_by,
            created_at=datetime.now(UTC),
        )
        self._session.add(version)
        await self._session.flush()
        return version

    async def get_by_id(self, version_id: UUID) -> DatasetVersion | None:
        return await self._session.get(DatasetVersion, version_id)

    async def latest(self, dataset_id: UUID) -> DatasetVersion | None:
        result = await self._session.execute(
            select(DatasetVersion)
            .where(DatasetVersion.dataset_id == dataset_id)
            .order_by(DatasetVersion.version_number.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def max_version_number(self, dataset_id: UUID) -> int:
        result = await self._session.execute(
            select(func.max(DatasetVersion.version_number)).where(
                DatasetVersion.dataset_id == dataset_id
            )
        )
        return result.scalar_one() or 0

    async def count_for_dataset(self, dataset_id: UUID) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(DatasetVersion)
            .where(DatasetVersion.dataset_id == dataset_id)
        )
        return result.scalar_one()

    async def list_for_dataset(
        self, dataset_id: UUID, *, page: int, page_size: int
    ) -> tuple[list[DatasetVersion], int]:
        total = (
            await self._session.execute(
                select(func.count())
                .select_from(DatasetVersion)
                .where(DatasetVersion.dataset_id == dataset_id)
            )
        ).scalar_one()
        result = await self._session.execute(
            select(DatasetVersion)
            .where(DatasetVersion.dataset_id == dataset_id)
            .order_by(DatasetVersion.version_number.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), total


class TestCaseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def bulk_create(self, version_id: UUID, records: list[dict]) -> list[TestCase]:
        now = datetime.now(UTC)
        cases: list[TestCase] = []
        for index, record in enumerate(records, start=1):
            case = TestCase(
                dataset_version_id=version_id,
                row_number=index,
                input=str(record.get("input") or ""),
                expected_output=(
                    str(record.get("expected_output"))
                    if record.get("expected_output") is not None
                    else None
                ),
                context=record.get("context"),
                category=record.get("category"),
                difficulty=record.get("difficulty"),
                metadata_=record.get("metadata"),
                status="PENDING",
                created_at=now,
                updated_at=now,
            )
            self._session.add(case)
            cases.append(case)
        await self._session.flush()
        return cases

    async def get_by_id(self, test_case_id: UUID) -> TestCase | None:
        return await self._session.get(TestCase, test_case_id)

    async def list_for_version(
        self,
        version_id: UUID,
        *,
        page: int,
        page_size: int,
        search: str | None = None,
        category: str | None = None,
        status: str | None = None,
        difficulty: str | None = None,
    ) -> tuple[list[TestCase], int]:
        base = select(TestCase).where(TestCase.dataset_version_id == version_id)
        count = (
            select(func.count())
            .select_from(TestCase)
            .where(TestCase.dataset_version_id == version_id)
        )
        if search:
            pattern = f"%{search}%"
            base = base.where(TestCase.input.ilike(pattern))
            count = count.where(TestCase.input.ilike(pattern))
        if category:
            base = base.where(TestCase.category == category)
            count = count.where(TestCase.category == category)
        if status:
            base = base.where(TestCase.status == status.upper())
            count = count.where(TestCase.status == status.upper())
        if difficulty:
            base = base.where(TestCase.difficulty == difficulty)
            count = count.where(TestCase.difficulty == difficulty)
        total = (await self._session.execute(count)).scalar_one()
        result = await self._session.execute(
            base.order_by(TestCase.row_number.asc().nulls_last(), TestCase.created_at.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), total

    async def all_for_version(self, version_id: UUID) -> list[TestCase]:
        result = await self._session.execute(
            select(TestCase)
            .where(TestCase.dataset_version_id == version_id)
            .order_by(TestCase.row_number.asc().nulls_last(), TestCase.created_at.asc())
        )
        return list(result.scalars().all())

    async def set_status(self, test_case: TestCase, status: str) -> TestCase:
        test_case.status = status
        test_case.updated_at = datetime.now(UTC)
        return test_case
