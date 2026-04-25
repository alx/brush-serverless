#!/usr/bin/env bash
# Build both CUDA targets locally and push to GHCR.
#
# Usage:
#   ./scripts/publish.sh <version>          # e.g. v0.1.1
#   ./scripts/publish.sh <version> --no-push
#
# Requires:
#   docker login ghcr.io -u alx --password-stdin <<< "$GITHUB_TOKEN"
#
# Produces tags:
#   ghcr.io/alx/brush-serverless:<version>-cuda12.5  (ubuntu24.04)
#   ghcr.io/alx/brush-serverless:<version>-cuda12.4  (ubuntu22.04)
#   ghcr.io/alx/brush-serverless:<version>            → cuda12.5
#   ghcr.io/alx/brush-serverless:latest               → cuda12.5
set -euo pipefail

REGISTRY="ghcr.io/alx/brush-serverless"
VERSION="${1:-}"
PUSH=1

if [[ -z "$VERSION" ]]; then
  echo "Usage: $0 <version> [--no-push]"
  echo "  e.g. $0 v0.1.1"
  exit 1
fi

for arg in "${@:2}"; do
  case $arg in
    --no-push) PUSH=0 ;;
    *) echo "Unknown flag: $arg"; exit 1 ;;
  esac
done

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

log() { echo "▶ $*"; }

# ── cuda12.5 (ubuntu24.04) ────────────────────────────────────────────────────
log "Building cuda12.5 (ubuntu24.04) — Brush compiles from source, allow ~20 min ..."
docker build \
  --build-arg CUDA_VERSION=12.5.1 \
  --build-arg UBUNTU_VERSION=24.04 \
  -t "${REGISTRY}:${VERSION}-cuda12.5" \
  "$REPO_ROOT"

# ── cuda12.4 (ubuntu22.04) ────────────────────────────────────────────────────
log "Building cuda12.4 (ubuntu22.04) ..."
docker build \
  --build-arg CUDA_VERSION=12.4.1 \
  --build-arg UBUNTU_VERSION=22.04 \
  -t "${REGISTRY}:${VERSION}-cuda12.4" \
  "$REPO_ROOT"

# ── Alias tags (cuda12.5 is the default/latest) ───────────────────────────────
docker tag "${REGISTRY}:${VERSION}-cuda12.5" "${REGISTRY}:${VERSION}"
docker tag "${REGISTRY}:${VERSION}-cuda12.5" "${REGISTRY}:latest"

log "Built tags:"
echo "  ${REGISTRY}:${VERSION}-cuda12.5"
echo "  ${REGISTRY}:${VERSION}-cuda12.4"
echo "  ${REGISTRY}:${VERSION}  →  cuda12.5"
echo "  ${REGISTRY}:latest      →  cuda12.5"

if [[ $PUSH -eq 1 ]]; then
  log "Pushing to GHCR ..."
  docker push "${REGISTRY}:${VERSION}-cuda12.5"
  docker push "${REGISTRY}:${VERSION}-cuda12.4"
  docker push "${REGISTRY}:${VERSION}"
  docker push "${REGISTRY}:latest"
  log "Done. Images available at https://github.com/alx/brush-serverless/pkgs/container/brush-serverless"
else
  log "Skipping push (--no-push). To push manually:"
  echo "  docker push ${REGISTRY}:${VERSION}-cuda12.5"
  echo "  docker push ${REGISTRY}:${VERSION}-cuda12.4"
  echo "  docker push ${REGISTRY}:${VERSION}"
  echo "  docker push ${REGISTRY}:latest"
fi
