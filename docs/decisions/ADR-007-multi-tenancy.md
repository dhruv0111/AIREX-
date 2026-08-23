# ADR-007: Multi-Tenancy by Design

**Status:** Accepted

## Context
Every organization-owned resource must be isolated (PRD §10, AC-SEC-001/002). Authorization must be enforced server-side and never trust client-supplied IDs (spec §2.4, §41).

## Decision
- Every tenant-owned table carries `organization_id`.
- All data access goes through tenant-scoped repositories that inject the org boundary.
- The API resolves the active org from JWT claims + validated membership (the `X-Organization-Id` header is only a context switch, never a privilege grant).
- Cross-tenant access returns 404 to prevent enumeration (AC-SEC-002).

## Alternatives
- Column-scoping only at the query layer (no repository enforcement) — error-prone.
- 403 for cross-tenant access — leaks resource existence.

## Consequences
- Pros: strong isolation, testable (AT-010/AT-012), defense-in-depth.
- Cons: repository discipline required; documented in PERMISSION_MATRIX.
