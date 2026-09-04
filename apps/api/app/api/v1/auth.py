"""Authentication endpoints (spec §33; AT-004..AT-008; Phase 12)."""

from __future__ import annotations

from uuid import UUID
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
    RefreshTokenRequest,
    RegisterRequest,
    SessionResponse,
    TokenResponse,
)
from app.schemas.common import ok, ok_list
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
    user_agent = request.headers.get("user-agent")
    check_rate_limit(
        f"register:{client_ip}", settings.rate_limit_register, settings.rate_limit_register_window
    )
    service = AuthService(session)
    tokens = await service.register(
        name=payload.name,
        email=payload.email,
        password=payload.password,
        ip_address=client_ip,
        device_info=user_agent,
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
    user_agent = request.headers.get("user-agent")
    check_rate_limit(
        f"login:{payload.email}:{client_ip}",
        settings.rate_limit_login,
        settings.rate_limit_login_window,
    )
    service = AuthService(session)
    tokens = await service.login(
        email=payload.email,
        password=payload.password,
        ip_address=client_ip,
        device_info=user_agent,
    )
    return ok(tokens)


@router.post("/refresh", status_code=status.HTTP_200_OK)
async def refresh_tokens(
    payload: RefreshTokenRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Rotate refresh token and issue new token pair (detects token reuse)."""
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent")
    service = AuthService(session)
    tokens = await service.refresh_tokens(
        payload.refresh_token,
        ip_address=client_ip,
        device_info=user_agent,
    )
    return ok(tokens)


@router.get("/sessions", status_code=status.HTTP_200_OK)
async def list_sessions(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """List all active/recent sessions for the authenticated user."""
    service = AuthService(session)
    sessions = await service.list_sessions(user.id)
    return ok([SessionResponse.model_validate(s) for s in sessions])


@router.post("/sessions/{session_id}/revoke", status_code=status.HTTP_200_OK)
async def revoke_session(
    session_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Revoke a specific user session."""
    service = AuthService(session)
    await service.revoke_session(user.id, session_id)
    return ok({"revoked": True, "session_id": str(session_id)})


@router.post("/sessions/revoke-all", status_code=status.HTTP_200_OK)
async def revoke_all_sessions(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Revoke all active sessions for the current user."""
    service = AuthService(session)
    count = await service.revoke_all_sessions(user.id)
    return ok({"revoked_count": count})


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
