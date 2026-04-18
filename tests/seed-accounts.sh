#!/bin/bash
# seed-accounts.sh — 创建固定测试账号
#
# 在 run-regression.sh 中调用，在 Docker 健康检查通过后执行。
# 幂等：账号已存在（409）时跳过，继续执行。
#
# 账号：
#   test_empty  / TestEmpty123!  — 空家庭（无资产）
#   test_rich   / TestRich123!   — 完整数据（资产+负债+心愿）
#   test_asset  / TestAsset123!  — 单个实物资产

set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost/api/v1}"
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_ok()   { echo -e "${GREEN}✓ $1${NC}" >&2; }
log_info() { echo -e "${YELLOW}ℹ $1${NC}" >&2; }
log_err()  { echo -e "${RED}✗ $1${NC}" >&2; }

# 注册账号，返回 access_token（已存在则登录）
register_or_login() {
  local username="$1"
  local password="$2"
  local display_name="$3"
  local family_name="$4"

  local resp
  resp=$(curl -sL -w "\n%{http_code}" -X POST "$BASE_URL/auth/register" \
    -H "Content-Type: application/json" \
    -d "{\"username\":\"$username\",\"display_name\":\"$display_name\",\"password\":\"$password\",\"family_name\":\"$family_name\"}")

  local http_code body
  http_code=$(echo "$resp" | tail -1)
  body=$(echo "$resp" | sed '$d')

  if [ "$http_code" = "200" ] || [ "$http_code" = "201" ]; then
    echo "$body" | jq -r '.access_token // .data.access_token'
    return 0
  elif [ "$http_code" = "409" ] || [ "$http_code" = "400" ]; then
    log_info "账号 $username 已存在 ($http_code)，直接登录"
    local login_resp
    login_resp=$(curl -sL -X POST "$BASE_URL/auth/login" \
      -H "Content-Type: application/json" \
      -d "{\"username\":\"$username\",\"password\":\"$password\"}")
    echo "$login_resp" | jq -r '.access_token // .data.access_token'
    return 0
  else
    log_err "注册 $username 失败: HTTP $http_code — $body"
    return 1
  fi
}

# 获取分类 ID
get_category_id() {
  local token="$1"
  local name="$2"
  local asset_type="$3"

  curl -sL "$BASE_URL/categories?asset_type=$asset_type" \
    -H "Authorization: Bearer $token" \
    | jq -r ".data[] | select(.name==\"$name\") | .id" | head -1
}

# 检查资产数量（避免重复创建）
get_asset_count() {
  local token="$1"
  local resp
  resp=$(curl -sL "$BASE_URL/assets" \
    -H "Authorization: Bearer $token")
  # 支持响应格式：数组 或 {total: N, items: [...]} 或 {items: [...]}
  echo "$resp" | jq -r 'if type == "array" then length elif (.data | type) == "array" then .data | length elif (.data.total | type) == "number" then .data.total elif (.data.items | type) == "array" then .data.items | length else 0 end' 2>/dev/null || echo "0"
}

echo ""
echo "=========================================="
echo "Numina 测试账号初始化"
echo "=========================================="

# ──────────────────────────────────────────────
# 1. test_empty — 空家庭
# ──────────────────────────────────────────────
log_info "初始化 test_empty..."
TOKEN_EMPTY=$(register_or_login "test_empty" "TestEmpty123!" "Empty Test User" "Empty Test Family")
if [ -z "$TOKEN_EMPTY" ] || [ "$TOKEN_EMPTY" = "null" ]; then
  log_err "test_empty 初始化失败"
  exit 1
fi
log_ok "test_empty 就绪（无资产）"

# ──────────────────────────────────────────────
# 2. test_asset — 单个实物资产
# ──────────────────────────────────────────────
log_info "初始化 test_asset..."
TOKEN_ASSET=$(register_or_login "test_asset" "TestAsset123!" "Asset Test User" "Asset Test Family")
if [ -z "$TOKEN_ASSET" ] || [ "$TOKEN_ASSET" = "null" ]; then
  log_err "test_asset 初始化失败"
  exit 1
fi

ASSET_COUNT=$(get_asset_count "$TOKEN_ASSET")
if [ "$ASSET_COUNT" = "0" ]; then
  CAT_HOUSE=$(get_category_id "$TOKEN_ASSET" "房产" "physical")
  if [ -z "$CAT_HOUSE" ] || [ "$CAT_HOUSE" = "null" ]; then
    log_err "找不到「房产」分类，请确认后端已初始化默认分类"
    exit 1
  fi

  curl -sL -X POST "$BASE_URL/assets" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN_ASSET" \
    -d "{
      \"name\":\"测试房产\",
      \"asset_type\":\"physical\",
      \"category_id\":\"$CAT_HOUSE\",
      \"purchase_price\":1000000,
      \"current_value\":1000000,
      \"currency\":\"CNY\",
      \"purchase_date\":\"2024-01-01\",
      \"status\":\"in_use\",
      \"location\":\"测试城市\",
      \"usage_frequency\":\"daily\",
      \"expected_lifespan_days\":36500,
      \"annual_maintenance_cost\":10000,
      \"notes\":\"E2E 测试用资产\"
    }" > /dev/null
  log_ok "test_asset 就绪（1 个实物资产）"
