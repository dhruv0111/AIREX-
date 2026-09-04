#!/usr/bin/env bash
set -euo pipefail

# AIREX — Build & Push Multi-Architecture Images (linux/amd64, linux/arm64)
# Zero-Cost: Uses GitHub Container Registry (ghcr.io) or local Docker Buildx

REGISTRY=${REGISTRY:-"ghcr.io/dhruv0111"}
VERSION_TAG=${VERSION_TAG:-"v1.0.0-$(git rev-parse --short HEAD)"}

echo "=== Building Multi-Arch AIREX Images: ${VERSION_TAG} ==="

# Ensure buildx builder exists
if ! docker buildx inspect airex-builder >/dev/null 2>&1; then
    echo "Creating new Docker buildx builder 'airex-builder'..."
    docker buildx create --name airex-builder --use
    docker buildx inspect --bootstrap
fi

echo "1. Building & Pushing API Multi-Arch Image..."
docker buildx build \
    --platform linux/amd64,linux/arm64 \
    -t "${REGISTRY}/airex-api:${VERSION_TAG}" \
    -t "${REGISTRY}/airex-api:latest" \
    -f apps/api/Dockerfile \
    apps/api \
    ${PUSH_FLAG:---load}

echo "2. Building & Pushing Web Multi-Arch Image..."
docker buildx build \
    --platform linux/amd64,linux/arm64 \
    -t "${REGISTRY}/airex-web:${VERSION_TAG}" \
    -t "${REGISTRY}/airex-web:latest" \
    -f apps/web/Dockerfile \
    . \
    ${PUSH_FLAG:---load}

echo "=== Build Complete for Tag: ${VERSION_TAG} ==="
