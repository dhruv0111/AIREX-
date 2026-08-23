# Security Architecture — AIREX

Maps every security requirement from PRD §59–§65, §92–§94, and the security ACs (AC-SEC-001..005, AC-AUTH-*, AC-MODEL-007) to concrete controls. Zero-cost-first: all controls are implemented with free libraries and patterns; paid hardening (KMS, WAF) is production-only optional.

---

## 1. Security Model Overview

```
┌────────────────────────────────────────────────────────────┐
│ Transport (HTTPS/TLS 1.2+; HSTS)                          │
├────────────────────────────────────────────────────────────┤
│ Edge: rate limiting, request validation, CSRF (cookies)    │
├────────────────────────────────────────────────────────────┤
│ AuthN: JWT access/refresh, argon2id passwords, email verify│
│        org API keys (hashed), MFA (later)                  │
├────────────────────────────────────────────────────────────┤
│ AuthZ: RBAC (4 roles) + org tenancy + object-level authz   │
├────────────────────────────────────────────────────────────┤
│ Data: encryption at rest (DB, object storage), Fernet/KMS  │
│       key encryption, secret masking, PII redaction        │
├────────────────────────────────────────────────────────────┤
│ Integrity: audit logging (append-only), outbox events,     │
│            tamper-evident audit (hash chain, optional)     │
├────────────────────────────────────────────────────────────┤
│ Ops: secret hygiene, dependency scanning, SAST/DAST in CI, │
│      logging without secrets                               │
└────────────────────────────────────────────────────────────┘
```

---

## 2. Authentication (PRD §9, §59)

| Requirement | Control | Zero-cost impl | Prod option |
|-------------|---------|----------------|-------------|
| Email/password registration (FR-AUTH-001) | Registration service; uniqueness (AC-AUTH-002) | app code + DB unique | — |
| Login/logout (FR-AUTH-002/003) | Password verify + session revoke | app code | — |
| Password reset (FR-AUTH-004) | Signed one-time token, expiry, rate-limited | app code + Redis rate limit | — |
| Email verification (FR-AUTH-005) | Signed token → verified flag | app code + mailer | SES |
| JWT/session (FR-AUTH-006) | JWT access (short) + refresh (rotating); httpOnly cookie for SSR; Bearer for API | PyJWT, argon2-cffi | KMS key wrapping |
| Password hashing (SEC-AUTH-002) | **argon2id** (memory-hard) | argon2-cffi | — |
| HTTPS (SEC-001) | TLS termination at LB/ingress; HSTS | Traefik/nginx (local), cert local | ACM |
| Token storage | httpOnly, Secure, SameSite=Strict cookies (web); no localStorage | app code | — |

**Session/API key model:**
- User: `access` (15 min) + `refresh` (7 days, rotating, revocable) JWTs; claims include `sub`, `orgs` (membership map) or `org_id` for active org, `role`.
- Programmatic: org API key = `<prefix>_<random>`, stored as **hash only** + encrypted secret for gateway use; created/revoked only by Admin (SEC-AUDIT-003). Never returned in plaintext (AC-SEC-003).

## 3. Authorization (PRD §7, §9; AC-AUTH-005/006, AC-SEC-001/002)

- **RBAC roles:** Admin, Project Owner, Engineer, Viewer (from [`PERMISSION_MATRIX.md`](../PRD_ANALYSIS/PERMISSION_MATRIX.md)). Undefined cells are resolved as **least-privilege assumptions** and recorded in [`ARCHITECTURE_DECISIONS.md`](./ARCHITECTURE_DECISIONS.md) (ADR-SEC-002).
- **Middleware chain (every protected request):**
  1. Authenticate (JWT/API key).
  2. Resolve org + role from claims (ignore client-provided org header for privilege).
  3. **Tenant scope:** repository layer injects `organization_id`; cross-tenant resource IDs → 404 (AC-SEC-002, prevents enumeration).
  4. **Object-level authz:** verify resource belongs to caller's org before any read/write (AC-AUTH-005).
  5. **Role check** on mutating capabilities (AC-AUTH-006: Viewer read-only).
- **Defense in depth:** PostgreSQL RLS enabled on tenant tables as a second barrier.
- Deleted/removed users lose access immediately (AC-SEC-004): session/API-key revocation on removal; middleware re-checks membership each request (cache TTL short).

## 4. Secrets & Key Handling (SEC-API-001/002/003, AC-MODEL-007)

| Secret | Storage | At rest | Handling |
|--------|---------|---------|----------|
| Provider API keys | `models.api_key_encrypted` | **Fernet** (dev/local key) or KMS envelope (prod) | Injected server-side into gateway; masked on read; never logged |
| Org API keys | `api_keys.key_hash` + encrypted secret | Fernet/KMS | Hash for lookup; secret only for gateway/auth |
| DB/Redis passwords | env / secret manager | — | Env in dev; SSM/Secrets Manager in prod |
| JWT signing keys | env / KMS | — | Rotated; refresh tokens revocable |
| Encryption keys | local file (dev) / KMS | — | Rotated |

**Log hygiene (SEC-LOG-002, §94):** structured logs contain `timestamp, request_id, user_id, organization_id, service, level, message`; a redaction filter strips keys/passwords/tokens/unmasked PII before write. Gateway and trace pipelines run the same redactor (AC-MODEL-007, FR-OBS-007).

