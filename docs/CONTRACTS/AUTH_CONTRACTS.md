# Authentication & Authorization Contracts — AIREX

AuthN/AuthZ contract derived from PRD §9 (authentication features + AC-AUTH-001..006), §7 (roles), §59 (security controls), §93 (AC-SEC-001..005), and the security architecture. Three principal mechanisms:

1. **User JWT** (interactive web/API) — access + rotating refresh.
2. **Organization API keys** (programmatic: CLI, CI/CD) — hashed, scoped, revocable.
3. **Session cookie** (SSR web) — httpOnly cookie wrapping the same JWT.

---

## 1. Token Contracts

### 1.1 Access Token (JWT)

| Claim | Type | Description |
|-------|------|-------------|
| `sub` | string | user id |
| `iss` | string | `airex` |
| `aud` | string | `airex-api` |
| `iat` / `exp` | int | issued / expiry (**900 s / 15 min**) |
| `jti` | string | unique token id (revocation/audit) |
| `org` | object | `{organization_id, role}` — **active** org + role at issue |
| `memberships` | int[] | org ids the user belongs to (fast tenant check) |
| `type` | string | `"access"` |

### 1.2 Refresh Token (JWT, rotating)

| Claim | Type | Description |
|-------|------|-------------|
| `sub` | string | user id |
| `type` | string | `"refresh"` |
| `jti` | string | token id, stored in Redis allowlist (`refresh:{jti}`) for revocation |
| `exp` | int | **7 days** |
| `rotation` | string | family id — rotation invalidates prior token in family |

**Rotation rule:** every `POST /auth/refresh` issues a new pair and invalidates the previous refresh (`jti`). Logout revokes the current refresh. User removal revokes **all** refresh tokens + sessions (AC-SEC-004).

### 1.3 Signed One-Time Tokens (email)

| Token | TTL | Use |
|-------|-----|-----|
| `verify_email` | 24 h | AC-AUTH-005 |
| `reset_password` | 30 min | FR-AUTH-004 |
| `invite` | 7 days | org invite (§10) |

Payload: `{user_id|email, purpose, exp}`; HMAC-signed (server secret), single-use (stored nonce).

### 1.4 Organization API Key

| Part | Format | Storage |
|------|--------|---------|
| Display prefix | `airex_` + 8 chars | `api_keys.key_prefix` |
| Secret | `airex_` + 32 base62 chars | returned **once** at creation; only `key_hash` (argon2id/sha256) persisted (AC-SEC-003) |
| Scopes | `["ci","cli"]` | `api_keys.scopes` (least privilege) |

Auth header: `Authorization: Bearer airex_<secret>`. Lookup by hash only; cross-check org, scope, expiry, `deleted_at`.

---

## 2. Auth Flows

### 2.1 Register (AC-AUTH-001/002)
```
POST /auth/register {email, password, full_name}
 → validate (unique email, password ≥ 8, argon2id hash)
 → create users(status=pending)
 → outbox: user.registered → verification email (24h token)
 → 201
```

### 2.2 Verify email (AC-AUTH-005)
```
POST /auth/verify-email {token} → sets email_verified_at, status=active → 200
```

### 2.3 Login (AC-AUTH-003)
```
POST /auth/login {email,password}
 → verify argon2id hash
 → if !verified → 403 AUTH_EMAIL_UNVERIFIED
 → issue access (15m) + refresh (7d, allowlisted)
 → audit user.login (§61)
 → 200 {access_token, refresh_token, token_type, expires_in}
   (SSR: set httpOnly Secure SameSite=Strict cookies; CSRF token issued)
```

### 2.4 Logout
```
POST /auth/logout → revoke refresh jti, clear cookies → 204; audit
```

### 2.5 Refresh
```
POST /auth/refresh {refresh_token} → validate + rotation → new pair
```

### 2.6 Password reset
```
POST /auth/password-reset/request {email} → 202 (no enumeration)
POST /auth/password-reset/confirm {token,password} → update hash, revoke sessions → 200
```

### 2.7 API-key auth (programmatic/CI)
```
Authorization: Bearer airex_<secret>
 → hash lookup → scope check (ci|cli) → org + role resolution (engineer-equivalent for evaluations)
 → audit api key usage (rate-limited)
```

---

## 3. Roles & Capability Map (RBAC contract)

Roles: `admin` · `project_owner` · `engineer` · `viewer` (PRD §7). Capability model = capability-based checks derived from the permission matrix; least-privilege defaults fill the PRD's NS cells (ADR-SEC-002).

