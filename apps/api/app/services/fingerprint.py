"""Configuration fingerprinting for model, provider, policy, and evaluation environments (Phase 10)."""

from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import UUID


def compute_configuration_fingerprint(
    *,
    model_id: UUID | str,
    provider_id: UUID | str,
    environment_id: UUID | str,
    model_version: str | None = None,
    model_configuration: dict[str, Any] | None = None,
    dataset_version_id: UUID | str | None = None,
    evaluation_version: str | None = None,
    benchmark_version: str | None = None,
    policy_version: int = 1,
) -> str:
    """Compute a deterministic SHA-256 fingerprint representing all configuration inputs."""
    # Canonicalize configuration dict
    config_str = json.dumps(model_configuration or {}, sort_keys=True, separators=(",", ":"))
    
    payload = (
        f"model:{str(model_id)}|"
        f"provider:{str(provider_id)}|"
        f"env:{str(environment_id)}|"
        f"model_version:{str(model_version or '')}|"
        f"config:{config_str}|"
        f"dataset_version:{str(dataset_version_id or '')}|"
        f"evaluation_version:{str(evaluation_version or '')}|"
        f"benchmark_version:{str(benchmark_version or '')}|"
        f"policy_version:{policy_version}"
    )
    
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
