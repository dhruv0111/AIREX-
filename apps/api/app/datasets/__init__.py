"""Dataset parsing, validation and canonicalization (Phase 2 §19–§33)."""

from app.datasets.canonical import canonicalize, checksum
from app.datasets.parsers import SUPPORTED_FORMATS, parse_dataset, parse_format_from_filename
from app.datasets.validation import ValidationIssue, ValidationResult, validate_records

__all__ = [
    "SUPPORTED_FORMATS",
    "parse_dataset",
    "parse_format_from_filename",
    "validate_records",
    "ValidationIssue",
    "ValidationResult",
    "canonicalize",
    "checksum",
]
