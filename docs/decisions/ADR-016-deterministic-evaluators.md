# ADR-016: Deterministic Evaluators (no LLM-as-a-judge)

- Status: Accepted
- Date: 2026-08-23
- Phase: 3
- Deciders: AIREX Engineering
- Related: ADR-015 (evaluation engine), ADR-017 (reproducibility)

## Context

Evaluations need scoring logic ("evaluators"). A judge model ("LLM-as-a-judge")
is non-deterministic, costly, and hard to reproduce across runs and tenants.
Phase 3 must ship a trustworthy baseline evaluation capability.

## Decision

- Ship **only deterministic, provider-independent evaluators** in Phase 3.
- Evaluators are discovered through an `EvaluatorRegistry` by name; the runner
  never contains a conditional over evaluator types.
- Each evaluator implements `evaluate(expected, actual, config) ->
  EvaluationScore` and carries a **semantic version** so a historical run records
  exactly which evaluator version produced each score.
- Core evaluators (all `version 1.0.0`):

  | Evaluator | Behavior |
  | --- | --- |
  | `exact_match` | trimmed string equality |
  | `case_insensitive_exact_match` | case/whitespace-insensitive equality |
  | `contains` | expected substring present in output |
  | `regex` | `re.search`; invalid pattern → error |
  | `json_match` | key-order-independent JSON equality |
  | `numeric_match` | absolute difference ≤ config `tolerance` |
  | `length` | output length within `min_length`/`max_length` |

- An evaluator that cannot execute (e.g. invalid regex, missing bounds) raises
  `EvaluatorError`; the runner records an **ERROR** result
  (`EVALUATOR_ERROR`) without aborting the run.
- Non-matching outputs yield **FAIL** (`ASSERTION_FAILED`).

## Consequences

- Results are deterministic and reproducible across runs (same input + evaluator
  version ⇒ same score).
- No dependency on a judge model, keys, or additional cost for scoring.
- LLM-as-a-judge can be added later behind the same `Evaluator` protocol without
  changing the runner.
