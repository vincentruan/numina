#!/usr/bin/env bash
# scripts/deploy-docker.sh
# Numina Docker 快速部署脚本
#
# 用法：
#   ./scripts/deploy-docker.sh [--skip-clone] [--dev]
#
# 参数：
#   --skip-clone  跳过 deer-flow 克隆（如果已存在）
#   --dev         使用开发环境模式（放宽部分安全检查）

set -euo pipefail

# ========================================
# 颜色输出
# ========================================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

info() { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# ========================================
# 参数解析
# ========================================
SKIP_CLONE=false
DEV_MODE=false

while [[ $# -gt 0 ]]; do
  case $1 in
    --skip-clone) SKIP_CLONE=true; shift ;;
    --dev) DEV_MODE=true; shift ;;
    *) error "未知参数: $1" ;;
  esac
done

# ========================================
# 1. 环境依赖检查
# ========================================
info "检查环境依赖..."

# Docker
if ! command -v docker &> /dev/null; then
  error "Docker 未安装！请先安装 Docker: https://docs.docker.com/get-docker/"
fi
DOCKER_VERSION=$(docker --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
success "Docker 已安装 (版本 $DOCKER_VERSION)"

# Docker Compose
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
  error "Docker Compose 未安装！请先安装 Docker Compose"
fi
if command -v docker-compose &> /dev/null; then
  COMPOSE_CMD="docker-compose"
  COMPOSE_VERSION=$(docker-compose --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
else
  COMPOSE_CMD="docker compose"
  COMPOSE_VERSION=$(docker compose version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
fi
success "Docker Compose 已安装 (版本 $COMPOSE_VERSION)"

# OpenSSL (用于生成密钥)
if ! command -v openssl &> /dev/null; then
  error "OpenSSL 未安装！请先安装 OpenSSL"
fi
success "OpenSSL 已安装"

# Python3 (用于生成 Fernet key)
if ! command -v python3 &> /dev/null; then
  error "Python3 未安装！请先安装 Python3"
fi
success "Python3 已安装"

# cryptography 库 (用于生成 Fernet key)
if ! python3 -c "from cryptography.fernet import Fernet" 2>/dev/null; then
  warn "cryptography 库未安装，尝试安装..."
  pip3 install cryptography --quiet || error "安装 cryptography 失败"
fi
success "cryptography 库可用"

# Git
if ! command -v git &> /dev/null; then
  error "Git 未安装！请先安装 Git"
fi
success "Git 已安装"

# ========================================
# 2. 工作目录设置
# ========================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

info "工作目录: $PROJECT_ROOT"

# ========================================
# 3. DeerFlow harness 准备
# ========================================
DEERFLOW_REF_PATH="${PROJECT_ROOT}/../deer-flow-reference"
HARNESS_DST="$PROJECT_ROOT/agent/vendor/deerflow-harness"

if [[ "$SKIP_CLONE" == true ]]; then
  info "跳过 deer-flow 克隆 (--skip-clone)"
else
  if [[ ! -d "$DEERFLOW_REF_PATH" ]]; then
    info "克隆 DeerFlow 仓库..."
    git clone --depth 1 https://github.com/bytedance/deer-flow.git "$DEERFLOW_REF_PATH"
    success "DeerFlow 仓库已克隆到: $DEERFLOW_REF_PATH"
  else
    info "DeerFlow 仓库已存在: $DEERFLOW_REF_PATH"
  fi
fi

# Vendor harness
if [[ ! -d "$HARNESS_DST" ]]; then
  info "复制 DeerFlow harness 到 vendor 目录..."

  if [[ ! -d "$DEERFLOW_REF_PATH/backend/packages/harness" ]]; then
    error "Harness 目录不存在: $DEERFLOW_REF_PATH/backend/packages/harness"
  fi

  rm -rf "$HARNESS_DST"
  cp -r "$DEERFLOW_REF_PATH/backend/packages/harness" "$HARNESS_DST"

  # 写入 manifest
  COMMIT_SHA=$(git -C "$DEERFLOW_REF_PATH" rev-parse HEAD 2>/dev/null || echo "unknown")
  cat > "$HARNESS_DST/.vendor-manifest.json" <<EOF
{
  "source": "https://github.com/bytedance/deer-flow",
  "commit": "$COMMIT_SHA",
  "vendored_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "harness_path": "backend/packages/harness"
}
EOF

  success "Harness 已复制到: $HARNESS_DST"
else
  info "Harness 已存在: $HARNESS_DST"
fi

# ========================================
# 4. .env 文件配置
# ========================================
ENV_FILE="$PROJECT_ROOT/.env"

generate_hex_key() {
  openssl rand -hex 32
}

generate_fernet_key() {
  python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
}

info "配置环境变量..."

if [[ ! -f "$ENV_FILE" ]]; then
  info "创建 .env 文件..."

  # 生成所有密钥
  SECRET_KEY=$(generate_hex_key)
  ALTCHA_HMAC_KEY=$(generate_hex_key)
  AI_ENCRYPTION_KEY=$(generate_hex_key)
  AGENT_INTERNAL_TOKEN=$(generate_hex_key)
  STORAGE_ENCRYPTION_KEY=$(generate_fernet_key)

  # 设置环境模式
  if [[ "$DEV_MODE" == true ]]; then
    ENVIRONMENT="development"
  else
    ENVIRONMENT="production"
  fi

  cat > "$ENV_FILE" <<EOF
# Numina Environment Configuration
# 自动生成于 $(date -u +%Y-%m-%dT%H:%M:%SZ)

# JWT Secret Key
SECRET_KEY=${SECRET_KEY}

# Database URL (default: SQLite)
DATABASE_URL=sqlite:////app/data/numina.db

# Environment mode
ENVIRONMENT=${ENVIRONMENT}

# CORS Origins (JSON array format)
CORS_ORIGINS=["http://localhost:80","http://localhost:28080"]

# JWT Token Expiration
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# Altcha HMAC Key (for CAPTCHA)
ALTCHA_HMAC_KEY=${ALTCHA_HMAC_KEY}

# Agent Configuration
AI_ENCRYPTION_KEY=${AI_ENCRYPTION_KEY}
AGENT_INTERNAL_TOKEN=${AGENT_INTERNAL_TOKEN}

# Storage Encryption Key (Fernet format)
STORAGE_ENCRYPTION_KEY=${STORAGE_ENCRYPTION_KEY}

# Optional: MySQL/PostgreSQL credentials
MYSQL_ROOT_PASSWORD=rootpass
MYSQL_DATABASE=numina
MYSQL_USER=numina
MYSQL_PASSWORD=numinapass
POSTGRES_DB=numina
POSTGRES_USER=numina
POSTGRES_PASSWORD=numinapass
EOF

  success ".env 文件已创建"
else
  info ".env 文件已存在，检查必要配置..."

  # 检查并补充缺失的必要配置
  NEED_UPDATE=false

  # 检查 SECRET_KEY
  if ! grep -q "^SECRET_KEY=." "$ENV_FILE" || grep -q "^SECRET_KEY=your-secret-key" "$ENV_FILE"; then
    warn "SECRET_KEY 需要配置"
    SECRET_KEY=$(generate_hex_key)
    if grep -q "^SECRET_KEY=" "$ENV_FILE"; then
      sed -i.bak "s/^SECRET_KEY=.*/SECRET_KEY=${SECRET_KEY}/" "$ENV_FILE"
    else
      echo "SECRET_KEY=${SECRET_KEY}" >> "$ENV_FILE"
    fi
    NEED_UPDATE=true
  fi

  # 检查 ALTCHA_HMAC_KEY
  if ! grep -q "^ALTCHA_HMAC_KEY=." "$ENV_FILE" || grep -q "^ALTCHA_HMAC_KEY=$" "$ENV_FILE"; then
    warn "ALTCHA_HMAC_KEY 需要配置"
    ALTCHA_HMAC_KEY=$(generate_hex_key)
    if grep -q "^ALTCHA_HMAC_KEY=" "$ENV_FILE"; then
      sed -i.bak "s/^ALTCHA_HMAC_KEY=.*/ALTCHA_HMAC_KEY=${ALTCHA_HMAC_KEY}/" "$ENV_FILE"
    else
      echo "ALTCHA_HMAC_KEY=${ALTCHA_HMAC_KEY}" >> "$ENV_FILE"
    fi
    NEED_UPDATE=true
  fi

  # 检查 AI_ENCRYPTION_KEY
  if ! grep -q "^AI_ENCRYPTION_KEY=." "$ENV_FILE" || grep -q "^AI_ENCRYPTION_KEY=$" "$ENV_FILE"; then
    warn "AI_ENCRYPTION_KEY 需要配置"
    AI_ENCRYPTION_KEY=$(generate_hex_key)
    if grep -q "^AI_ENCRYPTION_KEY=" "$ENV_FILE"; then
      sed -i.bak "s/^AI_ENCRYPTION_KEY=.*/AI_ENCRYPTION_KEY=${AI_ENCRYPTION_KEY}/" "$ENV_FILE"
    else
      echo "AI_ENCRYPTION_KEY=${AI_ENCRYPTION_KEY}" >> "$ENV_FILE"
    fi
    NEED_UPDATE=true
  fi

  # 检查 AGENT_INTERNAL_TOKEN
  if ! grep -q "^AGENT_INTERNAL_TOKEN=." "$ENV_FILE" || grep -q "^AGENT_INTERNAL_TOKEN=$" "$ENV_FILE"; then
    warn "AGENT_INTERNAL_TOKEN 需要配置"
    AGENT_INTERNAL_TOKEN=$(generate_hex_key)
    if grep -q "^AGENT_INTERNAL_TOKEN=" "$ENV_FILE"; then
      sed -i.bak "s/^AGENT_INTERNAL_TOKEN=.*/AGENT_INTERNAL_TOKEN=${AGENT_INTERNAL_TOKEN}/" "$ENV_FILE"
    else
      echo "AGENT_INTERNAL_TOKEN=${AGENT_INTERNAL_TOKEN}" >> "$ENV_FILE"
    fi
    NEED_UPDATE=true
  fi

  # 检查 STORAGE_ENCRYPTION_KEY
  if ! grep -q "^STORAGE_ENCRYPTION_KEY=." "$ENV_FILE" || grep -q "^STORAGE_ENCRYPTION_KEY=$" "$ENV_FILE"; then
    warn "STORAGE_ENCRYPTION_KEY 需要配置"
    STORAGE_ENCRYPTION_KEY=$(generate_fernet_key)
    if grep -q "^STORAGE_ENCRYPTION_KEY=" "$ENV_FILE"; then
      sed -i.bak "s/^STORAGE_ENCRYPTION_KEY=.*/STORAGE_ENCRYPTION_KEY=${STORAGE_ENCRYPTION_KEY}/" "$ENV_FILE"
    else
      echo "STORAGE_ENCRYPTION_KEY=${STORAGE_ENCRYPTION_KEY}" >> "$ENV_FILE"
    fi
    NEED_UPDATE=true
  fi

  if [[ "$NEED_UPDATE" == true ]]; then
    success ".env 文件已更新"
  else
    success ".env 配置完整"
  fi
fi

# ========================================
# 5. 数据目录准备
# ========================================
DATA_DIR="$PROJECT_ROOT/data"
if [[ ! -d "$DATA_DIR" ]]; then
  info "创建数据目录..."
  mkdir -p "$DATA_DIR"
  success "数据目录已创建: $DATA_DIR"
fi

# ========================================
# 6. Docker 服务部署
# ========================================
info "停止现有容器..."
$COMPOSE_CMD down --remove-orphans 2>/dev/null || true

info "构建并启动 Docker 服务..."
$COMPOSE_CMD up -d --build

# ========================================
# 7. 健康检查
# ========================================
info "等待服务启动..."
sleep 10

# 等待 backend healthy
MAX_WAIT=60
WAIT_COUNT=0
while [[ $WAIT_COUNT -lt $MAX_WAIT ]]; do
  if $COMPOSE_CMD ps backend | grep -q "healthy"; then
    break
  fi
  WAIT_COUNT=$((WAIT_COUNT + 1))
  sleep 2
done

if [[ $WAIT_COUNT -ge $MAX_WAIT ]]; then
  error "Backend 服务启动超时"
fi

# 等待 agent healthy
WAIT_COUNT=0
while [[ $WAIT_COUNT -lt $MAX_WAIT ]]; do
  if $COMPOSE_CMD ps agent | grep -q "healthy"; then
    break
  fi
  WAIT_COUNT=$((WAIT_COUNT + 1))
  sleep 2
done

if [[ $WAIT_COUNT -ge $MAX_WAIT ]]; then
  error "Agent 服务启动超时"
fi

success "所有服务已健康启动"

# ========================================
# 8. 检查数据库迁移日志
# ========================================
info "检查数据库迁移状态..."

# 查看 backend 启动日志中的迁移信息
MIGRATION_LOG=$($COMPOSE_CMD logs backend 2>&1 | grep -E "数据库结构|新建表|新增字段|新增索引|迁移错误" | tail -10)

if [[ -n "$MIGRATION_LOG" ]]; then
  echo "$MIGRATION_LOG"
else
  success "数据库结构已完整（无迁移日志表示无需迁移）"
fi

# ========================================
# 9. 验证部署
# ========================================
info "验证部署..."

# 检查 API health
API_HEALTH=$(curl -s http://localhost:80/api/health)
if [[ "$API_HEALTH" == '{"status":"ok"}' ]]; then
  success "API 健康检查通过"
else
  error "API 健康检查失败: $API_HEALTH"
fi

# ========================================
# 10. 显示服务状态
# ========================================
echo ""
echo "========================================"
echo "       Numina 部署完成"
echo "========================================"
echo ""
$COMPOSE_CMD ps
echo ""
echo "访问地址:"
echo "  - 主入口:     http://localhost:80"
echo "  - 前端直连:   http://localhost:28080"
echo ""
echo "数据目录: $DATA_DIR"
echo "配置文件: $ENV_FILE"
echo ""
echo "管理命令:"
echo "  - 查看日志:   $COMPOSE_CMD logs -f"
echo "  - 停止服务:   $COMPOSE_CMD down"
echo "  - 重启服务:   $COMPOSE_CMD restart"
echo ""