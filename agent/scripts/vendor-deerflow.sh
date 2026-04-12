#!/usr/bin/env bash
# scripts/vendor-deerflow.sh
# 将 DeerFlow harness 包从参考仓库复制到 agent/vendor/deerflow-harness/
# 在 Docker 构建前或本地开发时运行。
#
# 用法：
#   ./scripts/vendor-deerflow.sh [DEERFLOW_REF_PATH]
#
# 默认参考路径：../deer-flow-reference
# 可通过环境变量 DEERFLOW_REF_PATH 覆盖。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REF_PATH="${DEERFLOW_REF_PATH:-$(cd "$AGENT_DIR/../deer-flow-reference" 2>/dev/null && pwd || echo "")}"

if [ -z "$REF_PATH" ] || [ ! -d "$REF_PATH" ]; then
  echo "ERROR: DeerFlow reference repo not found at '$REF_PATH'"
  echo "  Clone it first: git clone https://github.com/bytedance/deer-flow.git ../deer-flow-reference"
  echo "  Or set DEERFLOW_REF_PATH=/path/to/deer-flow"
  exit 1
fi

HARNESS_SRC="$REF_PATH/backend/packages/harness"
HARNESS_DST="$AGENT_DIR/vendor/deerflow-harness"

if [ ! -d "$HARNESS_SRC" ]; then
  echo "ERROR: Harness package not found at '$HARNESS_SRC'"
  exit 1
fi

echo "Vendoring DeerFlow harness..."
echo "  Source: $HARNESS_SRC"
echo "  Dest:   $HARNESS_DST"

# Record the commit SHA being vendored
COMMIT_SHA=$(cd "$REF_PATH" && git rev-parse HEAD)
echo "  Commit: $COMMIT_SHA"

# Clean and copy
rm -rf "$HARNESS_DST"
cp -r "$HARNESS_SRC" "$HARNESS_DST"

# Write a manifest so the Dockerfile and CI can verify the pinned SHA
cat > "$HARNESS_DST/.vendor-manifest.json" <<EOF
{
  "source": "https://github.com/bytedance/deer-flow",
  "commit": "$COMMIT_SHA",
  "vendored_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "harness_path": "backend/packages/harness"
}
EOF

echo "Done. Harness vendored at $HARNESS_DST (commit $COMMIT_SHA)"
echo ""
echo "Next steps:"
echo "  1. uv add --editable ./vendor/deerflow-harness"
echo "  2. Apply langgraph runtime compatibility patch:"
echo "     uv run python scripts/patch-langgraph-runtime.py"