| Capability | admin | project_owner | engineer | viewer |
|------------|:-----:|:-------------:|:--------:|:------:|
| manage organization / users / roles | ✅ | ❌ | ❌ | ❌ |
| manage API keys / integrations / policies | ✅ | ❌ | ❌ | ❌ |
| manage projects (create/edit/archive/delete) | ✅ | ✅ | ❌ | ❌ |
| configure models/providers | ✅ | ✅ | ❌ | ❌ |
| manage datasets | ✅ | ✅ | ✅ | ❌ |
| create/approve tests, run evaluations | ✅ | ✅ | ✅ | ❌ |
| create/run experiments, set baselines | ✅ | ✅ | ✅ | ❌ |
| configure alert rules | ✅ | ✅ | ❌ | ❌ |
| manage environments | ✅ | ✅ | ❌ | ❌ |
| research experiments | ✅ | ✅ | ✅ | ❌ |
| view dashboards/reports/experiment results | ✅ | ✅ | ✅ | ✅ |
| **modify datasets/evaluations** | ✅ | ✅ | ✅ | **❌ (AC-AUTH-006)** |
| view audit logs | ✅ | ❌ | ❌ | ❌ |
| export data | ✅ | ✅ | ✅ | ❌ |
| human review | ✅ | ✅ | ✅ | ❌ |

**Authorization evaluation (every request):**
```
1. authenticate (JWT | API key | cookie)
2. resolve org + role from token claims (never trust client headers)
3. tenant check: target resource.organization_id ∈ memberships (else 404)
4. capability check: (role, capability, resource_type) allowed?
5. object-level check for project-scoped resources (AC-SEC-002)
6. audit denied attempts (result=denied)
```

---

## 4. Session & Cookie Contract (SSR web)

| Cookie | Value | Attributes |
|--------|-------|------------|
| `airex_access` | access JWT | HttpOnly, Secure, SameSite=Strict, Path=/api, Max-Age 900 |
| `airex_refresh` | refresh JWT | HttpOnly, Secure, SameSite=Strict, Path=/api/v1/auth, Max-Age 604800 |
| `airex_csrf` | CSRF token | SameSite=Strict, readable by JS (for header) |

- Mutating cookie-authed requests must include `X-CSRF-Token` header matching `airex_csrf` (CSRF control, SEC-INPUT-004).
- Bearer-authed requests (API keys, non-browser) are exempt from CSRF.
- No tokens in `localStorage`/`sessionStorage`.

---

## 5. Tenancy Headers & Claims

| Header | Purpose | Trusted? |
|--------|---------|----------|
| `X-Organization-Id` | Select active org among the caller's memberships | No — server cross-checks against JWT `memberships`; used only to switch context |
| `X-Request-Id` | Correlation | No — echoed |
| `Idempotency-Key` | Idempotency (POST /run, /generate, /versions) | No — validated format |

**Never** derive privileges from client headers; all authorization derives from token claims + resource ownership.

---

## 6. Rate Limits for Auth (§62)

| Scope | Default |
|-------|---------|
| register | 10/hour/IP |
| login | 5/min per account, 20/hour/IP |
| password reset request | 5/hour/account |
| verify/confirm token | 10/hour/IP |
| refresh | 30/min |
| API key usage | `api` scope (600/min/org default) |

---

## 7. Audit Events (auth-related, §61)

`user.login` · `user.logout` · `user.role_changed` · `user.removed` · `api_key.created` · `api_key.deleted` · `authz.denied` — each with actor, action, resource, timestamp, ip, result.

---

## 8. Security Controls (mapped)

| PRD | Control |
|-----|---------|
| §59 HTTPS | TLS everywhere; HSTS |
| §59 password hashing | argon2id (memory-hard) |
| §59 JWT/session security | short-lived access + rotating refresh + allowlist revocation |
| §59 RBAC | §3 capability map |
| §59 API key encryption | `key_hash` + Fernet/KMS-encrypted secret |
| §59 secret masking | keys masked in all responses (FR-PROVIDER-008) |
| §59 CSRF where applicable | §4 cookies + CSRF token |
| §93 AC-SEC-003 | keys never plaintext retrievable |
| §93 AC-SEC-004 | user removal revokes all sessions immediately |
| §93 AC-SEC-005 | audit append-only |
| AC-AUTH-004 | protected APIs reject unauthenticated requests (401 AUTH_MISSING_TOKEN) |
| AC-AUTH-005 | org scoping (404 on cross-tenant) |
| AC-AUTH-006 | viewer cannot modify datasets/evaluations |
| §95 API docs | OpenAPI documents auth per endpoint |

---

## 9. PRD Traceability (AUTH)

| PRD requirement | Contract section |
|-----------------|------------------|
| §9 email/password registration | §2.1 |
| §9 login/logout | §2.3/§2.4 |
| §9 password reset | §2.6 |
| §9 email verification | §2.2 |
| §9 JWT/session | §1.1/§1.2/§4 |
| §9 RBAC | §3 |
| §9 organization membership | §3 + memberships claim |
| §9 project-level permissions | §3 object-level check |
| AC-AUTH-001..006 | §2 + §3 |
| §59 security controls | §8 |
| §62 rate limiting | §6 |
| §61 audit | §7 |
