#!/usr/bin/env bash
# vendor-harness.sh — copy the pinned DeerFlow harness into agent/vendor/
#
# Run this before `docker build` or `uv pip install -e .` in development.
# The vendor/ directory is gitignored; this script is the canonical way to
# populate it from the reference clone.
#
# Usage:
#   ./scripts/vendor-harness.sh
#
# Requirements:
#   - ../deer-flow-reference/ must be cloned and checked out
#   - The checked-out commit must match agent/deerflow_config/HARNESS_VERSION

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REF_DIR="$(cd "$AGENT_DIR/../deer-flow-reference" 2>/dev/null || true && pwd 2>/dev/null || echo "")"
HARNESS_SRC="$REF_DIR/backend/packages/harness"
HARNESS_DST="$AGENT_DIR/vendor/deerflow-harness"
VERSION_FILE="$AGENT_DIR/deerflow_config/HARNESS_VERSION"

# ── 1. Check reference repo exists ──────────────────────────────────────────
if [ -z "$REF_DIR" ] || [ ! -d "$REF_DIR" ]; then
  echo "ERROR: ../deer-flow-reference/ not found."
  echo "Clone it first: git clone <deerflow-repo-url> ../deer-flow-reference"
  exit 1
fi

if [ ! -d "$HARNESS_SRC" ]; then
  echo "ERROR: Harness package not found at $HARNESS_SRC"
  echo "Check that the reference repo has backend/packages/harness/"
  exit 1
fi

# ── 2. Verify commit SHA matches HARNESS_VERSION ────────────────────────────
PINNED_SHA="$(cat "$VERSION_FILE" | tr -d '[:space:]')"
CURRENT_SHA="$(git -C "$REF_DIR" rev-parse HEAD | cut -c1-7)"

if [ "$CURRENT_SHA" != "$PINNED_SHA" ]; then
  echo "ERROR: Commit SHA mismatch."
  echo "  Pinned in HARNESS_VERSION : $PINNED_SHA"
  echo "  Current in reference repo : $CURRENT_SHA"
  echo ""
  echo "To update the pin: echo '$CURRENT_SHA' > deerflow_config/HARNESS_VERSION"
  echo "To use the pinned version:  git -C ../deer-flow-reference checkout $PINNED_SHA"
  exit 1
fi

# ── 3. Copy harness into vendor/ ─────────────────────────────────────────────
echo "Vendoring DeerFlow harness @ $PINNED_SHA → $HARNESS_DST"
rm -rf "$HARNESS_DST"
cp -r "$HARNESS_SRC" "$HARNESS_DST"
echo "Done. Run 'docker build .' or 'uv pip install -e .' to use the vendored harness."
