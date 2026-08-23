"""Authentication endpoints (spec §33; AT-004..AT-008)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.ratelimit import check_rate_limit
from app.db.session import get_db
from app.models import User
from app.schemas.auth import (
    LoginRequest,
    MeResponse,
    RegisterRequest,
)
from app.schemas.common import ok
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> dict:
    settings = get_settings()
    client_ip = request.client.host if request.client else "unknown"
    check_rate_limit(
        f"register:{client_ip}", settings.rate_limit_register, settings.rate_limit_register_window
    )
    service = AuthService(session)
    tokens = await service.register(
        name=payload.name, email=payload.email, password=payload.password
    )
    return ok(tokens)


@router.post("/login", status_code=status.HTTP_200_OK)
async def login(
    payload: LoginRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> dict:
    settings = get_settings()
    client_ip = request.client.host if request.client else "unknown"
    check_rate_limit(
        f"login:{payload.email}:{client_ip}",
        settings.rate_limit_login,
        settings.rate_limit_login_window,
    )
    service = AuthService(session)
    tokens = await service.login(email=payload.email, password=payload.password)
    return ok(tokens)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> None:
    service = AuthService(session)
    await service.logout(user.id)
    response.status_code = status.HTTP_204_NO_CONTENT


@router.get("/me", status_code=status.HTTP_200_OK)
async def me(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)
) -> dict:
    service = AuthService(session)
    result: MeResponse = await service.me(user.id)
    return ok(result)
