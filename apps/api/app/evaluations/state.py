"""Evaluation run state machine (Phase 3 §8).

Invalid transitions are rejected with a 409 conflict.
"""

from __future__ import annotations

from app.core.errors import ConflictError

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "QUEUED": {"RUNNING", "CANCELLED", "FAILED"},
    "RUNNING": {"COMPLETED", "FAILED", "CANCELLED"},
    "COMPLETED": set(),
    "FAILED": set(),
    "CANCELLED": set(),
}


def validate_transition(current: str, new: str) -> None:
    """Raise ConflictError when ``current -> new`` is not allowed (§8)."""
    allowed = ALLOWED_TRANSITIONS.get(current, set())
    if new not in allowed:
        raise ConflictError(
            f"Cannot transition evaluation from {current} to {new}.",
        )
