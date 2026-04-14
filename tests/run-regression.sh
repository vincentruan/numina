#!/bin/bash
# run-regression.sh — 一键回归测试
#
# 用法：
#   ./tests/run-regression.sh           # 完整运行（测试后自动清理）
#   ./tests/run-regression.sh --keep-up # 测试后保留 Docker 环境（用于调试）
#
# 依赖：docker, docker compose, curl, jq, node/npm

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
KEEP_UP=false
START_TIME=$(date +%s)

# ── 参数解析 ──────────────────────────────────────────────
for arg in "$@"; do
  case "$arg" in
    --keep-up) KEEP_UP=true ;;
    *) echo "未知参数: $arg" >&2; exit 1 ;;
  esac
done

# ── 颜色输出 ──────────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

log_ok()   { echo -e "${GREEN}✓ $1${NC}"; }
log_info() { echo -e "${YELLOW}ℹ $1${NC}"; }
log_err()  { echo -e "${RED}✗ $1${NC}" >&2; }
log_bold() { echo -e "${BOLD}$1${NC}"; }

# ── 清理 trap ─────────────────────────────────────────────
cleanup() {
  local exit_code=$?
  if [ "$KEEP_UP" = "false" ]; then
    log_info "清理 Docker 环境..."
    cd "$REPO_ROOT"
    docker compose down -v 2>/dev/null || true
    log_ok "Docker 环境已清理"
  else
    log_info "--keep-up: Docker 环境保留，可手动运行 'docker compose down -v' 清理"
  fi
  exit $exit_code
}
trap cleanup EXIT

# ── 主流程 ────────────────────────────────────────────────
echo ""
log_bold "=========================================="
log_bold "Numina 回归测试"
log_bold "=========================================="
echo ""

cd "$REPO_ROOT"

# 1. 启动 Docker 服务
log_info "启动 Docker 服务..."
docker compose up -d
log_ok "Docker 服务已启动"

# 2. 等待后端健康检查
log_info "等待后端就绪（最多 90 秒）..."
BACKEND_READY=false
for i in $(seq 1 45); do
  if curl -sf "http://localhost/api/health" > /dev/null 2>&1; then
    BACKEND_READY=true
    break
  fi
  sleep 2
done

if [ "$BACKEND_READY" = "false" ]; then
  log_err "后端在 90 秒内未就绪"
  exit 1
fi
log_ok "后端就绪"

# 3. 等待 agent 健康检查（可选，404 则跳过）
log_info "检查 agent 服务..."
AGENT_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:8001/health" 2>/dev/null || echo "000")
if [ "$AGENT_STATUS" = "200" ]; then
  log_ok "agent 就绪"
elif [ "$AGENT_STATUS" = "404" ]; then
  log_info "agent /health 端点不存在，跳过检查"
else
  log_info "等待 agent 就绪（最多 60 秒）..."
  AGENT_READY=false
  for i in $(seq 1 30); do
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:8001/health" 2>/dev/null || echo "000")
    if [ "$STATUS" = "200" ]; then
      AGENT_READY=true
      break
    fi
    sleep 2
  done
  if [ "$AGENT_READY" = "true" ]; then
    log_ok "agent 就绪"
  else
    log_info "agent 未响应，继续执行（非关键依赖）"
  fi
fi

# 4. 初始化测试账号
log_info "初始化测试账号..."
bash "$SCRIPT_DIR/seed-accounts.sh"

# 5. 安装 Playwright 依赖
log_info "安装测试依赖..."
cd "$SCRIPT_DIR"
npm ci --silent
log_ok "依赖安装完成"

# 6. 运行 Playwright 测试
echo ""
log_bold "── 运行 Playwright 测试 ──────────────────"
echo ""
TEST_EXIT=0
npx playwright test || TEST_EXIT=$?

# 7. 输出结果
END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))
echo ""
log_bold "=========================================="
if [ $TEST_EXIT -eq 0 ]; then
  echo -e "${GREEN}${BOLD}PASSED${NC} (${ELAPSED}s)"
else
  echo -e "${RED}${BOLD}FAILED${NC} (${ELAPSED}s)"
fi
log_bold "=========================================="
echo ""

exit $TEST_EXIT
