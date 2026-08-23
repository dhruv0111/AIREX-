# ADR-010: Credential Encryption at Rest

**Status:** Accepted

## Context

AI provider API keys are long-lived secrets (PRD §5.4, §7; spec §17, §19–§22).
Storing them as plaintext in the `providers` table would expose credentials on
any database leak and would violate the platform's own security requirements
(AT-029 secret protection). Credentials must be encrypted at rest, never appear
in API responses or logs, and support rotation.

## Decision

Encrypt provider credentials with **Fernet** (AES-128-CBC + HMAC, from the
`cryptography` library) before persisting them in `providers.encrypted_credentials`.

- The key comes from `CREDENTIAL_ENCRYPTION_KEY` (a Fernet key, base64-encoded
  32 bytes), read at startup via settings and required in non-test environments.
- Encryption/decryption lives in `app/core/encryption.py`
  (`encrypt_credentials`, `decrypt_credentials`, `mask_secret`).
- `ProviderResponse` returns only `masked_key` (first 4 chars + `****` + last 4
  chars); the plaintext is never serialized.
- Rotation (`POST /api/v1/providers/{id}/rotate`) validates the new key first,
  re-encrypts it, and increments `credential_version` for auditability.
- The log scrubber (`mask_secrets`) redacts key-like strings from structured
  logs.

## Alternatives

- Plaintext columns — rejected: credential leak on DB compromise.
- Application-side reversible encryption with a KMS — overkill for a
  self-hosted, zero-cost-first deployment; the app holds the key locally anyway.
- Asymmetric encryption (public key encrypt / private key decrypt) — adds key
  management complexity without a corresponding benefit for a single-service
  deployment.
- Hash-only storage — impossible: the gateway must replay the real key to the
  provider.

## Consequences

- Pros: credentials are unreadable without the encryption key; masking is
  centralized; rotation is explicit and auditable; `credential_version` enables
  future "rotate all keys" policies.
- Cons: the encryption key must be protected and rotated out-of-band; key loss
  makes existing credentials unrecoverable (by design); all Phase 1 code paths
  must use the encryption service rather than reading the column directly.
