"""AI test generation domain package (Phase 5)."""

from app.generation.candidate import compute_quality_score, fingerprint_candidate
from app.generation.config import (
    DEFAULT_COUNT,
    DIFFICULTIES,
    GENERATION_TYPES,
    MAX_COUNT,
    SOURCE_TYPES,
    validate_generation_config,
    validate_generation_type,
    validate_source_type,
)
from app.generation.parser import GenerationParseError, parse_generation_output, validate_candidate
from app.generation.prompts import (
    GENERATION_PROMPT_VERSION,
    build_generation_messages,
    build_generation_prompt,
    render_source_material,
)
from app.generation.runner import GenerationRunner, recover_stale_generations
from app.generation.state import validate_candidate_transition, validate_request_transition

__all__ = [
    "DEFAULT_COUNT",
    "DIFFICULTIES",
    "GENERATION_TYPES",
    "MAX_COUNT",
    "SOURCE_TYPES",
    "validate_generation_config",
    "validate_generation_type",
    "validate_source_type",
    "GenerationParseError",
    "parse_generation_output",
    "validate_candidate",
    "GENERATION_PROMPT_VERSION",
    "build_generation_messages",
    "build_generation_prompt",
    "render_source_material",
    "validate_candidate_transition",
    "validate_request_transition",
    "compute_quality_score",
    "fingerprint_candidate",
    "GenerationRunner",
    "recover_stale_generations",
]
