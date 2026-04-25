#!/usr/bin/env bash
set -euo pipefail

IMAGE="brush-serverless:local-test"
# Pre-generated COLMAP workspace from lighthouse.mp4 (30 frames).
# Generate it by running colmap-serverless/scripts/test_local.sh and extracting
# the colmap_workspace_b64 value, or download the fixture from:
# https://github.com/alx/brush-serverless/releases/download/v0.1.0/lighthouse_colmap_workspace.tar.gz
FIXTURE_URL="https://github.com/alx/brush-serverless/releases/download/v0.1.0/lighthouse_colmap_workspace.tar.gz"
STEPS=500       # low count so the test finishes in a few minutes
TIMEOUT=600     # seconds

# ── flags ──────────────────────────────────────────────────────────────────────
NO_BUILD=0
for arg in "$@"; do
  case $arg in
    --no-build) NO_BUILD=1 ;;
    *) echo "Usage: $0 [--no-build]"; exit 1 ;;
  esac
done

# ── helpers ────────────────────────────────────────────────────────────────────
pass() { echo "[PASS] $*"; }
fail() { echo "[FAIL] $*"; exit 1; }

# ── GPU check ─────────────────────────────────────────────────────────────────
if ! docker info 2>/dev/null | grep -q "nvidia"; then
  echo "WARNING: nvidia runtime not listed in 'docker info'."
  echo "  Run: sudo nvidia-ctk runtime configure --runtime=docker && sudo systemctl restart docker"
fi

# ── build ─────────────────────────────────────────────────────────────────────
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [[ $NO_BUILD -eq 0 ]]; then
  echo "Building $IMAGE (Brush from source — first build ~20 min) ..."
  docker build -t "$IMAGE" "$REPO_ROOT"
else
  echo "Skipping build (--no-build)"
fi

# ── download colmap workspace fixture ────────────────────────────────────────
FIXTURE_TAR=$(mktemp --suffix=.tar.gz)
trap 'rm -f "$FIXTURE_TAR" "$TMPLOG"' EXIT

echo "Downloading COLMAP workspace fixture..."
curl -fL "$FIXTURE_URL" -o "$FIXTURE_TAR"
WORKSPACE_B64=$(base64 -w 0 "$FIXTURE_TAR")

# ── run handler with test input ───────────────────────────────────────────────
echo ""
echo "Running test job (steps=$STEPS, timeout=${TIMEOUT}s) ..."

TEST_INPUT=$(printf '{"input":{"colmap_workspace_b64":"%s","steps":%d}}' \
  "$WORKSPACE_B64" "$STEPS")

TMPLOG=$(mktemp)

timeout "$TIMEOUT" docker run --rm --gpus all \
  "$IMAGE" \
  python3 handler.py --test_input "$TEST_INPUT" 2>&1 | tee "$TMPLOG" || {
  fail "Container exited non-zero or timed out after ${TIMEOUT}s"
}

# ── validate output ───────────────────────────────────────────────────────────
if ! grep -q "completed successfully" "$TMPLOG"; then
  fail "Did not find 'completed successfully' in output"
fi

if ! grep -q "'ply_base64':" "$TMPLOG"; then
  fail "ply_base64 key not found in output"
fi

LOGSIZE=$(wc -c < "$TMPLOG")
if [[ "$LOGSIZE" -lt 100000 ]]; then
  fail "Output suspiciously small (${LOGSIZE} bytes) — ply_base64 likely empty"
fi

echo ""
pass "Job completed successfully, ply_base64 present (${LOGSIZE} bytes)"