else
  log_info "test_asset 已有 $ASSET_COUNT 个资产，跳过创建"
  log_ok "test_asset 就绪"
fi

# ──────────────────────────────────────────────
# 3. test_rich — 完整数据
# ──────────────────────────────────────────────
log_info "初始化 test_rich..."
TOKEN_RICH=$(register_or_login "test_rich" "TestRich123!" "Rich Test User" "Rich Test Family")
if [ -z "$TOKEN_RICH" ] || [ "$TOKEN_RICH" = "null" ]; then
  log_err "test_rich 初始化失败"
  exit 1
fi

RICH_ASSET_COUNT=$(get_asset_count "$TOKEN_RICH")
RICH_LIABILITY_COUNT=$(curl -sL "$BASE_URL/liabilities" \
  -H "Authorization: Bearer $TOKEN_RICH" \
  | jq -r 'if type == "array" then length elif (.data | type) == "array" then .data | length elif (.data.total | type) == "number" then .data.total elif (.data.items | type) == "array" then .data.items | length else 0 end' 2>/dev/null || echo "0")

if [ "$RICH_ASSET_COUNT" != "0" ] && [ "$RICH_LIABILITY_COUNT" != "0" ]; then
  log_info "test_rich 已有 $RICH_ASSET_COUNT 个资产 + $RICH_LIABILITY_COUNT 个负债，跳过种子数据"
  log_ok "test_rich 就绪"
else
  log_info "为 test_rich 创建种子数据..."

  # 获取分类 ID
  CAT_HOUSE_R=$(get_category_id "$TOKEN_RICH" "房产" "physical")
  CAT_CAR_R=$(get_category_id "$TOKEN_RICH" "车辆" "physical")
  CAT_ELEC_R=$(get_category_id "$TOKEN_RICH" "电子设备" "physical")
  CAT_STOCK_R=$(get_category_id "$TOKEN_RICH" "股票" "financial")
  CAT_FUND_R=$(get_category_id "$TOKEN_RICH" "基金" "financial")
  CAT_DEPOSIT_R=$(get_category_id "$TOKEN_RICH" "存款" "financial")

  create_asset() {
    curl -sL -X POST "$BASE_URL/assets" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer $TOKEN_RICH" \
      -d "$1" > /dev/null
  }

  create_liability() {
    curl -sL -X POST "$BASE_URL/liabilities" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer $TOKEN_RICH" \
      -d "$1" > /dev/null
  }

  create_wish() {
    curl -sL -X POST "$BASE_URL/wishes" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer $TOKEN_RICH" \
      -d "$1" > /dev/null
  }

  # 实物资产（3 个）
  create_asset "{\"name\":\"测试房产\",\"asset_type\":\"physical\",\"category_id\":\"$CAT_HOUSE_R\",\"purchase_price\":5000000,\"current_value\":5500000,\"currency\":\"CNY\",\"purchase_date\":\"2020-01-01\",\"status\":\"in_use\",\"location\":\"测试城市\",\"usage_frequency\":\"daily\",\"expected_lifespan_days\":36500,\"annual_maintenance_cost\":30000}"
  create_asset "{\"name\":\"测试车辆\",\"asset_type\":\"physical\",\"category_id\":\"$CAT_CAR_R\",\"purchase_price\":300000,\"current_value\":250000,\"currency\":\"CNY\",\"purchase_date\":\"2022-06-01\",\"status\":\"in_use\",\"location\":\"测试城市\",\"usage_frequency\":\"daily\",\"expected_lifespan_days\":3650,\"annual_maintenance_cost\":15000}"
  create_asset "{\"name\":\"测试电脑\",\"asset_type\":\"physical\",\"category_id\":\"$CAT_ELEC_R\",\"purchase_price\":15000,\"current_value\":10000,\"currency\":\"CNY\",\"purchase_date\":\"2023-01-01\",\"status\":\"in_use\",\"location\":\"家\",\"usage_frequency\":\"daily\",\"expected_lifespan_days\":1825,\"annual_maintenance_cost\":500}"

  # 金融资产（3 个）
  create_asset "{\"name\":\"测试股票\",\"asset_type\":\"financial\",\"category_id\":\"$CAT_STOCK_R\",\"purchase_price\":100000,\"current_value\":120000,\"currency\":\"CNY\",\"purchase_date\":\"2023-01-01\",\"institution\":\"测试券商\",\"notes\":\"测试股票持仓\"}"
  create_asset "{\"name\":\"测试基金\",\"asset_type\":\"financial\",\"category_id\":\"$CAT_FUND_R\",\"purchase_price\":50000,\"current_value\":55000,\"currency\":\"CNY\",\"purchase_date\":\"2023-06-01\",\"institution\":\"测试基金公司\"}"
  create_asset "{\"name\":\"测试存款\",\"asset_type\":\"financial\",\"category_id\":\"$CAT_DEPOSIT_R\",\"purchase_price\":200000,\"current_value\":200000,\"currency\":\"CNY\",\"purchase_date\":\"2024-01-01\",\"institution\":\"测试银行\"}"

  # 负债（2 个）
  create_liability "{\"name\":\"测试房贷\",\"category\":\"mortgage\",\"original_amount\":3000000,\"remaining_amount\":2800000,\"currency\":\"CNY\",\"interest_rate\":4.2,\"monthly_payment\":15000,\"start_date\":\"2020-01-01\",\"end_date\":\"2050-01-01\",\"institution\":\"测试银行\"}"
  create_liability "{\"name\":\"测试车贷\",\"category\":\"car_loan\",\"original_amount\":200000,\"remaining_amount\":100000,\"currency\":\"CNY\",\"interest_rate\":5.0,\"monthly_payment\":4000,\"start_date\":\"2022-06-01\",\"end_date\":\"2026-06-01\",\"institution\":\"测试银行\"}"

  # 心愿（2 个）
  create_wish "{\"name\":\"测试心愿1\",\"target_amount\":50000,\"currency\":\"CNY\",\"priority\":\"high\",\"description\":\"E2E 测试心愿\"}"
  create_wish "{\"name\":\"测试心愿2\",\"target_amount\":10000,\"currency\":\"CNY\",\"priority\":\"medium\",\"description\":\"E2E 测试心愿2\"}"

  log_ok "test_rich 就绪（6 资产 + 2 负债 + 2 心愿）"
