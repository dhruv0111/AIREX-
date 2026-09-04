# AIREX — PHASE 17.2: ARM64 ARCHITECTURE & MULTI-PLATFORM COMPATIBILITY REPORT

**Date:** September 4, 2026  
**Target Hardware:** Oracle Cloud Always Free ARM Ampere A1 (`aarch64` / `linux/arm64`)  
**Auditor:** Antigravity Advanced Agentic Engineering

---

## 1. COMPONENT-BY-COMPONENT ARM64 COMPATIBILITY MATRIX

| Component / Layer | Base Image / Dependency | ARM64 Support | Native vs Emulated | Verification Status |
| :--- | :--- | :---: | :---: | :---: |
| **API Container** | `python:3.12-slim` | **YES** | Native `linux/arm64` | **PASS** |
| **Python C-Extensions** | `asyncpg`, `cryptography`, `bcrypt`, `pydantic-core`, `greenlet` | **YES** | Pre-built wheels available on PyPI for `manylinux_aarch64` | **PASS** |
| **Web Container** | `node:20-alpine` | **YES** | Native `linux/arm64` | **PASS** |
| **Next.js & React 19** | `@next/swc-linux-arm64-musl`, `tailwindcss` | **YES** | Native SWC binaries for ARM64 Alpine | **PASS** |
| **Database Container** | `postgres:16-alpine` | **YES** | Official multi-arch Docker image (`amd64`/`arm64`) | **PASS** |
| **Cache Container** | `redis:7-alpine` | **YES** | Official multi-arch Docker image (`amd64`/`arm64`) | **PASS** |
| **k3s Runtime** | `k3s v1.30+` | **YES** | Native `aarch64` binary by Rancher | **PASS** |
| **Ingress Controller** | `traefik:v2.10` / `ingress-nginx` | **YES** | Native `linux/arm64` images | **PASS** |
| **Cert-Manager** | `cert-manager v1.14+` | **YES** | Native `linux/arm64` images | **PASS** |

---

## 2. MULTI-PLATFORM DOCKER BUILDX COMMANDS

To produce universal container images that run natively on both `linux/amd64` (Intel/AMD) and `linux/arm64` (Oracle Ampere / Apple Silicon), use Docker Buildx:

```bash
# 1. Initialize Docker multi-platform buildx builder
docker buildx create --name airex-builder --use
docker buildx inspect --bootstrap

# 2. Build and push multi-arch API image
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t ghcr.io/<ORGANIZATION>/airex-api:v1.0.0 \
  -t ghcr.io/<ORGANIZATION>/airex-api:latest \
  -f apps/api/Dockerfile \
  apps/api \
  --push

# 3. Build and push multi-arch Web image
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t ghcr.io/<ORGANIZATION>/airex-web:v1.0.0 \
  -t ghcr.io/<ORGANIZATION>/airex-web:latest \
  -f apps/web/Dockerfile \
  . \
  --push
```

---

## 3. IDENTIFIED ARM CAVEATS & RESOLUTIONS

- **PyPI Binary Wheels:** All runtime dependencies in `pyproject.toml` provide official `aarch64` wheels. No runtime compilation (`gcc`) is required inside the production container, maintaining lean image sizes (~180MB for API, ~120MB for Web).
- **Next.js Standalone Runner:** Alpine ARM64 downloads `@next/swc-linux-arm64-musl` during `npm install` automatically, ensuring fast native compilation.