## 5. Input Validation & Injection Defenses (SEC-INPUT-001..004)

| Threat | Control |
|--------|---------|
| SQL injection | ORM parameterized queries; no raw SQL except reviewed migrations; RLS |
| XSS | React escaping; sanitize rendered LLM/text output; CSP headers |
| CSRF | SameSite=Strict cookies + CSRF token for mutating cookie-authed requests |
| Malformed input | Pydantic schemas on every endpoint; size limits on uploads; strict JSON |
| Prompt injection (platform-level) | Treat any LLM output as untrusted data; never execute; redact before display; the **feature** (FR-PROMPTINJ) tests *customers'* apps, not the platform |
| Data leakage | Privacy toggles (§60) gate prompt/response storage; redaction pipeline; no internal stack traces (SEC-ERR-002) |

## 6. Data Privacy & Redaction (PRD §60)

- **Toggles (org/project level, resolved defaults: raw storage OFF, masking ON, prompt storage per-project, response storage per-project):** stored in `organizations.privacy_policy` / project config (AMB-PRIVACY-001 resolution).
- **Redaction pipeline:** tokenizer-based PII detection → replace with `[PERSON]`, `[PHONE]`, `[EMAIL]`, `[ADDRESS]`, `[ORG]`, `[OTHER]` (extends the PRD examples). Applied at capture points: gateway, traces, dataset display, exports, logs.
- When prompt/response storage is OFF, the gateway records only hashes/counts, not content.

## 7. Rate Limiting (PRD §62)

| Scope | Default (configurable per org, Admin) |
|-------|----------------------------------------|
| API requests | 600 req/min per user/IP (Redis sliding window) |
| Evaluation jobs | e.g., 5 concurrent / 50 per hour per project |
| Model calls | per-provider budget (e.g., 60/min default) |
| Dataset generation | e.g., 10 per hour per project |
| Test generation | e.g., 5 per hour per project |
| Auth endpoints | stricter (login 5/min per account; register 10/hour per IP) |

Implementation: `ratelimit.py` middleware using Redis; `429 RATE_LIMIT_*` with `Retry-After`; limits applied in API server **and** workers (job admission).

## 8. Audit Logging (PRD §61, AC-SEC-005)

- Append-only `audit_logs` table; **no UPDATE/DELETE by application** (DB trigger + restricted role); normal users cannot modify (AC-SEC-005).
- Recorded events: user login, API key created/deleted, project created/deleted, dataset deleted, evaluation executed, config changed, user role changed, plus permission-denied events (§61 list).
- Each row: actor, action, resource, timestamp, IP (where available), result (§61).
- Optional tamper-evidence: per-row hash chain (production hardening).

## 9. Multi-Tenant Security Tests (AC-SEC-001..005)

| AC | Test mapping |
|----|--------------|
| AC-SEC-001 | Cross-tenant read returns empty/404 (e2e security test) |
| AC-SEC-002 | Guess other project ID → 404; ID not used for authz |
| AC-SEC-003 | Read model/API-key endpoints → masked; hash-only lookup |
| AC-SEC-004 | Remove user → immediate 401 on next request |
| AC-SEC-005 | Normal user attempts audit-log write → rejected/immutable |

## 10. Security Testing (PRD §92)

SAST (e.g., Bandit/Semgrep), dependency audit, secret scanning (gitleaks), DAST/OWASP ZAP on staging, plus the §92 manual security test suite: auth bypass, authz bypass, SQLi, XSS, CSRF, rate-limit bypass, secret exposure, cross-tenant, prompt injection, data leakage. These become the `tests/security/` suite.

## 11. Infrastructure Security

- Network: private subnets for DB/Redis/workers; only API/Web exposed via LB.
- TLS everywhere; HSTS; no TLS downgrade.
- Least-privilege IAM (prod): minimal roles for services; secrets via Secret Manager.
- Dependency/container scanning in CI (Trivy); base images pinned.

## 12. Decision Summary

| Decision | WHY | Alternatives | Tradeoff | Cost | Scalability | Security |
|----------|-----|--------------|----------|------|-------------|----------|
| argon2id | Memory-hard password hashing (SEC-AUTH-002) | bcrypt, scrypt | Slower (intended) | Free | — | Strong |
| JWT + rotating refresh | Stateless auth, revocable refresh | Opaque server sessions | Token invalidation complexity | Free | Stateless scale | Good with rotation |
| Fernet/KMS key encryption | Encrypt provider keys at rest (SEC-API-001) | Raw env vars | Key mgmt needed | Free→paid(KMS) | — | Strong |
| RLS + repository scoping | Defense in depth (AC-SEC-001) | Repo-only | RLS complexity | Free | Minor overhead | Strong |
| Append-only audit + triggers | AC-SEC-005 | App-level only | Extra schema | Free | Partitioned | Tamper-resistant |
| Redis rate limiting | Per-org configurable (§62) | In-memory | Redis dependency | Free | Distributed | DoS-resistant |
| 404 on cross-tenant | Enumeration prevention (AC-SEC-002) | 403 | None | Free | — | Stronger |
| Least-privilege RBAC defaults | Resolves AMB-PERM-001 safely | Generous defaults | None | Free | — | Stronger |
