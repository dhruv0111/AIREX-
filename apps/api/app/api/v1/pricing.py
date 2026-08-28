"""Model pricing configuration API (Phase 8 §11).

Pricing is used by the cost engine to estimate LLM span costs. Prices are never
hardcoded in business logic; they are stored as versioned configuration. When
no pricing matches, cost is ``null`` (never fabricated).
"""

from __future__ import annotations

from datetime import datetime, UTC
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.errors import ForbiddenError, NotFoundError, ValidationFailure
from app.core.permissions import Role
from app.db.session import get_db
from app.models.pricing import ModelPricing
from app.models.user import User
from app.schemas.pricing import PricingCreate, PricingResponse, PricingUpdate

router = APIRouter(prefix="/pricing", tags=["pricing"])


async def _require_privileged_role(user: User, db: AsyncSession) -> None:
    """Pricing is shared configuration; require a non-viewer membership."""
    from sqlalchemy import select
    from app.models.organization import OrganizationMember

    res = await db.execute(select(OrganizationMember).where(OrganizationMember.user_id == user.id))
    memberships = list(res.scalars().all())
    if not memberships:
        raise ForbiddenError("You do not belong to any organization.")
    for m in memberships:
        try:
            role = Role(m.role)
        except ValueError:
            continue
        if role != Role.VIEWER:
            return
    raise ForbiddenError("Viewer cannot modify pricing configuration.")


@router.get("", status_code=status.HTTP_200_OK)
async def list_pricing(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[PricingResponse]:
    """List all versioned pricing configurations."""
    res = await db.execute(select(ModelPricing).order_by(ModelPricing.provider, ModelPricing.model_pattern))
    return [PricingResponse.model_validate(p) for p in res.scalars().all()]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_pricing(
    payload: PricingCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PricingResponse:
    """Create a versioned pricing configuration."""
    await _require_privileged_role(user, db)

    pattern = payload.model_pattern.strip().lower()
    provider = payload.provider.strip().lower()

    existing = await db.execute(
        select(ModelPricing).where(ModelPricing.model_pattern == pattern)
    )
    if existing.scalar_one_or_none():
        raise ValidationFailure(f"Pricing for model pattern '{pattern}' already exists.")

    pricing = ModelPricing(
        id=uuid4(),
        model_pattern=pattern,
        provider=provider,
        input_price_per_1k=payload.input_price_per_1k,
        output_price_per_1k=payload.output_price_per_1k,
        currency=payload.currency,
        effective_from=payload.effective_from or datetime.now(UTC),
        effective_until=payload.effective_until,
    )
    db.add(pricing)
    await db.commit()
    await db.refresh(pricing)
    return PricingResponse.model_validate(pricing)


@router.patch("/{pricing_id}", status_code=status.HTTP_200_OK)
async def update_pricing(
    pricing_id: UUID,
    payload: PricingUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PricingResponse:
    """Update an existing pricing configuration."""
    await _require_privileged_role(user, db)

    pricing = await db.get(ModelPricing, pricing_id)
    if not pricing:
        raise NotFoundError("Pricing configuration not found.")

    update_data = payload.model_dump(exclude_unset=True)
    for key, val in update_data.items():
        if key == "model_pattern" and val is not None:
            val = val.strip().lower()
        if key == "provider" and val is not None:
            val = val.strip().lower()
        setattr(pricing, key, val)
    pricing.updated_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(pricing)
    return PricingResponse.model_validate(pricing)


@router.delete("/{pricing_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pricing(
    pricing_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a pricing configuration."""
    await _require_privileged_role(user, db)

    pricing = await db.get(ModelPricing, pricing_id)
    if not pricing:
        raise NotFoundError("Pricing configuration not found.")

    await db.delete(pricing)
    await db.commit()
