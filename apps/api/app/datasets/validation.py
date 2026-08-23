"""Dataset record validation (Phase 2 §28–§31).

Validation rules (documented):
- Required: ``input`` must be non-empty; ``expected_output`` must be non-empty.
- ``errors`` block the version (no official version is created).
- ``warnings`` (e.g. duplicate inputs) do NOT block the version — the product
  treats duplicates as a quality signal, not an invalid dataset.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ValidationIssue:
    row: int | None
    field: str | None
    code: str
    message: str


@dataclass
class ValidationResult:
    valid: bool
    record_count: int
    errors: list[ValidationIssue] = field(default_factory=list)
    warnings: list[ValidationIssue] = field(default_factory=list)


def _is_empty(value) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


def validate_records(records: list[dict], *, max_records: int) -> ValidationResult:
    """Validate normalized records; ``max_records`` is the hard record limit."""
    result = ValidationResult(valid=True, record_count=len(records))

    if len(records) > max_records:
        result.errors.append(
            ValidationIssue(
                row=None,
                field=None,
                code="TOO_MANY_RECORDS",
                message=f"Record count {len(records)} exceeds the limit of {max_records}.",
            )
        )
        result.valid = False

    seen_inputs: set[str] = set()
    for index, record in enumerate(records, start=1):
        if _is_empty(record.get("input")):
            result.errors.append(
                ValidationIssue(
                    row=index, field="input", code="EMPTY_VALUE", message="Input cannot be empty."
                )
            )
        if _is_empty(record.get("expected_output")):
            result.errors.append(
                ValidationIssue(
                    row=index,
                    field="expected_output",
                    code="EMPTY_VALUE",
                    message="Expected output cannot be empty.",
                )
            )
        key = str(record.get("input"))
        if key in seen_inputs:
            result.warnings.append(
                ValidationIssue(
                    row=index,
                    field="input",
                    code="DUPLICATE_INPUT",
                    message="Duplicate input detected.",
                )
            )
        else:
            seen_inputs.add(key)

    if result.errors:
        result.valid = False
    return result