fi

# ──────────────────────────────────────────────
# 4. test_child — test_rich 家庭的儿童账号
# ──────────────────────────────────────────────
log_info "初始化 test_child（test_rich 家庭的儿童账号）..."

# 检查是否已有名为 test_child 的儿童
CHILDREN_RESP=$(curl -sL "$BASE_URL/family/children" \
  -H "Authorization: Bearer $TOKEN_RICH")
CHILD_ID=$(echo "$CHILDREN_RESP" | jq -r '.data[] | select(.display_name=="test_child") | .id' 2>/dev/null | head -1)

if [ -z "$CHILD_ID" ] || [ "$CHILD_ID" = "null" ]; then
  log_info "创建 test_child..."
  CREATE_CHILD_RESP=$(curl -sL -w "\n%{http_code}" -X POST "$BASE_URL/family/children" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN_RICH" \
    -d '{"display_name":"test_child","avatar_color":"#FF6B6B","pin":["🐱","🐶","🐸","🦊"]}')
  CHILD_HTTP=$(echo "$CREATE_CHILD_RESP" | tail -1)
  CHILD_BODY=$(echo "$CREATE_CHILD_RESP" | sed '$d')
  if [ "$CHILD_HTTP" = "200" ] || [ "$CHILD_HTTP" = "201" ]; then
    CHILD_ID=$(echo "$CHILD_BODY" | jq -r '.id // .data.id')
    log_ok "test_child 创建成功（id: $CHILD_ID）"
  else
    log_err "创建 test_child 失败: HTTP $CHILD_HTTP — $CHILD_BODY"
    exit 1
  fi
else
  log_info "test_child 已存在，跳过（id: $CHILD_ID）"
fi
log_ok "test_child 就绪"

# ──────────────────────────────────────────────
# 5. 家务模板 — test_rich 家庭的测试家务
# ──────────────────────────────────────────────
log_info "初始化「测试家务」模板..."

TEMPLATES_RESP=$(curl -sL "$BASE_URL/family/chore-templates" \
  -H "Authorization: Bearer $TOKEN_RICH")
TEMPLATE_ID=$(echo "$TEMPLATES_RESP" | jq -r '.data[] | select(.name=="测试家务") | .id' 2>/dev/null | head -1)

if [ -z "$TEMPLATE_ID" ] || [ "$TEMPLATE_ID" = "null" ]; then
  log_info "创建「测试家务」模板..."
  CREATE_TPL_RESP=$(curl -sL -w "\n%{http_code}" -X POST "$BASE_URL/family/chore-templates" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN_RICH" \
    -d '{"name":"测试家务","emoji":"🧹","coin_reward":10,"frequency":"daily","assignment_type":"pool"}')
  TPL_HTTP=$(echo "$CREATE_TPL_RESP" | tail -1)
  TPL_BODY=$(echo "$CREATE_TPL_RESP" | sed '$d')
  if [ "$TPL_HTTP" = "200" ] || [ "$TPL_HTTP" = "201" ]; then
    TEMPLATE_ID=$(echo "$TPL_BODY" | jq -r '.id // .data.id')
    log_ok "「测试家务」模板创建成功（id: $TEMPLATE_ID）"
  else
    log_err "创建「测试家务」模板失败: HTTP $TPL_HTTP — $TPL_BODY"
    exit 1
  fi
else
  log_info "「测试家务」模板已存在，跳过（id: $TEMPLATE_ID）"
fi
log_ok "「测试家务」模板就绪"

echo ""
echo "=========================================="
echo "测试账号初始化完成"
echo "=========================================="
