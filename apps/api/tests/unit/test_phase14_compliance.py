"""Unit tests for Phase 14 Compliance, Audit Intelligence & Data Governance."""

from __future__ import annotations

import uuid
import pytest

from app.core.classification import (
    DataClassification,
    get_classification_rank,
    is_more_or_equally_restrictive,
    enforce_classification_inheritance,
)
from app.core.sensitive_data import (
    SensitiveDataAction,
    scan_text,
    redact_text,
    enforce_sensitive_data_policy,
)
from app.services.evidence_service import EvidenceService


def test_data_classification_hierarchy_and_inheritance():
    assert get_classification_rank(DataClassification.PUBLIC) == 0
    assert get_classification_rank(DataClassification.INTERNAL) == 1
    assert get_classification_rank(DataClassification.CONFIDENTIAL) == 2
    assert get_classification_rank(DataClassification.RESTRICTED) == 3

    assert is_more_or_equally_restrictive(DataClassification.RESTRICTED, DataClassification.INTERNAL)
    assert not is_more_or_equally_restrictive(DataClassification.PUBLIC, DataClassification.CONFIDENTIAL)

    # Valid: child equals or exceeds parent
    child = enforce_classification_inheritance(DataClassification.INTERNAL, DataClassification.CONFIDENTIAL)
    assert child == DataClassification.CONFIDENTIAL

    # Default inheritance from parent
    child_default = enforce_classification_inheritance(DataClassification.RESTRICTED, None)
    assert child_default == DataClassification.RESTRICTED

    # Downgrade prohibited without explicit authorization
    with pytest.raises(ValueError, match="Classification downgrade prohibited"):
        enforce_classification_inheritance(DataClassification.CONFIDENTIAL, DataClassification.PUBLIC, allow_downgrade=False)

    # Authorized downgrade
    child_authorized = enforce_classification_inheritance(DataClassification.CONFIDENTIAL, DataClassification.PUBLIC, allow_downgrade=True)
    assert child_authorized == DataClassification.PUBLIC


def test_sensitive_data_detection_patterns():
    # OpenAI key
    text_key = "Connecting with key sk-abcdef1234567890abcdef123456 to endpoint."
    findings = scan_text(text_key)
    assert len(findings) == 1
    assert findings[0].category == "api_key_openai"

    # Email and Phone
    text_pii = "Contact security officer at compliance-team@airex.internal or call +1-555-867-5309."
    findings = scan_text(text_pii)
    categories = {f.category for f in findings}
    assert "email" in categories
    assert "phone" in categories

    # Financial / Credit Card
    text_cc = "Payment card: 4111111111111111 for enterprise subscription."
    findings = scan_text(text_cc)
    assert any(f.category == "credit_card" for f in findings)


def test_sensitive_data_policy_actions():
    sample = "User secret: sk-1234567890123456789012345 and email test@example.com"

    # ALLOW
    out_allow, findings, blocked = enforce_sensitive_data_policy(sample, SensitiveDataAction.ALLOW)
    assert out_allow == sample
    assert len(findings) >= 2
    assert not blocked

    # WARN
    out_warn, findings, blocked = enforce_sensitive_data_policy(sample, SensitiveDataAction.WARN)
    assert out_warn == sample
    assert not blocked

    # REDACT
    out_redact, findings, blocked = enforce_sensitive_data_policy(sample, SensitiveDataAction.REDACT)
    assert "sk-1234567890123456789012345" not in out_redact
    assert "test@example.com" not in out_redact
    assert "[REDACTED:" in out_redact
    assert not blocked

    # BLOCK
    out_block, findings, blocked = enforce_sensitive_data_policy(sample, SensitiveDataAction.BLOCK)
    assert blocked


def test_evidence_fingerprint_determinism():
    data_a = {"model": "gpt-4o", "dataset": "safety_v1", "score": 94.5}
    data_b = {"score": 94.5, "model": "gpt-4o", "dataset": "safety_v1"}  # Different key order

    fp_a = EvidenceService.compute_fingerprint(data_a)
    fp_b = EvidenceService.compute_fingerprint(data_b)

    assert fp_a == fp_b
    assert len(fp_a) == 64  # Valid SHA-256 hex string

    # Mutated payload produces different fingerprint
    data_mutated = {"model": "gpt-4o", "dataset": "safety_v1", "score": 92.0}
    fp_mutated = EvidenceService.compute_fingerprint(data_mutated)
    assert fp_a != fp_mutated
