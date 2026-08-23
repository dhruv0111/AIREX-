"""CSV / JSON / JSONL dataset parsers (Phase 2 §19–§22).

Each parser returns a list of normalized record dicts with a fixed shape::

    {"input", "expected_output", "context", "category", "difficulty", "metadata"}

Structural failures (unsupported format, malformed JSON/CSV/JSONL) raise the
standardized ``INVALID_DATASET_FORMAT`` / ``INVALID_DATASET_SCHEMA`` errors so
no partial official version is ever created (Phase 2 §36–§37).
"""

from __future__ import annotations

import csv
import io
import json

from app.core.errors import InvalidDatasetFormatError, InvalidDatasetSchemaError

SUPPORTED_FORMATS = ("csv", "json", "jsonl")

# Keys a normalized record may carry.
_RECORD_KEYS = ("input", "expected_output", "context", "category", "difficulty", "metadata")


def parse_format_from_filename(filename: str | None) -> str | None:
    """Infer the format from a filename extension (case-insensitive)."""
    if not filename:
        return None
    suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if suffix in SUPPORTED_FORMATS:
        return suffix
    if suffix == "jsonl":
        return "jsonl"
    return None


def _normalize_record(raw: dict) -> dict:
    """Project a raw row onto the canonical record shape (unknown keys dropped)."""
    normalized: dict = {}
    for key in _RECORD_KEYS:
        value = raw.get(key)
        # Accept "meta" as an alias for metadata (common in exports).
        if key == "metadata" and value is None:
            value = raw.get("meta")
        if value is not None:
            normalized[key] = value
    return normalized


def _normalize_text(value) -> str | None:
    if value is None:
        return None
    return str(value)


def parse_csv(text: str) -> list[dict]:
    """Parse a simple CSV with a header row. Handles quoted commas/escapes
    (the stdlib csv module) and UTF-8 text."""
    try:
        reader = csv.DictReader(io.StringIO(text))
    except csv.Error as exc:  # pragma: no cover - defensive
        raise InvalidDatasetSchemaError(f"Malformed CSV: {exc}")
    if not reader.fieldnames:
        raise InvalidDatasetSchemaError("CSV must contain a header row.")
    if "input" not in reader.fieldnames:
        raise InvalidDatasetSchemaError("CSV must contain an 'input' header column.")
    records: list[dict] = []
    for raw in reader:
        # csv.DictReader yields dicts of str|None; normalize text fields.
        record = {
            "input": _normalize_text(raw.get("input")),
            "expected_output": _normalize_text(raw.get("expected_output")),
            "context": raw.get("context"),
            "category": _normalize_text(raw.get("category")),
            "difficulty": _normalize_text(raw.get("difficulty")),
            "metadata": raw.get("metadata"),
        }
        records.append(_normalize_record(record))
    return records


def parse_json(text: str) -> list[dict]:
    """Parse a top-level JSON array of record objects (Phase 2 §21)."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise InvalidDatasetSchemaError(f"Malformed JSON: {exc.msg} (line {exc.lineno}).")
    if not isinstance(data, list):
        raise InvalidDatasetSchemaError("JSON dataset must be an array of records.")
    records: list[dict] = []
    for item in data:
        if not isinstance(item, dict):
            raise InvalidDatasetSchemaError("JSON dataset records must be objects.")
        records.append(_normalize_record(item))
    return records


def parse_jsonl(text: str) -> list[dict]:
    """Parse newline-delimited JSON, reporting the malformed line number (Phase 2 §22)."""
    records: list[dict] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            item = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise InvalidDatasetSchemaError(f"Malformed JSONL at line {lineno}: {exc.msg}.")
        if not isinstance(item, dict):
            raise InvalidDatasetSchemaError(f"JSONL line {lineno} must be an object.")
        records.append(_normalize_record(item))
    return records


def parse_dataset(text: str, fmt: str | None) -> list[dict]:
    """Parse ``text`` according to ``fmt`` (one of csv/json/jsonl)."""
    normalized = (fmt or "").lower().lstrip(".")
    if normalized not in SUPPORTED_FORMATS:
        raise InvalidDatasetFormatError(f"Unsupported dataset format: {fmt!r}.")
    if normalized == "csv":
        return parse_csv(text)
    if normalized == "json":
        return parse_json(text)
    return parse_jsonl(text)
