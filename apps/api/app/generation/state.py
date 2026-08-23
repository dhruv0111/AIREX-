"""Generation request + candidate state machines (Phase 5)."""

from __future__ import annotations

from app.core.errors import ConflictError

_REQUEST_ALLOWED: dict[str, set[str]] = {
    "QUEUED": {"RUNNING", "CANCELLED"},
    "RUNNING": {"COMPLETED", "FAILED", "CANCELLED"},
    "COMPLETED": set(),
    "FAILED": set(),
    "CANCELLED": set(),
}

_CANDIDATE_ALLOWED: dict[str, set[str]] = {
    "PENDING_REVIEW": {"APPROVED", "REJECTED"},
    "APPROVED": set(),
    "REJECTED": set(),
}


def validate_request_transition(current: str, new: str) -> None:
    if new not in _REQUEST_ALLOWED.get(current, set()):
        raise ConflictError(f"Cannot transition generation from {current} to {new}.")


def validate_candidate_transition(current: str, new: str) -> None:
    if new not in _CANDIDATE_ALLOWED.get(current, set()):
        raise ConflictError(f"Cannot transition candidate from {current} to {new}.")
