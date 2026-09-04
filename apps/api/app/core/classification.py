"""Platform-wide Data Classification Model (spec Phase 14)."""

from __future__ import annotations

from enum import Enum
from typing import Any


class DataClassification(str, Enum):
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    CONFIDENTIAL = "CONFIDENTIAL"
    RESTRICTED = "RESTRICTED"


_SENSITIVITY_RANK: dict[DataClassification, int] = {
    DataClassification.PUBLIC: 0,
    DataClassification.INTERNAL: 1,
    DataClassification.CONFIDENTIAL: 2,
    DataClassification.RESTRICTED: 3,
}


def get_classification_rank(classification: DataClassification | str) -> int:
    """Return numerical sensitivity rank for a data classification."""
    if isinstance(classification, str):
        try:
            classification = DataClassification(classification.upper())
        except ValueError:
            classification = DataClassification.INTERNAL
    return _SENSITIVITY_RANK.get(classification, 1)


def is_more_or_equally_restrictive(
    candidate: DataClassification | str, base: DataClassification | str
) -> bool:
    """Return True if candidate is at least as restrictive as base."""
    return get_classification_rank(candidate) >= get_classification_rank(base)


def enforce_classification_inheritance(
    parent_classification: DataClassification | str,
    child_classification: DataClassification | str | None,
    allow_downgrade: bool = False,
) -> DataClassification:
    """
    Enforce classification inheritance invariant.
    A child resource cannot automatically receive a less restrictive classification
    than its parent unless allow_downgrade is explicitly authorized.
    """
    if isinstance(parent_classification, str):
        parent_classification = DataClassification(parent_classification.upper())
    
    if child_classification is None:
        return parent_classification

    if isinstance(child_classification, str):
        child_classification = DataClassification(child_classification.upper())

    if not allow_downgrade and get_classification_rank(child_classification) < get_classification_rank(parent_classification):
        raise ValueError(
            f"Classification downgrade prohibited: child ({child_classification.value}) cannot be less restrictive than parent ({parent_classification.value}) without explicit authorization."
        )

    return child_classification
