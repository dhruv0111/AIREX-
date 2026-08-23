"""Unit tests for dataset parsing, validation, canonicalization, storage and
filename sanitization (Phase 2 §57)."""

from __future__ import annotations

import pytest

from app.core.errors import (
    InvalidDatasetEncodingError,  # noqa: F401  (imported for coverage reference)
    InvalidDatasetFormatError,
    InvalidDatasetSchemaError,
)
from app.datasets import (
    canonicalize,
    checksum,
    parse_dataset,
    parse_format_from_filename,
    validate_records,
)
from app.storage import LocalStorageProvider, sanitize_filename

# ------------------------------------------------------------------ parsers


def test_parse_csv_quoted_commas_and_escaped_quotes():
    text = (
        "input,expected_output,category\n"
        '"What is 2+2?","4","math"\n'
        '"He said ""hi"", ok","response","general"\n'
    )
    records = parse_dataset(text, "csv")
    assert len(records) == 2
    assert records[0] == {"input": "What is 2+2?", "expected_output": "4", "category": "math"}
    assert records[1]["input"] == 'He said "hi", ok'


def test_parse_csv_utf8_and_empty_values():
    text = 'input,expected_output,category\n"café","naïve","general"\n"",value,cat\n'
    records = parse_dataset(text, "csv")
    assert records[0]["input"] == "café"
    assert records[0]["expected_output"] == "naïve"
    # empty input is preserved for validation to flag
    assert records[1]["input"] == ""


def test_parse_csv_missing_input_header():
    with pytest.raises(InvalidDatasetSchemaError):
        parse_dataset("foo,bar\n1,2\n", "csv")


def test_parse_json_valid():
    text = '[{"input":"q","expected_output":"a","category":"math"}]'
    records = parse_dataset(text, "json")
    assert records == [{"input": "q", "expected_output": "a", "category": "math"}]


def test_parse_json_malformed():
    with pytest.raises(InvalidDatasetSchemaError):
        parse_dataset("{not json", "json")


def test_parse_json_non_array():
    with pytest.raises(InvalidDatasetSchemaError):
        parse_dataset('{"input":"q"}', "json")


def test_parse_jsonl_valid_and_blank_lines():
    text = '{"input":"q1","expected_output":"a1"}\n' "\n" '{"input":"q2","expected_output":"a2"}\n'
    records = parse_dataset(text, "jsonl")
    assert len(records) == 2


def test_parse_jsonl_malformed_reports_line():
    text = '{"input":"q1"}\n{bad\n{"input":"q3"}\n'
    with pytest.raises(InvalidDatasetSchemaError) as exc:
        parse_dataset(text, "jsonl")
    assert "line 2" in str(exc.value.message)


def test_parse_unsupported_format():
    with pytest.raises(InvalidDatasetFormatError):
        parse_dataset("anything", "xlsx")


def test_parse_format_from_filename():
    assert parse_format_from_filename("data.csv") == "csv"
    assert parse_format_from_filename("data.json") == "json"
    assert parse_format_from_filename("data.jsonl") == "jsonl"
    assert parse_format_from_filename("data.xlsx") is None
    assert parse_format_from_filename(None) is None


def test_normalize_drops_unknown_keys_and_meta_alias():
    records = parse_dataset(
        '[{"input":"q","expected_output":"a","extra":"x","meta":{"k":1}}]', "json"
    )
    assert records[0] == {"input": "q", "expected_output": "a", "metadata": {"k": 1}}


# --------------------------------------------------------------- validation


def test_validate_requires_input_and_expected_output():
    result = validate_records([{"input": "", "expected_output": "a"}], max_records=100)
    assert result.valid is False
    codes = {e.code for e in result.errors}
    assert "EMPTY_VALUE" in codes


def test_validate_duplicates_are_warnings():
    records = [
        {"input": "q", "expected_output": "a"},
        {"input": "q", "expected_output": "b"},
    ]
    result = validate_records(records, max_records=100)
    assert result.valid is True
    assert any(w.code == "DUPLICATE_INPUT" for w in result.warnings)


def test_validate_too_many_records():
    records = [{"input": f"q{i}", "expected_output": "a"} for i in range(10)]
    result = validate_records(records, max_records=5)
    assert result.valid is False
    assert any(e.code == "TOO_MANY_RECORDS" for e in result.errors)


# ------------------------------------------------------------ canonicalization


def test_canonicalize_is_deterministic_and_sorted():
    a = [{"input": "q", "expected_output": "a", "category": "math"}]
    b = [{"category": "math", "expected_output": "a", "input": "q"}]
    assert canonicalize(a) == canonicalize(b)


def test_canonicalize_drops_nulls_and_unknown_keys():
    a = canonicalize([{"input": "q", "expected_output": "a", "context": None, "extra": 1}])
    b = canonicalize([{"input": "q", "expected_output": "a"}])
    assert a == b


def test_checksum_same_content_same_digest():
    r1 = [{"input": "q", "expected_output": "a", "category": "math"}]
    r2 = [{"category": "math", "input": "q", "expected_output": "a"}]
    assert checksum(r1) == checksum(r2)
    assert len(checksum(r1)) == 64


def test_checksum_differs_for_different_content():
    assert checksum([{"input": "q", "expected_output": "a"}]) != checksum(
        [{"input": "q", "expected_output": "b"}]
    )


# ------------------------------------------------------------------ storage


def test_local_storage_roundtrip(tmp_path):
    provider = LocalStorageProvider(tmp_path)
    provider.put("datasets/x/versions/1/dataset.jsonl", b"hello")
    assert provider.exists("datasets/x/versions/1/dataset.jsonl")
    assert provider.get("datasets/x/versions/1/dataset.jsonl") == b"hello"
    provider.delete("datasets/x/versions/1/dataset.jsonl")
    assert not provider.exists("datasets/x/versions/1/dataset.jsonl")


def test_local_storage_rejects_path_traversal(tmp_path):
    provider = LocalStorageProvider(tmp_path)
    with pytest.raises(InvalidDatasetSchemaError):
        provider.put("../../secret.txt", b"x")
    with pytest.raises(InvalidDatasetSchemaError):
        provider.put("/etc/passwd", b"x")


def test_local_storage_get_missing_raises(tmp_path):
    provider = LocalStorageProvider(tmp_path)
    with pytest.raises(FileNotFoundError):
        provider.get("datasets/missing")


# ------------------------------------------------------------- sanitization


def test_sanitize_filename_rejects_traversal():
    assert sanitize_filename("../../secret.txt") != "../../secret.txt"
    assert sanitize_filename("..\\..\\secret.txt") != "..\\..\\secret.txt"
    assert "/" not in sanitize_filename("../a/b.txt")
    assert sanitize_filename(None) == "dataset"
    assert sanitize_filename("data.csv") == "data.csv"
