# ADR-020: Judge Reproducibility Snapshots

- Status: Accepted
- Date: 2026-08-23
- Phase: 4
- Deciders: AIREX Engineering
- Related: ADR-017 (evaluation reproducibility), ADR-018 (llm judge), ADR-019 (rubric versioning)

## Context

LLM judging is sensitive to the prompt wording, the rubric, the judge model and
its configuration. If any of these change after a run starts, the run's results
would become ambiguous. Phase 4 must guarantee historical judge evaluations are
unambiguous.

## Decision

At creation, every evaluation run freezes judge inputs on `evaluation_runs`
(never mutated afterwards):

- `judge_model_id` + `judge_model_snapshot` — the judge model identity and its
  effective configuration (provider, identifier, temperature/max_tokens/top_p,
  configuration, base URL, model version).
- `judge_rubric_id` + `judge_rubric_snapshot` — the exact rubric version and its
  criteria (ADR-019).
- `judge_prompt_version` — the versioned prompt template used.
- `evaluator_versions` — the `llm_judge` evaluator version (already recorded).

The runner executes the judge **against these snapshots**, not against the live
judge model/rubric rows. Per-result fields (`judge_score`, `judge_confidence`,
`judge_reasoning`, `judge_criteria_scores`, judge model/rubric/prompt refs) make
each result self-describing.

## Consequences

- Changing or deleting a rubric version, editing a judge model, or revising the
  prompt template never rewrites historical judge results.
- A completed judge run can be fully reconstructed: same snapshot ⇒ same prompt
  ⇒ same validated score.
- Extends the Phase 3 reproducibility model (ADR-017) to the judge path.
