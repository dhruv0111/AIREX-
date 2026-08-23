# ADR-018: LLM-as-a-Judge

- Status: Accepted
- Date: 2026-08-23
- Phase: 4
- Deciders: AIREX Engineering
- Related: ADR-011 (model gateway), ADR-016 (deterministic evaluators), ADR-019 (rubric versioning), ADR-020 (judge reproducibility)

## Context

Deterministic evaluators cannot capture semantic quality (e.g. an answer that
is factually correct but worded differently). Phase 4 introduces an
LLM-as-a-judge. Judge models can be non-deterministic, costly and biased, so the
design must minimize instability and keep the existing architecture intact.

## Decision

- **Judging is an evaluator**: the `llm_judge` evaluator is registered in the
  same registry as the deterministic evaluators and owns all judge behavior.
  The runner only builds it with a dependency context and awaits it; it never
  mixes judge logic into the runner.
- **The judge model is always invoked through the Model Gateway** — never a
  provider SDK. This reuses retries, timeouts, metrics and error normalization
  (ADR-011).
- **The judge model is independent from the target model**; both are
  snapshotted separately at evaluation creation (ADR-020).
- **Judging is structured**: a versioned prompt asks for JSON, and the response
  is strictly validated (schema, ranges, criterion names, confidence,
  reasoning) before any score is accepted (invalid → ERROR).
- **Scoring is threshold-based**: `score >= threshold` → PASS (the judge's own
  `passed` field is informational only).
- **Confidence is documented as the judge model's self-reported confidence, not
  a calibrated probability.**
- **Bias mitigations** (position independence, structured rubric, fixed 0–1
  range, versioned prompt/rubric, separate target/judge model) are documented
  as mitigations — the project explicitly does **not** claim they eliminate LLM
  judge bias.

## Consequences

- Semantic evaluation is available without any change to the runner's model-call
  path and without a second retry/timeout mechanism.
- Deterministic and judge evaluators can be combined in one run; every
  individual score is preserved alongside a combined decision.
- Judge behavior is auditable and reproducible (prompt/rubric/evaluator/model
  versions are recorded).
