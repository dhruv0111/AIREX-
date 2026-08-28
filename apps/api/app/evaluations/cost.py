"""LLM Span cost calculation engine (Phase 8)."""

from __future__ import annotations

from decimal import Decimal
import fnmatch
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pricing import ModelPricing


async def calculate_span_cost(
    session: AsyncSession,
    *,
    provider: str,
    model: str,
    input_tokens: int | None,
    output_tokens: int | None,
) -> Decimal | None:
    """Look up versioned pricing configuration and calculate cost using Decimal.
    
    If pricing is missing or token counts are missing, returns None.
    """
    if input_tokens is None or output_tokens is None:
        return None

    # Load all pricing configurations for this provider
    stmt = select(ModelPricing).where(ModelPricing.provider == provider.lower())
    res = await session.execute(stmt)
    pricings = res.scalars().all()

    # Find matching pattern (e.g. "gpt-4o*" matching "gpt-4o-2024-05-13")
    matched_pricing = None
    for p in pricings:
        # Match pattern exactly or with wildcard
        pattern = p.model_pattern.lower()
        if fnmatch.fnmatch(model.lower(), pattern):
            matched_pricing = p
            break

    if not matched_pricing:
        return None

    input_price = Decimal(str(matched_pricing.input_price_per_1k))
    output_price = Decimal(str(matched_pricing.output_price_per_1k))
    
    in_tokens = Decimal(input_tokens)
    out_tokens = Decimal(output_tokens)
    
    cost = (in_tokens / Decimal("1000")) * input_price + (out_tokens / Decimal("1000")) * output_price
    return cost
