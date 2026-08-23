"""Phase 4+ stub routers (spec §7 module structure; §131 item 2).

Dataset management (Phase 2) and the evaluation engine (Phase 3) are
implemented; experiments belong to a later phase and return 501 NOT_IMPLEMENTED.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.errors import NotImplementedFeature
from app.db.session import get_db
from app.models import User


def not_implemented(feature: str) -> None:
    raise NotImplementedFeature(f"{feature} is not implemented yet.")


experiments_router = APIRouter(prefix="/experiments", tags=["experiments"])


@experiments_router.get("", status_code=501)
@experiments_router.post("", status_code=501)
async def _experiments(
    _user: User = Depends(get_current_user), _session: AsyncSession = Depends(get_db)
) -> None:
    not_implemented("Experiments")
