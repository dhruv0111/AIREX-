"""Dataset management endpoints (Phase 2 §13–§18, §27, §39, §51)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile
from fastapi import status as http_status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_active_organization, get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.common import ok, ok_list
from app.schemas.dataset import DatasetCreate, DatasetUpdate
from app.services.dataset import DatasetService

router = APIRouter(tags=["datasets"])


@router.post("/projects/{project_id}/datasets", status_code=http_status.HTTP_201_CREATED)
async def create_dataset(
    project_id: UUID,
    payload: DatasetCreate,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    service = DatasetService(session)
    dataset = await service.create(
        organization_id=organization_id,
        project_id=project_id,
        user_id=user.id,
        payload=payload,
    )
    return ok(dataset)


@router.get("/projects/{project_id}/datasets", status_code=http_status.HTTP_200_OK)
async def list_datasets(
    project_id: UUID,
    page: int = 1,
    page_size: int = 20,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    service = DatasetService(session)
    datasets, total = await service.list_datasets(
        organization_id=organization_id,
        project_id=project_id,
        user_id=user.id,
        page=page,
        page_size=page_size,
    )
    return ok_list(datasets, page=page, page_size=page_size, total=total)


@router.get("/datasets/{dataset_id}", status_code=http_status.HTTP_200_OK)
async def get_dataset(
    dataset_id: UUID,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    service = DatasetService(session)
    dataset = await service.get(
        organization_id=organization_id, dataset_id=dataset_id, user_id=user.id
    )
    return ok(dataset)


@router.patch("/datasets/{dataset_id}", status_code=http_status.HTTP_200_OK)
async def update_dataset(
    dataset_id: UUID,
    payload: DatasetUpdate,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    service = DatasetService(session)
    dataset = await service.update(
        organization_id=organization_id,
        dataset_id=dataset_id,
        user_id=user.id,
        payload=payload,
    )
    return ok(dataset)


@router.delete("/datasets/{dataset_id}", status_code=http_status.HTTP_204_NO_CONTENT)
async def archive_dataset(
    dataset_id: UUID,
    response: Response,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> None:
    # DELETE is implemented as a safe archive (Phase 2 §17); versions are retained.
    service = DatasetService(session)
    await service.archive(organization_id=organization_id, dataset_id=dataset_id, user_id=user.id)
    response.status_code = http_status.HTTP_204_NO_CONTENT


@router.post("/datasets/{dataset_id}/versions", status_code=http_status.HTTP_201_CREATED)
async def create_dataset_version(
    dataset_id: UUID,
    file: UploadFile = File(...),
    format: str | None = Form(default=None),
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    file_bytes = await file.read()
    service = DatasetService(session)
    version = await service.create_version(
        organization_id=organization_id,
        dataset_id=dataset_id,
        user_id=user.id,
        file_bytes=file_bytes,
        filename=file.filename,
        fmt=format,
    )
    return ok(version)


@router.get("/datasets/{dataset_id}/versions", status_code=http_status.HTTP_200_OK)
async def list_dataset_versions(
    dataset_id: UUID,
    page: int = 1,
    page_size: int = 20,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    service = DatasetService(session)
    versions, total = await service.list_versions(
        organization_id=organization_id,
        dataset_id=dataset_id,
        user_id=user.id,
        page=page,
        page_size=page_size,
    )
    return ok_list(versions, page=page, page_size=page_size, total=total)


@router.get("/dataset-versions/{version_id}", status_code=http_status.HTTP_200_OK)
async def get_dataset_version(
    version_id: UUID,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    service = DatasetService(session)
    version = await service.get_version(
        organization_id=organization_id, version_id=version_id, user_id=user.id
    )
    return ok(version)


@router.patch("/dataset-versions/{version_id}", status_code=http_status.HTTP_409_CONFLICT)
async def patch_dataset_version(
    version_id: UUID,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> None:
    # Versions are immutable; any content mutation is rejected (Phase 2 §21, AT-P2-021).
    service = DatasetService(session)
    await service.reject_immutable_change(
        organization_id=organization_id, version_id=version_id, user_id=user.id
    )


@router.get("/dataset-versions/{version_id}/export", status_code=http_status.HTTP_200_OK)
async def export_dataset_version(
    version_id: UUID,
    format: str = "jsonl",
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> Response:
    service = DatasetService(session)
    content, media_type = await service.export_version(
        organization_id=organization_id, version_id=version_id, user_id=user.id, fmt=format
    )
    safe_format = format.lower().lstrip(".") if format else "jsonl"
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="dataset-{version_id}.{safe_format}"'
        },
    )


@router.get("/dataset-versions/{version_id}/test-cases", status_code=http_status.HTTP_200_OK)
async def list_test_cases(
    version_id: UUID,
    page: int = 1,
    page_size: int = 20,
    search: str | None = None,
    category: str | None = None,
    status: str | None = None,
    difficulty: str | None = None,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    service = DatasetService(session)
    cases, total = await service.list_test_cases(
        organization_id=organization_id,
        version_id=version_id,
        user_id=user.id,
        page=page,
        page_size=page_size,
        search=search,
        category=category,
        status=status,
        difficulty=difficulty,
    )
    return ok_list(cases, page=page, page_size=page_size, total=total)


@router.get("/test-cases/{test_case_id}", status_code=http_status.HTTP_200_OK)
async def get_test_case(
    test_case_id: UUID,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    service = DatasetService(session)
    test_case = await service.get_test_case(
        organization_id=organization_id, test_case_id=test_case_id, user_id=user.id
    )
    return ok(test_case)


@router.patch("/test-cases/{test_case_id}", status_code=http_status.HTTP_409_CONFLICT)
async def patch_test_case(
    test_case_id: UUID,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> None:
    # Test cases are content-immutable inside a version (Phase 2 §26–§27).
    service = DatasetService(session)
    await service.reject_test_case_change(
        organization_id=organization_id, test_case_id=test_case_id, user_id=user.id
    )


@router.post("/test-cases/{test_case_id}/approve", status_code=http_status.HTTP_200_OK)
async def approve_test_case(
    test_case_id: UUID,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    service = DatasetService(session)
    test_case = await service.set_test_case_status(
        organization_id=organization_id,
        test_case_id=test_case_id,
        user_id=user.id,
        status="APPROVED",
    )
    return ok(test_case)


@router.post("/test-cases/{test_case_id}/reject", status_code=http_status.HTTP_200_OK)
async def reject_test_case(
    test_case_id: UUID,
    user: User = Depends(get_current_user),
    organization_id: UUID = Depends(get_active_organization),
    session: AsyncSession = Depends(get_db),
) -> dict:
    service = DatasetService(session)
    test_case = await service.set_test_case_status(
        organization_id=organization_id,
        test_case_id=test_case_id,
        user_id=user.id,
        status="REJECTED",
    )
    return ok(test_case)
