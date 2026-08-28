# ADR-025: Regression Detection and Quality Gates

- Status: Accepted
- Date: 2026-08-25
- Phase: 6
- Deciders: AIREX Engineering
- Related: ADR-024 (Experimentation Lifecycle), ADR-015 (Evaluation engine)

## Context

AIREX needs to identify if a candidate configuration has degraded quality compared to a baseline. 
This requires statistical significance calculations (Welch's t-test) to distinguish actual performance regressions from noise, effect size estimation (Cohen's d), classification of regression severity, and automated release policies (quality gates).

## Decision

### Pure Python Statistical Analysis
To avoid external binary compilation dependencies (e.g. `scipy` or `statsmodels`), statistical calculations are implemented in pure Python:
- **Welch's t-test**: Standard error of difference, degrees of freedom (Welch–Satterthwaite equation), and normal approximation of the cumulative distribution function (using `math.erf` to resolve p-values).
- **Degenerate Variance Handling**: If all baseline and candidate outputs are deterministic and standard error is 0, the engine yields $p = 0.0$ when means differ to correctly denote absolute significance.
- **Cohen's d**: Standard pooled deviation metrics calculate standard effect sizes.

### Regression Severity Classification
Calculated degradations classify regressions into clear tiers:
- Degradation $< 0.02$: `MINOR`
- Degradation $\ge 0.02$ and $< 0.05$: `MODERATE`
- Degradation $\ge 0.05$: `SEVERE`

### Quality Gate release criteria
Each gate specifies a rule checking a metric value against operator limits (`GT`, `GTE`, `LT`, `LTE`, `EQ`). 
Outcomes evaluate to:
- `PASS`: Candidate value satisfies rule threshold AND no significant regression is detected.
- `FAIL`: Candidate value violates rule threshold OR a regression is detected.
- `INCONCLUSIVE`: If statistical sample sizes are too small to draw significance.

## Consequences

- Noise is successfully separated from real regressions.
- Third-party compilation dependencies are avoided.
- Automated gates enable continuous integration regression checks.
