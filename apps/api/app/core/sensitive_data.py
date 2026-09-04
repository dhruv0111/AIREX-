"""Deterministic Sensitive Data Inspection & Policy Enforcement Engine (spec Phase 14)."""

from __future__ import annotations

import re
from enum import Enum
from typing import Any


class SensitiveDataAction(str, Enum):
    ALLOW = "ALLOW"
    WARN = "WARN"
    REDACT = "REDACT"
    BLOCK = "BLOCK"


# Deterministic, explainable regex patterns
_PATTERNS: dict[str, re.Pattern[str]] = {
    "api_key_openai": re.compile(r"\bsk-[a-zA-Z0-9_-]{20,}\b"),
    "api_key_github": re.compile(r"\bghp_[a-zA-Z0-9]{36}\b"),
    "api_key_aws": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "bearer_jwt": re.compile(r"\beyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\b"),
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
    "phone": re.compile(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    "credit_card": re.compile(r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|3(?:0[0-5]|[68][0-9])[0-9]{11}|6(?:011|5[0-9]{2})[0-9]{12})\b"),
    "iban": re.compile(r"\b[A-Z]{2}[0-9]{2}(?:[ ]?[A-Z0-9]{4}){4,7}\b"),
    "password_field": re.compile(r"""(?i)(?:password|passwd|pwd|secret)\s*[:=]\s*['"]?([^\s'"]{6,})['"]?"""),
}


class SensitiveDataFinding:
    def __init__(self, category: str, match: str, start: int, end: int) -> None:
        self.category = category
        self.match = match
        self.start = start
        self.end = end

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "match_snippet": self.match[:2] + "****" + self.match[-2:] if len(self.match) > 4 else "****",
            "start": self.start,
            "end": self.end,
        }


def scan_text(
    text: str, custom_patterns: dict[str, str] | None = None
) -> list[SensitiveDataFinding]:
    """Scan a string for sensitive data categories and return findings."""
    if not text or not isinstance(text, str):
        return []

    findings: list[SensitiveDataFinding] = []

    # Built-in patterns
    for cat, pattern in _PATTERNS.items():
        for m in pattern.finditer(text):
            findings.append(
                SensitiveDataFinding(
                    category=cat,
                    match=m.group(0),
                    start=m.start(),
                    end=m.end(),
                )
            )

    # Custom patterns
    if custom_patterns:
        for cat, pat_str in custom_patterns.items():
            try:
                cp = re.compile(pat_str)
                for m in cp.finditer(text):
                    findings.append(
                        SensitiveDataFinding(
                            category=cat,
                            match=m.group(0),
                            start=m.start(),
                            end=m.end(),
                        )
                    )
            except re.error:
                continue

    return findings


def redact_text(
    text: str, custom_patterns: dict[str, str] | None = None
) -> tuple[str, list[SensitiveDataFinding]]:
    """Redact sensitive occurrences in a string and return (redacted_text, findings)."""
    findings = scan_text(text, custom_patterns)
    if not findings:
        return text, []

    # Sort descending by start to replace without altering previous indices
    sorted_findings = sorted(findings, key=lambda f: f.start, reverse=True)
    res = text
    for f in sorted_findings:
        replacement = f"[REDACTED:{f.category.upper()}]"
        res = res[: f.start] + replacement + res[f.end :]

    return res, findings


def enforce_sensitive_data_policy(
    text: str,
    action: SensitiveDataAction | str = SensitiveDataAction.REDACT,
    custom_patterns: dict[str, str] | None = None,
) -> tuple[str, list[dict[str, Any]], bool]:
    """
    Apply sensitive data policy to text.
    Returns: (output_text, findings_summary, is_blocked)
    """
    if isinstance(action, str):
        try:
            action = SensitiveDataAction(action.upper())
        except ValueError:
            action = SensitiveDataAction.REDACT

    findings = scan_text(text, custom_patterns)
    findings_dicts = [f.to_dict() for f in findings]

    if not findings:
        return text, [], False

    if action == SensitiveDataAction.ALLOW:
        return text, findings_dicts, False

    if action == SensitiveDataAction.WARN:
        return text, findings_dicts, False

    if action == SensitiveDataAction.REDACT:
        redacted, _ = redact_text(text, custom_patterns)
        return redacted, findings_dicts, False

    if action == SensitiveDataAction.BLOCK:
        return text, findings_dicts, True

    return text, findings_dicts, False


def sanitize_payload(
    payload: Any,
    action: SensitiveDataAction | str = SensitiveDataAction.REDACT,
    custom_patterns: dict[str, str] | None = None,
) -> tuple[Any, list[dict[str, Any]], bool]:
    """Recursively enforce sensitive data policy across strings, dicts, and lists in a payload.

    Returns (sanitized_payload, all_findings, is_blocked).
    If action is BLOCK and any sensitive data is discovered, returns (payload, all_findings, True).
    """
    if isinstance(action, str):
        try:
            action = SensitiveDataAction(action.upper())
        except ValueError:
            action = SensitiveDataAction.REDACT

    all_findings: list[dict[str, Any]] = []
    has_block = False

    def _walk(obj: Any) -> Any:
        nonlocal has_block
        if obj is None:
            return None
        if isinstance(obj, str):
            out_text, findings, blocked = enforce_sensitive_data_policy(obj, action, custom_patterns)
            if findings:
                all_findings.extend(findings)
            if blocked:
                has_block = True
            return out_text
        elif isinstance(obj, dict):
            new_dict = {}
            for k, v in obj.items():
                new_key = _walk(k) if isinstance(k, str) else k
                new_dict[new_key] = _walk(v)
            return new_dict
        elif isinstance(obj, (list, tuple)):
            return [_walk(item) for item in obj]
        else:
            return obj

    sanitized = _walk(payload)
    return sanitized, all_findings, has_block

