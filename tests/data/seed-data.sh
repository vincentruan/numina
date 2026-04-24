#!/bin/bash
# seed-data.sh — 统一测试数据生成脚本
#
# 合并了 seed-accounts.sh 和原有 seed-data.sh
# 包含：
#   1. 固定测试账号（用于回归测试）
#      - test_empty / TestEmpty123! — 空家庭（无资产）
#      - test_asset  / TestAsset123!  — 单个实物资产
#      - test_rich   / TestRich123!   — 完整数据（资产+负债+心愿+儿童）
#      - test_child  — test_rich 家庭的儿童账号
#   2. 完整仿真数据（用于功能演示）
#      - demouser / DemoPass123 — 19项实物资产 + 11项金融资产 + 负债 + 心愿 + 儿童数据
#
# 用法：
#   ./tests/data/seed-data.sh [--skip-demo]
#
# 参数：
#   --skip-demo  跳过 demouser 完整数据生成（仅创建固定测试账号）
#
# 幂等性：
#   账号已存在（409）时自动登录
#   资产数量已达标时跳过创建

set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost/api/v1}"
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

log_ok()   { echo -e "${GREEN}✓ $1${NC}" >&2; }
log_info() { echo -e "${BLUE}ℹ $1${NC}" >&2; }
log_warn() { echo -e "${YELLOW}⚠ $1${NC}" >&2; }
log_err()  { echo -e "${RED}✗ $1${NC}" >&2; }

# ========================================
# 参数解析
# ========================================
SKIP_DEMO=false
INVITE_CODES=()

while [[ $# -gt 0 ]]; do
  case $1 in
    --skip-demo) SKIP_DEMO=true; shift ;;
    --invite-codes) IFS=',' read -ra INVITE_CODES <<< "$2"; shift 2 ;;
    *) log_err "未知参数: $1"; exit 1 ;;
  esac
done

# If FAMILY_INVITATION_CODES env var is set (comma-separated), use it
if [[ ${#INVITE_CODES[@]} -eq 0 ]] && [[ -n "${FAMILY_INVITATION_CODES:-}" ]]; then
  IFS=',' read -ra INVITE_CODES <<< "$FAMILY_INVITATION_CODES"
fi

_INVITE_INDEX=0
next_invite_code() {
  if [[ ${#INVITE_CODES[@]} -gt 0 ]]; then
    echo "${INVITE_CODES[$_INVITE_INDEX]:-}"
    _INVITE_INDEX=$(( _INVITE_INDEX + 1 ))
  else
    echo "${FAMILY_INVITATION_CODE:-}"
  fi
}

# ========================================
# 通用函数
# ========================================

# 注册账号，返回 access_token（已存在则登录）
register_or_login() {
  local username="$1"
  local password="$2"
  local display_name="$3"
  local family_name="$4"

  # Try login first — only consume an invite code if we need to register
  local login_resp
  login_resp=$(curl -sL -X POST "$BASE_URL/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"username\":\"$username\",\"password\":\"$password\"}")
  local login_token
  login_token=$(echo "$login_resp" | jq -r '.access_token // .data.access_token')
  if [ -n "$login_token" ] && [ "$login_token" != "null" ]; then
    log_info "账号 $username 已存在，直接登录"
    echo "$login_token"
    return 0
  fi

  # User doesn't exist — register with a fresh invite code
  local invite_code="${5:-$(next_invite_code)}"
  local resp
  resp=$(curl -sL -w "\n%{http_code}" -X POST "$BASE_URL/auth/register" \
    -H "Content-Type: application/json" \
    -d "{\"username\":\"$username\",\"display_name\":\"$display_name\",\"password\":\"$password\",\"family_name\":\"$family_name\",\"family_invitation_code\":\"$invite_code\"}")

  local http_code body
  http_code=$(echo "$resp" | tail -1)
  body=$(echo "$resp" | sed '$d')

  if [ "$http_code" = "200" ] || [ "$http_code" = "201" ]; then
    echo "$body" | jq -r '.access_token // .data.access_token'
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
  echo "$resp" | jq -r 'if type == "array" then length elif (.data | type) == "array" then .data | length elif (.data.total | type) == "number" then .data.total elif (.data.items | type) == "array" then .data.items | length else 0 end' 2>/dev/null || echo "0"
}

# 创建实物资产
create_physical_asset() {
  local token="$1"
  local data="$2"
  curl -sL -X POST "$BASE_URL/assets" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $token" \
    -d "$data" > /dev/null
}

# 创建金融资产
create_financial_asset() {
  local token="$1"
  local data="$2"
  curl -sL -X POST "$BASE_URL/assets" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $token" \
    -d "$data" > /dev/null
}

# 创建负债
create_liability() {
  local token="$1"
  local data="$2"
  curl -sL -X POST "$BASE_URL/liabilities" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $token" \
    -d "$data" > /dev/null
}

# 创建心愿
create_wish() {
  local token="$1"
  local data="$2"
  curl -sL -X POST "$BASE_URL/wishes" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $token" \
    -d "$data" > /dev/null
}

echo ""
echo "=========================================="
echo "  Numina 统一测试数据生成"
echo "=========================================="

# ========================================
# Part 1: 固定测试账号（用于回归测试）
# ========================================
log_info "========== Part 1: 固定测试账号 =========="

# ──────────────────────────────────────────────
# 1.1 test_empty — 空家庭
# ──────────────────────────────────────────────
log_info "初始化 test_empty..."
TOKEN_EMPTY=$(register_or_login "test_empty" "TestEmpty123!" "Empty Test User" "Empty Test Family")
if [ -z "$TOKEN_EMPTY" ] || [ "$TOKEN_EMPTY" = "null" ]; then
  log_err "test_empty 初始化失败"
  exit 1
fi
log_ok "test_empty 就绪（无资产）"

# ──────────────────────────────────────────────
# 1.2 test_asset — 单个实物资产 + 多状态资产
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
  CAT_CAR=$(get_category_id "$TOKEN_ASSET" "车辆" "physical")
  CAT_DIGITAL=$(get_category_id "$TOKEN_ASSET" "数码" "physical")
  CAT_CLOTHING=$(get_category_id "$TOKEN_ASSET" "服饰" "physical")
  if [ -z "$CAT_HOUSE" ] || [ "$CAT_HOUSE" = "null" ]; then
    log_err "找不到「房产」分类，请确认后端已初始化默认分类"
    exit 1
  fi

  # 1. 主资产 - in_use 状态
  create_physical_asset "$TOKEN_ASSET" "$(cat <<EOF
{
  "name":"测试房产",
  "asset_type":"physical",
  "category_id":"$CAT_HOUSE",
  "purchase_price":1000000,
  "current_value":1000000,
  "currency":"CNY",
  "purchase_date":"2024-01-01",
  "status":"in_use",
  "location":"测试城市",
  "usage_frequency":"daily",
  "expected_lifespan_days":36500,
  "annual_maintenance_cost":10000,
  "notes":"E2E 测试用资产",
  "properties":"{\"rooms\":3,\"area\":120}"
}
EOF
)"

  # 2. idle 状态资产（闲置）
  create_physical_asset "$TOKEN_ASSET" "$(cat <<EOF
{
  "name":"闲置车辆",
  "asset_type":"physical",
  "category_id":"$CAT_CAR",
  "purchase_price":200000,
  "current_value":150000,
  "currency":"CNY",
  "purchase_date":"2023-01-01",
  "status":"idle",
  "location":"车库",
  "usage_frequency":"rarely",
  "expected_lifespan_days":3650,
  "notes":"闲置状态测试资产"
}
EOF
)"

  # 3. 已归档资产
  create_physical_asset "$TOKEN_ASSET" "$(cat <<EOF
{
  "name":"旧电脑",
  "asset_type":"physical",
  "category_id":"$CAT_DIGITAL",
  "purchase_price":5000,
  "current_value":0,
  "currency":"CNY",
  "purchase_date":"2020-01-01",
  "status":"retired",
  "location":"储藏室",
  "usage_frequency":"idle",
  "expected_lifespan_days":1825,
  "notes":"已归档资产测试"
}
EOF
)"

  # 4. 多货币资产（USD）
  create_physical_asset "$TOKEN_ASSET" "$(cat <<EOF
{
  "name":"海外房产",
  "asset_type":"physical",
  "category_id":"$CAT_HOUSE",
  "purchase_price":500000,
  "current_value":550000,
  "currency":"USD",
  "purchase_date":"2022-06-01",
  "status":"in_use",
  "location":"美国加州",
  "notes":"多货币测试资产"
}
EOF
)"

  # 5. 已售出资产（通过 API 更新状态）
  SOLD_ASSET_RESP=$(curl -sL -X POST "$BASE_URL/assets" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN_ASSET" \
    -d "{\"name\":\"已售西装\",\"asset_type\":\"physical\",\"category_id\":\"$CAT_CLOTHING\",\"purchase_price\":3000,\"current_value\":0,\"currency\":\"CNY\",\"purchase_date\":\"2023-01-01\",\"status\":\"in_use\",\"notes\":\"待售出\"}")
  SOLD_ASSET_ID=$(echo "$SOLD_ASSET_RESP" | jq -r '.id // .data.id')

  # 标记为已售出
  curl -sL -X PUT "$BASE_URL/assets/$SOLD_ASSET_ID/sell" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN_ASSET" \
    -d '{"sell_price":2000,"sell_fee":50,"sell_channel":"二手平台","notes":"已售出测试"}' > /dev/null

  log_ok "test_asset 就绪（5 个资产：in_use/idle/retired/USD/已售出）"
else
  log_info "test_asset 已有 $ASSET_COUNT 个资产，跳过创建"
  log_ok "test_asset 就绪"
fi

# ──────────────────────────────────────────────
# 1.3 test_rich — 完整数据（资产+负债+心愿+多状态）
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

  # 实物资产（3 个，含 properties 字段）
  create_physical_asset "$TOKEN_RICH" "{\"name\":\"测试房产\",\"asset_type\":\"physical\",\"category_id\":\"$CAT_HOUSE_R\",\"purchase_price\":5000000,\"current_value\":5500000,\"currency\":\"CNY\",\"purchase_date\":\"2020-01-01\",\"status\":\"in_use\",\"location\":\"测试城市\",\"usage_frequency\":\"daily\",\"expected_lifespan_days\":36500,\"annual_maintenance_cost\":30000,\"properties\":\"{\\\"area\\\":120,\\\"rooms\\\":4}\"}"

  # 创建车辆资产并获取 ID（用于负债关联）
  CAR_RESP=$(curl -sL -X POST "$BASE_URL/assets" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN_RICH" \
    -d "{\"name\":\"测试车辆\",\"asset_type\":\"physical\",\"category_id\":\"$CAT_CAR_R\",\"purchase_price\":300000,\"current_value\":250000,\"currency\":\"CNY\",\"purchase_date\":\"2022-06-01\",\"status\":\"in_use\",\"location\":\"测试城市\",\"usage_frequency\":\"daily\",\"expected_lifespan_days\":3650,\"annual_maintenance_cost\":15000}")
  CAR_ID=$(echo "$CAR_RESP" | jq -r '.id // .data.id')

  create_physical_asset "$TOKEN_RICH" "{\"name\":\"测试电脑\",\"asset_type\":\"physical\",\"category_id\":\"$CAT_ELEC_R\",\"purchase_price\":15000,\"current_value\":10000,\"currency\":\"CNY\",\"purchase_date\":\"2023-01-01\",\"status\":\"in_use\",\"location\":\"家\",\"usage_frequency\":\"daily\",\"expected_lifespan_days\":1825,\"annual_maintenance_cost\":500}"

  # 金融资产（3 个）
  create_financial_asset "$TOKEN_RICH" "{\"name\":\"测试股票\",\"asset_type\":\"financial\",\"category_id\":\"$CAT_STOCK_R\",\"purchase_price\":100000,\"current_value\":120000,\"currency\":\"CNY\",\"purchase_date\":\"2023-01-01\",\"institution\":\"测试券商\",\"notes\":\"测试股票持仓\"}"
  create_financial_asset "$TOKEN_RICH" "{\"name\":\"测试基金\",\"asset_type\":\"financial\",\"category_id\":\"$CAT_FUND_R\",\"purchase_price\":50000,\"current_value\":55000,\"currency\":\"CNY\",\"purchase_date\":\"2023-06-01\",\"institution\":\"测试基金公司\"}"
  create_financial_asset "$TOKEN_RICH" "{\"name\":\"测试存款\",\"asset_type\":\"financial\",\"category_id\":\"$CAT_DEPOSIT_R\",\"purchase_price\":200000,\"current_value\":200000,\"currency\":\"CNY\",\"purchase_date\":\"2024-01-01\",\"institution\":\"测试银行\"}"

  # 负债（2 个基础 + 1 个关联资产的负债）
  create_liability "$TOKEN_RICH" "{\"name\":\"测试房贷\",\"category\":\"mortgage\",\"original_amount\":3000000,\"remaining_amount\":2800000,\"currency\":\"CNY\",\"interest_rate\":4.2,\"monthly_payment\":15000,\"start_date\":\"2020-01-01\",\"end_date\":\"2050-01-01\",\"institution\":\"测试银行\"}"

  # 关联车贷到车辆资产
  create_liability "$TOKEN_RICH" "{\"name\":\"测试车贷\",\"category\":\"car_loan\",\"original_amount\":200000,\"remaining_amount\":100000,\"currency\":\"CNY\",\"interest_rate\":5.0,\"monthly_payment\":4000,\"start_date\":\"2022-06-01\",\"end_date\":\"2026-06-01\",\"institution\":\"测试银行\",\"linked_asset_id\":\"$CAR_ID\",\"notes\":\"关联到测试车辆\"}"

  # 已还清的负债
  PAID_LIABILITY_RESP=$(curl -sL -X POST "$BASE_URL/liabilities" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN_RICH" \
    -d "{\"name\":\"已还清贷款\",\"category\":\"personal_loan\",\"original_amount\":50000,\"remaining_amount\":50000,\"currency\":\"CNY\",\"interest_rate\":6.0,\"start_date\":\"2023-01-01\",\"end_date\":\"2024-01-01\",\"institution\":\"测试银行\"}")
  PAID_LIABILITY_ID=$(echo "$PAID_LIABILITY_RESP" | jq -r '.id // .data.id')
  # 记录还款使其变为 is_active=false
  curl -sL -X PUT "$BASE_URL/liabilities/$PAID_LIABILITY_ID/payment" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN_RICH" \
    -d '{"amount":50000}' > /dev/null

  # 心愿（2 个基础 + 多状态）
  create_wish "$TOKEN_RICH" "{\"name\":\"测试心愿1\",\"expected_price\":50000,\"currency\":\"CNY\",\"priority\":\"high\",\"description\":\"E2E 测试心愿\"}"
  create_wish "$TOKEN_RICH" "{\"name\":\"测试心愿2\",\"expected_price\":10000,\"currency\":\"CNY\",\"priority\":\"medium\",\"description\":\"E2E 测试心愿2\"}"

  # 已实现的心愿
  REALIZED_WISH_RESP=$(curl -sL -X POST "$BASE_URL/wishes" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN_RICH" \
    -d "{\"name\":\"已实现心愿\",\"expected_price\":8000,\"currency\":\"CNY\",\"priority\":\"low\",\"description\":\"已购买\"}")
  REALIZED_WISH_ID=$(echo "$REALIZED_WISH_RESP" | jq -r '.id // .data.id')
  # 创建关联资产并标记心愿为已实现
  REALIZED_ASSET_RESP=$(curl -sL -X POST "$BASE_URL/assets" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN_RICH" \
    -d "{\"name\":\"实现心愿的资产\",\"asset_type\":\"physical\",\"category_id\":\"$CAT_ELEC_R\",\"purchase_price\":8000,\"current_value\":8000,\"currency\":\"CNY\",\"purchase_date\":\"2024-01-15\",\"status\":\"in_use\"}")
  REALIZED_ASSET_ID=$(echo "$REALIZED_ASSET_RESP" | jq -r '.id // .data.id')
  curl -sL -X POST "$BASE_URL/wishes/$REALIZED_WISH_ID/realize" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN_RICH" \
    -d "{\"purchase_price\":8000,\"purchase_date\":\"2024-01-15\",\"category_id\":\"$CAT_ELEC_R\"}" > /dev/null

  # 已取消的心愿
  CANCELLED_WISH_RESP=$(curl -sL -X POST "$BASE_URL/wishes" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN_RICH" \
    -d "{\"name\":\"已取消心愿\",\"expected_price\":20000,\"currency\":\"CNY\",\"priority\":\"medium\",\"description\":\"不再需要\"}")
  CANCELLED_WISH_ID=$(echo "$CANCELLED_WISH_RESP" | jq -r '.id // .data.id')
  curl -sL -X PUT "$BASE_URL/wishes/$CANCELLED_WISH_ID" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN_RICH" \
    -d '{"status":"cancelled"}' > /dev/null

  # 构造分页测试数据（各 25 个）
  log_info "为 test_rich 创建分页测试数据..."
  for i in {1..25}; do
    create_physical_asset "$TOKEN_RICH" "{\"name\":\"分页测试资产-$i\",\"asset_type\":\"physical\",\"category_id\":\"$CAT_HOUSE_R\",\"purchase_price\":1000,\"current_value\":1000,\"currency\":\"CNY\",\"purchase_date\":\"2023-01-01\",\"status\":\"in_use\"}"
    create_liability "$TOKEN_RICH" "{\"name\":\"分页测试负债-$i\",\"category\":\"other\",\"original_amount\":10000,\"remaining_amount\":5000,\"currency\":\"CNY\",\"institution\":\"测试银行\"}"
    create_wish "$TOKEN_RICH" "{\"name\":\"分页测试心愿-$i\",\"expected_price\":1000,\"currency\":\"CNY\",\"priority\":\"low\",\"description\":\"分页测试\"}"
  done

  log_ok "test_rich 就绪（31 资产 + 28 负债 + 29 心愿 + 多状态覆盖）"

  # ──────────────────────────────────────────────
  # 1.3.1 test_rich_member — test_rich 家庭的普通成员（测试角色权限）
  # ──────────────────────────────────────────────
  log_info "初始化 test_rich_member（test_rich 家庭的 member 角色）..."

  # 获取 test_rich 的家庭邀请码
  FAMILY_INFO=$(curl -sL "$BASE_URL/family/" -H "Authorization: Bearer $TOKEN_RICH")
  INVITE_CODE=$(echo "$FAMILY_INFO" | jq -r '.data.invite_code')

  if [ -n "$INVITE_CODE" ] && [ "$INVITE_CODE" != "null" ]; then
    # 注册新用户并加入家庭（角色为 member）
    MEMBER_RESP=$(curl -sL -w "\n%{http_code}" -X POST "$BASE_URL/auth/register" \
      -H "Content-Type: application/json" \
      -d "{\"username\":\"test_rich_member\",\"display_name\":\"测试成员\",\"password\":\"TestMember123!\"," \
      -d "\"family_invite_code\":\"$INVITE_CODE\"}")
    MEMBER_HTTP=$(echo "$MEMBER_RESP" | tail -1)
    MEMBER_BODY=$(echo "$MEMBER_RESP" | sed '$d')

    if [ "$MEMBER_HTTP" = "200" ] || [ "$MEMBER_HTTP" = "201" ]; then
      MEMBER_TOKEN=$(echo "$MEMBER_BODY" | jq -r '.access_token // .data.access_token')
      log_ok "test_rich_member 创建成功（member 角色）"

      # 为 member 创建少量资产（测试数据隔离）
      CAT_DIGITAL_M=$(get_category_id "$MEMBER_TOKEN" "电子设备" "physical")
      if [ -n "$CAT_DIGITAL_M" ] && [ "$CAT_DIGITAL_M" != "null" ]; then
        create_physical_asset "$MEMBER_TOKEN" "{\"name\":\"成员手机\",\"asset_type\":\"physical\",\"category_id\":\"$CAT_DIGITAL_M\",\"purchase_price\":5000,\"current_value\":4000,\"currency\":\"CNY\",\"purchase_date\":\"2023-06-01\",\"status\":\"in_use\"}"
        log_ok "test_rich_member 创建 1 个资产（member 数据隔离测试）"
      fi
    elif [ "$MEMBER_HTTP" = "409" ] || [ "$MEMBER_HTTP" = "400" ]; then
      log_info "test_rich_member 已存在，直接登录"
      MEMBER_LOGIN=$(curl -sL -X POST "$BASE_URL/auth/login" \
        -H "Content-Type: application/json" \
        -d '{"username":"test_rich_member","password":"TestMember123!"}')
      MEMBER_TOKEN=$(echo "$MEMBER_LOGIN" | jq -r '.access_token // .data.access_token')
      log_ok "test_rich_member 就绪（member 角色）"
    else
      log_warn "test_rich_member 创建失败: HTTP $MEMBER_HTTP — 跳过"
    fi
  else
    log_warn "无法获取 test_rich 家庭邀请码 — 跳过 member 创建"
  fi
fi

# ──────────────────────────────────────────────
# 1.4 test_child — test_rich 家庭的儿童账号
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
    -d '{"username":"testchild","display_name":"test_child","avatar_color":"#FF6B6B","pin":["🐱","🐶","🐸","🦊"]}')
  CHILD_HTTP=$(echo "$CREATE_CHILD_RESP" | tail -1)
  CHILD_BODY=$(echo "$CREATE_CHILD_RESP" | sed '$d')
  if [ "$CHILD_HTTP" = "200" ] || [ "$CHILD_HTTP" = "201" ]; then
    CHILD_ID=$(echo "$CHILD_BODY" | jq -r '.id // .data.id')
    log_ok "test_child created (id: $CHILD_ID)"
  else
    log_err "create test_child failed: HTTP $CHILD_HTTP - $CHILD_BODY"
    exit 1
  fi
else
  log_info "test_child exists, skipping (id: $CHILD_ID)"
fi
log_ok "test_child ready"

# ----------------------------------------------
# 1.5 Chore template - test_rich family test chore
# ----------------------------------------------
log_info "Initializing test chore template..."

TEMPLATES_RESP=$(curl -sL "$BASE_URL/family/chore-templates" \
  -H "Authorization: Bearer $TOKEN_RICH")
TEMPLATE_ID=$(echo "$TEMPLATES_RESP" | jq -r '.data[] | select(.name=="测试家务") | .id' 2>/dev/null | head -1)

if [ -z "$TEMPLATE_ID" ] || [ "$TEMPLATE_ID" = "null" ]; then
  log_info "Creating test chore template..."
  CREATE_TPL_RESP=$(curl -sL -w "\n%{http_code}" -X POST "$BASE_URL/family/chore-templates" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN_RICH" \
    -d '{"name":"测试家务","emoji":"🧹","coin_reward":10,"frequency":"daily","assignment_type":"pool"}')
  TPL_HTTP=$(echo "$CREATE_TPL_RESP" | tail -1)
  TPL_BODY=$(echo "$CREATE_TPL_RESP" | sed '$d')
  if [ "$TPL_HTTP" = "200" ] || [ "$TPL_HTTP" = "201" ]; then
    TEMPLATE_ID=$(echo "$TPL_BODY" | jq -r '.id // .data.id')
    log_ok "Test chore template created（id: $TEMPLATE_ID）"
  else
    log_err "Creating test chore template... HTTP $TPL_HTTP — $TPL_BODY"
    exit 1
  fi
else
  log_info "Test chore template already exists, skipping (id: $TEMPLATE_ID)"
fi
log_ok "Test chore template ready"

# ----------------------------------------------
# 1.6 test_child cross-day chores
# ----------------------------------------------
log_info "Initializing test_child cross-day chores..."
CHILD_TOKEN_RICH=$(curl -sL -X POST "$BASE_URL/auth/child/login" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"testchild\",\"pin_sequence\":[\"🐱\",\"🐶\",\"🐸\",\"🦊\"]}" \
  | jq -r '.data.access_token // .access_token')

if [ -n "$CHILD_TOKEN_RICH" ] && [ "$CHILD_TOKEN_RICH" != "null" ]; then
  if date -v-1d >/dev/null 2>&1; then
    YESTERDAY=$(date -v-1d +%Y-%m-%d)
    TOMORROW=$(date -v+1d +%Y-%m-%d)
  else
    YESTERDAY=$(date -d "yesterday" +%Y-%m-%d)
    TOMORROW=$(date -d "tomorrow" +%Y-%m-%d)
  fi
  TODAY=$(date +%Y-%m-%d)

  # 昨日任务（已完成且已审批）
  CHORES_YEST=$(curl -sL -X GET "$BASE_URL/child/chores?date=$YESTERDAY" -H "Authorization: Bearer $CHILD_TOKEN_RICH")
  INST_YEST=$(echo "$CHORES_YEST" | jq -r '.data[0].id // empty')
  STATUS_YEST=$(echo "$CHORES_YEST" | jq -r '.data[0].status // empty')

  if [ -n "$INST_YEST" ] && [ "$STATUS_YEST" = "available" ]; then
    curl -sL -X POST "$BASE_URL/child/chores/$INST_YEST/complete" -H "Authorization: Bearer $CHILD_TOKEN_RICH" > /dev/null
    curl -sL -X POST "$BASE_URL/family/chore-approvals/$INST_YEST/approve" -H "Authorization: Bearer $TOKEN_RICH" > /dev/null
    log_ok "test_child: 完成并审批昨日家务"
  fi

  # 今日任务（仅完成待审批）
  CHORES_TODAY=$(curl -sL -X GET "$BASE_URL/child/chores?date=$TODAY" -H "Authorization: Bearer $CHILD_TOKEN_RICH")
  INST_TODAY=$(echo "$CHORES_TODAY" | jq -r '.data[0].id // empty')
  STATUS_TODAY=$(echo "$CHORES_TODAY" | jq -r '.data[0].status // empty')

  if [ -n "$INST_TODAY" ] && [ "$STATUS_TODAY" = "available" ]; then
    curl -sL -X POST "$BASE_URL/child/chores/$INST_TODAY/complete" -H "Authorization: Bearer $CHILD_TOKEN_RICH" > /dev/null
    log_ok "test_child: 完成今日家务（待审批）"
  fi

  # 明日任务（仅生成获取）
  curl -sL -X GET "$BASE_URL/child/chores?date=$TOMORROW" -H "Authorization: Bearer $CHILD_TOKEN_RICH" > /dev/null
fi

# ----------------------------------------------
# 1.7 test_rich 家庭盲盒数据
# ----------------------------------------------
log_info "初始化 test_rich 盲盒数据..."

# 幂等检查：礼物池是否已有数据
GIFTS_RESP=$(curl -sL "$BASE_URL/blind-box/gifts" -H "Authorization: Bearer $TOKEN_RICH")
GIFT_COUNT=$(echo "$GIFTS_RESP" | jq -r 'if type == "array" then length elif (.data | type) == "array" then .data | length else 0 end' 2>/dev/null || echo "0")

if [ "$GIFT_COUNT" = "0" ]; then
  # 启用盲盒功能
  curl -sL -X PUT "$BASE_URL/blind-box/config" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN_RICH" \
    -d '{"enabled":true,"base_draw_prob":0.5,"special_day_prob":0.9}' > /dev/null
  log_ok "test_rich: 盲盒配置已启用"

  # 创建礼物池（覆盖不同 value_score 档位）
  GIFT1_RESP=$(curl -sL -X POST "$BASE_URL/blind-box/gifts" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN_RICH" \
    -d '{"name":"贴纸包","emoji":"🎨","value_score":2,"description":"一套可爱贴纸"}')
  GIFT1_ID=$(echo "$GIFT1_RESP" | jq -r '.id // .data.id')
  log_ok "test_rich: 创建礼物 贴纸包 (value_score=2)"

  GIFT2_RESP=$(curl -sL -X POST "$BASE_URL/blind-box/gifts" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN_RICH" \
    -d '{"name":"小玩具","emoji":"🧸","value_score":4,"description":"随机小玩具一个"}')
  GIFT2_ID=$(echo "$GIFT2_RESP" | jq -r '.id // .data.id')
  log_ok "test_rich: 创建礼物 小玩具 (value_score=4)"

  GIFT3_RESP=$(curl -sL -X POST "$BASE_URL/blind-box/gifts" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN_RICH" \
    -d '{"name":"乐高小套装","emoji":"🧱","value_score":7,"description":"乐高经典系列小套装"}')
  GIFT3_ID=$(echo "$GIFT3_RESP" | jq -r '.id // .data.id')
  log_ok "test_rich: 创建礼物 乐高小套装 (value_score=7, 惊喜档)"

  GIFT4_RESP=$(curl -sL -X POST "$BASE_URL/blind-box/gifts" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN_RICH" \
    -d '{"name":"游乐园门票","emoji":"🎡","value_score":9,"description":"亲子游乐园一日票"}')
  GIFT4_ID=$(echo "$GIFT4_RESP" | jq -r '.id // .data.id')
  log_ok "test_rich: 创建礼物 游乐园门票 (value_score=9, 惊喜档)"

  # 从心愿转入礼物池（需要先有已批准的儿童心愿）
  # 获取 test_child 的已批准心愿 ID（active 状态）
  CHILD_WISHES_RESP=$(curl -sL "$BASE_URL/family/child-wishes" \
    -H "Authorization: Bearer $TOKEN_RICH" 2>/dev/null || echo "{}")
  WISH_FOR_GIFT=$(echo "$CHILD_WISHES_RESP" | jq -r '[.data[] // .[] | select(.status=="active")] | .[0].id // empty' 2>/dev/null | head -1)
  if [ -n "$WISH_FOR_GIFT" ] && [ "$WISH_FOR_GIFT" != "null" ]; then
    curl -sL -X POST "$BASE_URL/blind-box/gifts/from-wish/$WISH_FOR_GIFT" \
      -H "Authorization: Bearer $TOKEN_RICH" > /dev/null
    log_ok "test_rich: 从心愿转入礼物池 (wish_id=$WISH_FOR_GIFT)"
  fi

  # 为 test_child 创建 bonus_draw（available 状态）
  NEXT_MONTH=$(date -v+30d +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -d "+30 days" +%Y-%m-%dT%H:%M:%SZ)
  curl -sL -X POST "$BASE_URL/blind-box/bonus-draws" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN_RICH" \
    -d "{\"child_user_id\":\"$CHILD_ID\",\"expires_at\":\"$NEXT_MONTH\"}" > /dev/null 2>&1 || true
  log_ok "test_rich: 为 test_child 创建 bonus_draw（available）"

  log_ok "test_rich: 盲盒礼物池就绪（4 个礼物）"
else
  log_info "test_rich 盲盒礼物池已有 $GIFT_COUNT 个礼物，跳过"
fi

log_ok "========== Part 1: Fixed test accounts complete =========="

# ========================================
# Part 2: Complete simulation data (for demo)
# ========================================
if [[ "$SKIP_DEMO" == true ]]; then
  log_info "Skip Part 2: Complete simulation data (--skip-demo)"
else
  log_info "========== Part 2: Complete simulation data =========="

  # ----------------------------------------------
  # 2.1 demouser login
  # ----------------------------------------------
  log_info "Initializing demouser..."
  TOKEN=$(register_or_login "demouser" "DemoPass123" "Demo User" "Demo Family")
  if [ -z "$TOKEN" ] || [ "$TOKEN" = "null" ]; then
    log_err "demouser initialization failed"
    exit 1
  fi
  log_ok "demouser login successful"

  # ──────────────────────────────────────────────
  # 2.2 幂等检查
  # ──────────────────────────────────────────────
  DEMO_ASSET_COUNT=$(get_asset_count "$TOKEN")
  if [ "$DEMO_ASSET_COUNT" -ge 30 ] 2>/dev/null; then
    log_info "demouser 已有 $DEMO_ASSET_COUNT 件资产，跳过资产/负债/心愿创建（幂等保护）"
  else
    # ═══════════════════════════════════════════
    # 2.3 创建实物资产（19 项）
    # ═══════════════════════════════════════════
    log_info "创建实物资产..."

    # 房产 - 高价值资产
    CAT_HOUSE=$(get_category_id "$TOKEN" "房产" "physical")
    create_physical_asset "$TOKEN" "$(cat <<EOF
{
  "name":"深圳湾一号",
  "asset_type":"physical",
  "category_id":"$CAT_HOUSE",
  "purchase_price":25000000,
  "current_value":28000000,
  "currency":"CNY",
  "purchase_date":"2020-01-15",
  "status":"in_use",
  "location":"深圳市南山区",
  "usage_frequency":"daily",
  "expected_lifespan_days":36500,
  "annual_maintenance_cost":50000,
  "notes":"豪宅，南山区海景房",
  "target_daily_cost":800
}
EOF
)"
    log_ok "创建: 深圳湾一号"

    # 车辆 - 中等价值
    CAT_CAR=$(get_category_id "$TOKEN" "车辆" "physical")
    create_physical_asset "$TOKEN" "$(cat <<EOF
{
  "name":"宝马X5",
  "asset_type":"physical",
  "category_id":"$CAT_CAR",
  "purchase_price":450000,
  "current_value":380000,
  "currency":"CNY",
  "purchase_date":"2022-06-01",
  "status":"in_use",
  "location":"深圳",
  "usage_frequency":"daily",
  "expected_lifespan_days":3650,
  "annual_maintenance_cost":15000,
  "notes":"2022款 xDrive40i",
  "target_daily_cost":150
}
EOF
)"
    log_ok "创建: 宝马X5"

    create_physical_asset "$TOKEN" "$(cat <<EOF
{
  "name":"特斯拉Model 3",
  "asset_type":"physical",
  "category_id":"$CAT_CAR",
  "purchase_price":280000,
  "current_value":220000,
  "currency":"CNY",
  "purchase_date":"2023-03-15",
  "status":"in_use",
  "location":"深圳",
  "usage_frequency":"daily",
  "expected_lifespan_days":3650,
  "annual_maintenance_cost":5000,
  "notes":"电动车，充电成本低"
}
EOF
)"
    log_ok "创建: 特斯拉Model 3"

    # 数码 - 高频使用
    CAT_DIGITAL=$(get_category_id "$TOKEN" "数码" "physical")
    create_physical_asset "$TOKEN" "$(cat <<EOF
{
  "name":"MacBook Pro",
  "asset_type":"physical",
  "category_id":"$CAT_DIGITAL",
  "purchase_price":18000,
  "current_value":15000,
  "currency":"CNY",
  "purchase_date":"2023-01-15",
  "status":"in_use",
  "location":"家中书房",
  "usage_frequency":"daily",
  "expected_lifespan_days":1825,
  "notes":"14寸 M2 Pro",
  "target_daily_cost":15
}
EOF
)"
    log_ok "创建: MacBook Pro"

    create_physical_asset "$TOKEN" "$(cat <<EOF
{
  "name":"iPad Pro",
  "asset_type":"physical",
  "category_id":"$CAT_DIGITAL",
  "purchase_price":8000,
  "current_value":6500,
  "currency":"CNY",
  "purchase_date":"2023-03-20",
  "status":"in_use",
  "location":"客厅",
  "usage_frequency":"weekly",
  "expected_lifespan_days":1825,
  "notes":"12.9寸 WiFi版"
}
EOF
)"
    log_ok "创建: iPad Pro"

    create_physical_asset "$TOKEN" "$(cat <<EOF
{
  "name":"iPhone 15 Pro",
  "asset_type":"physical",
  "category_id":"$CAT_DIGITAL",
  "purchase_price":8999,
  "current_value":8000,
  "currency":"CNY",
  "purchase_date":"2023-09-22",
  "status":"in_use",
  "location":"随身",
  "usage_frequency":"daily",
  "expected_lifespan_days":1095,
  "notes":"256GB 钛金属蓝色"
}
EOF
)"
    log_ok "创建: iPhone 15 Pro"

    # 家电
    CAT_APPLIANCE=$(get_category_id "$TOKEN" "家电" "physical")
    create_physical_asset "$TOKEN" "$(cat <<EOF
{
  "name":"戴森吸尘器",
  "asset_type":"physical",
  "category_id":"$CAT_APPLIANCE",
  "purchase_price":4500,
  "current_value":3500,
  "currency":"CNY",
  "purchase_date":"2023-05-10",
  "status":"in_use",
  "location":"客厅",
  "usage_frequency":"weekly",
  "expected_lifespan_days":1825,
  "annual_maintenance_cost":200,
  "notes":"V15 Detect"
}
EOF
)"
    log_ok "创建: 戴森吸尘器"

    create_physical_asset "$TOKEN" "$(cat <<EOF
{
  "name":"美的空调",
  "asset_type":"physical",
  "category_id":"$CAT_APPLIANCE",
  "purchase_price":6000,
  "current_value":5000,
  "currency":"CNY",
  "purchase_date":"2022-07-01",
  "status":"in_use",
  "location":"主卧",
  "usage_frequency":"daily",
  "expected_lifespan_days":3650,
  "annual_maintenance_cost":100,
  "notes":"1.5匹 变频"
}
EOF
)"
    log_ok "创建: 美的空调"

    create_physical_asset "$TOKEN" "$(cat <<EOF
{
  "name":"西门子洗衣机",
  "asset_type":"physical",
  "category_id":"$CAT_APPLIANCE",
  "purchase_price":5500,
  "current_value":4500,
  "currency":"CNY",
  "purchase_date":"2022-03-01",
  "status":"in_use",
  "location":"阳台",
  "usage_frequency":"weekly",
  "expected_lifespan_days":3650,
  "annual_maintenance_cost":50,
  "notes":"10公斤 滚筒"
}
EOF
)"
    log_ok "创建: 西门子洗衣机"

    # 家具
    CAT_FURNITURE=$(get_category_id "$TOKEN" "家具" "physical")
    create_physical_asset "$TOKEN" "$(cat <<EOF
{
  "name":"实木沙发",
  "asset_type":"physical",
  "category_id":"$CAT_FURNITURE",
  "purchase_price":12000,
  "current_value":10000,
  "currency":"CNY",
  "purchase_date":"2021-03-15",
  "status":"in_use",
  "location":"客厅",
  "usage_frequency":"daily",
  "expected_lifespan_days":7300,
  "notes":"北美黑胡桃木"
}
EOF
)"
    log_ok "创建: 实木沙发"

    create_physical_asset "$TOKEN" "$(cat <<EOF
{
  "name":"餐桌椅套装",
  "asset_type":"physical",
  "category_id":"$CAT_FURNITURE",
  "purchase_price":8000,
  "current_value":7000,
  "currency":"CNY",
  "purchase_date":"2021-03-15",
  "status":"in_use",
  "location":"餐厅",
  "usage_frequency":"daily",
  "expected_lifespan_days":7300,
  "notes":"一桌六椅"
}
EOF
)"
    log_ok "创建: 餐桌椅套装"

    create_physical_asset "$TOKEN" "$(cat <<EOF
{
  "name":"乳胶床垫",
  "asset_type":"physical",
  "category_id":"$CAT_FURNITURE",
  "purchase_price":15000,
  "current_value":12000,
  "currency":"CNY",
  "purchase_date":"2022-01-01",
  "status":"in_use",
  "location":"主卧",
  "usage_frequency":"daily",
  "expected_lifespan_days":3650,
  "notes":"King size 天然乳胶"
}
EOF
)"
    log_ok "创建: 乳胶床垫"

    # 珠宝 - 保值资产
    CAT_JEWELRY=$(get_category_id "$TOKEN" "珠宝" "physical")
    create_physical_asset "$TOKEN" "$(cat <<EOF
{
  "name":"黄金项链",
  "asset_type":"physical",
  "category_id":"$CAT_JEWELRY",
  "purchase_price":15000,
  "current_value":18000,
  "currency":"CNY",
  "purchase_date":"2020-12-20",
  "status":"in_use",
  "location":"保险箱",
  "usage_frequency":"monthly",
  "expected_lifespan_days":36500,
  "notes":"50克 足金"
}
EOF
)"
    log_ok "创建: 黄金项链"

    create_physical_asset "$TOKEN" "$(cat <<EOF
{
  "name":"钻石戒指",
  "asset_type":"physical",
  "category_id":"$CAT_JEWELRY",
  "purchase_price":30000,
  "current_value":35000,
  "currency":"CNY",
  "purchase_date":"2019-05-20",
  "status":"in_use",
  "location":"保险箱",
  "usage_frequency":"rarely",
  "expected_lifespan_days":36500,
  "notes":"1克拉 VS1净度"
}
EOF
)"
    log_ok "创建: 钻石戒指"

    create_physical_asset "$TOKEN" "$(cat <<EOF
{
  "name":"黄金手镯",
  "asset_type":"physical",
  "category_id":"$CAT_JEWELRY",
  "purchase_price":25000,
  "current_value":32000,
  "currency":"CNY",
  "purchase_date":"2021-02-14",
  "status":"in_use",
  "location":"保险箱",
  "usage_frequency":"monthly",
  "expected_lifespan_days":36500,
  "notes":"80克 古法金"
}
EOF
)"
    log_ok "创建: 黄金手镯"

    # 服饰
    CAT_CLOTHING=$(get_category_id "$TOKEN" "服饰" "physical")
    create_physical_asset "$TOKEN" "$(cat <<EOF
{
  "name":"羽绒服",
  "asset_type":"physical",
  "category_id":"$CAT_CLOTHING",
  "purchase_price":2000,
  "current_value":1500,
  "currency":"CNY",
  "purchase_date":"2023-11-01",
  "status":"in_use",
  "location":"衣帽间",
  "usage_frequency":"weekly",
  "expected_lifespan_days":1825,
  "notes":"Canada Goose"
}
EOF
)"
    log_ok "创建: 羽绒服"

    create_physical_asset "$TOKEN" "$(cat <<EOF
{
  "name":"西装套装",
  "asset_type":"physical",
  "category_id":"$CAT_CLOTHING",
  "purchase_price":5000,
  "current_value":4000,
  "currency":"CNY",
  "purchase_date":"2023-03-01",
  "status":"in_use",
  "location":"衣帽间",
  "usage_frequency":"monthly",
  "expected_lifespan_days":1825,
  "annual_maintenance_cost":200,
  "notes":"定制款 意大利面料"
}
EOF
)"
    log_ok "创建: 西装套装"

    # 美妆 - 消耗品
    CAT_BEAUTY=$(get_category_id "$TOKEN" "美妆" "physical")
    create_physical_asset "$TOKEN" "$(cat <<EOF
{
  "name":"SK-II套装",
  "asset_type":"physical",
  "category_id":"$CAT_BEAUTY",
  "purchase_price":3000,
  "current_value":2500,
  "currency":"CNY",
  "purchase_date":"2024-01-01",
  "status":"in_use",
  "location":"浴室",
  "usage_frequency":"daily",
  "expected_lifespan_days":730,
  "notes":"神仙水+精华+面霜"
}
EOF
)"
    log_ok "创建: SK-II套装"

    # 运动
    CAT_SPORTS=$(get_category_id "$TOKEN" "运动" "physical")
    create_physical_asset "$TOKEN" "$(cat <<EOF
{
  "name":"跑步机",
  "asset_type":"physical",
  "category_id":"$CAT_SPORTS",
  "purchase_price":5000,
  "current_value":4000,
  "currency":"CNY",
  "purchase_date":"2022-09-01",
  "status":"in_use",
  "location":"健身房",
  "usage_frequency":"weekly",
  "expected_lifespan_days":3650,
  "annual_maintenance_cost":100,
  "notes":"NordicTrack"
}
EOF
)"
    log_ok "创建: 跑步机"

    # ═══════════════════════════════════════════
    # 2.4 创建金融资产（11 项）
    # ═══════════════════════════════════════════
    log_info "创建金融资产..."

    # 存款
    CAT_DEPOSIT=$(get_category_id "$TOKEN" "存款" "financial")
    create_financial_asset "$TOKEN" "$(cat <<EOF
{
  "name":"招商银行定存",
  "asset_type":"financial",
  "category_id":"$CAT_DEPOSIT",
  "purchase_price":300000,
  "current_value":315000,
  "currency":"CNY",
  "purchase_date":"2023-01-15",
  "status":"in_use",
  "institution":"招商银行",
  "interest_rate":2.5,
  "maturity_date":"2027-01-01",
  "notes":"三年期大额存单"
}
EOF
)"
    log_ok "创建: 招商银行定存"

    create_financial_asset "$TOKEN" "$(cat <<EOF
{
  "name":"工商银行活期",
  "asset_type":"financial",
  "category_id":"$CAT_DEPOSIT",
  "purchase_price":200000,
  "current_value":202000,
  "currency":"CNY",
  "purchase_date":"2023-01-15",
  "status":"in_use",
  "institution":"工商银行",
  "interest_rate":0.3,
  "notes":"日常开支账户"
}
EOF
)"
    log_ok "创建: 工商银行活期"

    create_financial_asset "$TOKEN" "$(cat <<EOF
{
  "name":"美元存款",
  "asset_type":"financial",
  "category_id":"$CAT_DEPOSIT",
  "purchase_price":50000,
  "current_value":52000,
  "currency":"USD",
  "purchase_date":"2023-06-01",
  "status":"in_use",
  "institution":"中国银行",
  "interest_rate":4.5,
  "maturity_date":"2025-06-01",
  "notes":"两年期美元定存"
}
EOF
)"
    log_ok "创建: 美元存款"

    # 基金
    CAT_FUND=$(get_category_id "$TOKEN" "基金" "financial")
    create_financial_asset "$TOKEN" "$(cat <<EOF
{
  "name":"易方达蓝筹",
  "asset_type":"financial",
  "category_id":"$CAT_FUND",
  "purchase_price":150000,
  "current_value":120000,
  "currency":"CNY",
  "purchase_date":"2023-01-15",
  "status":"in_use",
  "institution":"易方达基金",
  "notes":"混合型基金 代码005827"
}
EOF
)"
    log_ok "创建: 易方达蓝筹"

    create_financial_asset "$TOKEN" "$(cat <<EOF
{
  "name":"华夏成长",
  "asset_type":"financial",
  "category_id":"$CAT_FUND",
  "purchase_price":80000,
  "current_value":75000,
  "currency":"CNY",
  "purchase_date":"2023-01-15",
  "status":"in_use",
  "institution":"华夏基金",
  "notes":"股票型基金 代码000001"
}
EOF
)"
    log_ok "创建: 华夏成长"

    create_financial_asset "$TOKEN" "$(cat <<EOF
{
  "name":"沪深300ETF",
  "asset_type":"financial",
  "category_id":"$CAT_FUND",
  "purchase_price":100000,
  "current_value":95000,
  "currency":"CNY",
  "purchase_date":"2022-07-01",
  "status":"in_use",
  "institution":"华泰柏瑞",
  "notes":"指数基金 代码510300"
}
EOF
)"
    log_ok "创建: 沪深300ETF"

    # 股票
    CAT_STOCK=$(get_category_id "$TOKEN" "股票" "financial")
    create_financial_asset "$TOKEN" "$(cat <<EOF
{
  "name":"贵州茅台",
  "asset_type":"financial",
  "category_id":"$CAT_STOCK",
  "purchase_price":100000,
  "current_value":95000,
  "currency":"CNY",
  "purchase_date":"2023-01-15",
  "status":"in_use",
  "institution":"中信证券",
  "notes":"50股 成本价2000元/股"
}
EOF
)"
    log_ok "创建: 贡献茅台"

    create_financial_asset "$TOKEN" "$(cat <<EOF
{
  "name":"腾讯控股",
  "asset_type":"financial",
  "category_id":"$CAT_STOCK",
  "purchase_price":50000,
  "current_value":42000,
  "currency":"HKD",
  "purchase_date":"2023-01-15",
  "status":"in_use",
  "institution":"富途证券",
  "notes":"港股 100股"
}
EOF
)"
    log_ok "创建: 腾讯控股"

    create_financial_asset "$TOKEN" "$(cat <<EOF
{
  "name":"苹果股票",
  "asset_type":"financial",
  "category_id":"$CAT_STOCK",
  "purchase_price":80000,
  "current_value":95000,
  "currency":"USD",
  "purchase_date":"2022-06-01",
  "status":"in_use",
  "institution":"盈透证券",
  "notes":"美股 AAPL 50股"
}
EOF
)"
    log_ok "创建: 苹果股票"

    # 债券
    CAT_BOND=$(get_category_id "$TOKEN" "债券" "financial")
    create_financial_asset "$TOKEN" "$(cat <<EOF
{
  "name":"国债",
  "asset_type":"financial",
  "category_id":"$CAT_BOND",
  "purchase_price":100000,
  "current_value":105000,
  "currency":"CNY",
  "purchase_date":"2023-01-15",
  "status":"in_use",
  "institution":"中国国债登记结算",
  "interest_rate":3.2,
  "maturity_date":"2028-01-01",
  "notes":"五年期储蓄国债"
}
EOF
)"
    log_ok "创建: 国债"

    # 保险
    CAT_INSURANCE=$(get_category_id "$TOKEN" "保险" "financial")
    create_financial_asset "$TOKEN" "$(cat <<EOF
{
  "name":"重疾险",
  "asset_type":"financial",
  "category_id":"$CAT_INSURANCE",
  "purchase_price":50000,
  "current_value":50000,
  "currency":"CNY",
  "purchase_date":"2023-01-15",
  "status":"in_use",
  "institution":"中国人寿",
  "notes":"保额50万 20年缴费"
}
EOF
)"
    log_ok "创建: 重疾险"

    # ═══════════════════════════════════════════
    # 2.5 创建负债（7 项）
    # ═══════════════════════════════════════════
    log_info "创建负债..."

    # 房贷 - 最大负债
    create_liability "$TOKEN" "$(cat <<EOF
{
  "name":"房贷",
  "category":"mortgage",
  "original_amount":18000000,
  "remaining_amount":15000000,
  "monthly_payment":85000,
  "interest_rate":4.2,
  "start_date":"2020-02-01",
  "end_date":"2050-02-01",
  "institution":"中国银行",
  "currency":"CNY",
  "notes":"深圳湾一号房贷 30年期"
}
EOF
)"
    log_ok "创建: 房贷"

    # 车贷
    create_liability "$TOKEN" "$(cat <<EOF
{
  "name":"宝马车贷",
  "category":"car_loan",
  "original_amount":300000,
  "remaining_amount":180000,
  "monthly_payment":8500,
  "interest_rate":3.5,
  "start_date":"2022-06-01",
  "end_date":"2026-06-01",
  "institution":"宝马金融",
  "currency":"CNY",
  "notes":"宝马X5车贷 4年期"
}
EOF
)"
    log_ok "创建: 宝马车贷"

    # 信用卡
    create_liability "$TOKEN" "$(cat <<EOF
{
  "name":"招商信用卡",
  "category":"credit_card",
  "original_amount":50000,
  "remaining_amount":30000,
  "monthly_payment":3000,
  "interest_rate":18,
  "institution":"招商银行",
  "currency":"CNY",
  "notes":"AE白金卡 本期账单分期"
}
EOF
)"
    log_ok "创建: 招商信用卡"

    create_liability "$TOKEN" "$(cat <<EOF
{
  "name":"工商信用卡",
  "category":"credit_card",
  "original_amount":30000,
  "remaining_amount":15000,
  "monthly_payment":1500,
  "interest_rate":15,
  "institution":"工商银行",
  "currency":"CNY",
  "notes":"工资卡关联 自动还款"
}
EOF
)"
    log_ok "创建: 工商信用卡"

    # 个人贷款
    create_liability "$TOKEN" "$(cat <<EOF
{
  "name":"装修贷款",
  "category":"personal_loan",
  "original_amount":200000,
  "remaining_amount":150000,
  "monthly_payment":5000,
  "interest_rate":6,
  "start_date":"2023-03-01",
  "end_date":"2027-03-01",
  "institution":"建设银行",
  "currency":"CNY",
  "notes":"装修贷 4年期 等额本息"
}
EOF
)"
    log_ok "创建: 装修贷款"

    create_liability "$TOKEN" "$(cat <<EOF
{
  "name":"教育贷款",
  "category":"personal_loan",
  "original_amount":100000,
  "remaining_amount":80000,
  "monthly_payment":3000,
  "interest_rate":4.5,
  "start_date":"2023-09-01",
  "end_date":"2026-09-01",
  "institution":"交通银行",
  "currency":"CNY",
  "notes":"MBA学费贷款"
}
EOF
)"
    log_ok "创建: 教育贷款"

    # 其他负债
    create_liability "$TOKEN" "$(cat <<EOF
{
  "name":"亲友借款",
  "category":"other",
  "original_amount":30000,
  "remaining_amount":20000,
  "monthly_payment":2000,
  "interest_rate":0,
  "institution":"",
  "currency":"CNY",
  "notes":"向亲戚借款 无息"
}
EOF
)"
    log_ok "创建: 亲友借款"

    # ═══════════════════════════════════════════
    # 2.6 创建心愿（9 项）
    # ═══════════════════════════════════════════
    log_info "创建心愿..."

    CAT_HOUSE_W=$(get_category_id "$TOKEN" "房产" "physical")
    CAT_CAR_W=$(get_category_id "$TOKEN" "车辆" "physical")
    CAT_DIGITAL_W=$(get_category_id "$TOKEN" "数码" "physical")
    CAT_SPORTS_W=$(get_category_id "$TOKEN" "运动" "physical")
    CAT_INSTRUMENT_W=$(get_category_id "$TOKEN" "乐器" "physical")
    CAT_JEWELRY_W=$(get_category_id "$TOKEN" "珠宝" "physical")

    # 高优先级心愿
    create_wish "$TOKEN" "$(cat <<EOF
{
  "name":"换新房",
  "expected_price":8000000,
  "priority":"high",
  "category_id":"$CAT_HOUSE_W",
  "currency":"CNY",
  "description":"在福田区购买一套四室两厅，改善居住环境"
}
EOF
)"
    log_ok "创建: 换新房"

    create_wish "$TOKEN" "$(cat <<EOF
{
  "name":"买新车",
  "expected_price":600000,
  "priority":"high",
  "category_id":"$CAT_CAR_W",
  "currency":"CNY",
  "description":"保时捷 Cayenne 或 奔驰 GLE"
}
EOF
)"
    log_ok "创建: 买新车"

    # 中优先级心愿
    create_wish "$TOKEN" "$(cat <<EOF
{
  "name":"出国旅游",
  "expected_price":80000,
  "priority":"medium",
  "currency":"CNY",
  "description":"去欧洲旅游两周，意大利+法国+瑞士"
}
EOF
)"
    log_ok "创建: 出国旅游"

    create_wish "$TOKEN" "$(cat <<EOF
{
  "name":"买相机",
  "expected_price":30000,
  "priority":"medium",
  "category_id":"$CAT_DIGITAL_W",
  "currency":"CNY",
  "description":"索尼 A7M4 全画幅微单 + 24-70mm 镜头"
}
EOF
)"
    log_ok "创建: 买相机"

    create_wish "$TOKEN" "$(cat <<EOF
{
  "name":"儿童钢琴",
  "expected_price":50000,
  "priority":"medium",
  "category_id":"$CAT_INSTRUMENT_W",
  "currency":"CNY",
  "description":"给孩子买一台雅马哈电钢琴"
}
EOF
)"
    log_ok "创建: 儿童钢琴"

    create_wish "$TOKEN" "$(cat <<EOF
{
  "name":"运动手表",
  "expected_price":5000,
  "priority":"medium",
  "category_id":"$CAT_SPORTS_W",
  "currency":"CNY",
  "description":"Apple Watch Ultra 或 Garmin Fenix"
}
EOF
)"
    log_ok "创建: 运动手表"

    # 低优先级心愿
    create_wish "$TOKEN" "$(cat <<EOF
{
  "name":"换手机",
  "expected_price":12000,
  "priority":"low",
  "category_id":"$CAT_DIGITAL_W",
  "currency":"CNY",
  "description":"iPhone 16 Pro Max 256GB"
}
EOF
)"
    log_ok "创建: 换手机"

    create_wish "$TOKEN" "$(cat <<EOF
{
  "name":"名表",
  "expected_price":150000,
  "priority":"low",
  "category_id":"$CAT_JEWELRY_W",
  "currency":"CNY",
  "description":"劳力士 Submariner 潜航者"
}
EOF
)"
    log_ok "创建: 名表"

    create_wish "$TOKEN" "$(cat <<EOF
{
  "name":"家庭影院",
  "expected_price":40000,
  "priority":"low",
  "currency":"CNY",
  "description":"投影仪+音响系统+电动幕布"
}
EOF
)"
    log_ok "创建: 家庭影院"

    # ═══════════════════════════════════════════
    # 2.7 生成快照
    # ═══════════════════════════════════════════
    log_info "生成快照..."
    curl -sL -X POST "$BASE_URL/family/snapshots/generate" \
      -H "Authorization: Bearer $TOKEN" > /dev/null
    log_ok "快照已生成"
  fi

  # ═══════════════════════════════════════════
  # 2.8 创建儿童数据
  # ═══════════════════════════════════════════
  log_info "创建儿童数据..."

  # 幂等检查：如果已有儿童成员，跳过创建
  EXISTING_CHILDREN=$(curl -sL "$BASE_URL/family/" -H "Authorization: Bearer $TOKEN" | jq '[.data.members[] | select(.role == "child")] | length')
  if [ "${EXISTING_CHILDREN:-0}" -ge 2 ] 2>/dev/null; then
    log_info "已存在 $EXISTING_CHILDREN 个儿童成员，跳过儿童数据创建（幂等保护）"
  else
    # 创建幼儿（6岁）
    CHILD1_RESP=$(curl -sL -X POST "$BASE_URL/family/children" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer $TOKEN" \
      -d '{
        "username": "xiaobao",
        "display_name": "小宝",
        "avatar_color": "#FF6B6B",
        "pin": ["🐱", "🌟", "🎈", "🐶"]
      }')
    CHILD1_ID=$(echo "$CHILD1_RESP" | jq -r '.data.id // .id')
    CHILD1_USERNAME=$(echo "$CHILD1_RESP" | jq -r '.data.username // .username')
    log_ok "创建儿童: 小宝 (6岁幼儿) id=$CHILD1_ID username=$CHILD1_USERNAME"

    # 创建青少年（14岁）
    CHILD2_RESP=$(curl -sL -X POST "$BASE_URL/family/children" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer $TOKEN" \
      -d '{
        "username": "dabao",
        "display_name": "大宝",
        "avatar_color": "#4ECDC4",
        "pin": ["🌈", "🍎", "🐸", "🦁"]
      }')
    CHILD2_ID=$(echo "$CHILD2_RESP" | jq -r '.data.id // .id')
    CHILD2_USERNAME=$(echo "$CHILD2_RESP" | jq -r '.data.username // .username')
    log_ok "创建儿童: 大宝 (14岁青少年) id=$CHILD2_ID username=$CHILD2_USERNAME"

    # 为两个孩子登录获取 child token（使用 username 方式）
    CHILD1_TOKEN=$(curl -sL -X POST "$BASE_URL/auth/child/login" \
      -H "Content-Type: application/json" \
      -d "{\"username\":\"xiaobao\",\"pin_sequence\":[\"🐱\",\"🌟\",\"🎈\",\"🐶\"]}" \
      | jq -r '.data.access_token // .access_token')

    CHILD2_TOKEN=$(curl -sL -X POST "$BASE_URL/auth/child/login" \
      -H "Content-Type: application/json" \
      -d "{\"username\":\"dabao\",\"pin_sequence\":[\"🌈\",\"🍎\",\"🐸\",\"🦁\"]}" \
      | jq -r '.data.access_token // .access_token')

    # 给孩子充值星星币（多次充值，创建交易历史）
    curl -sL -X POST "$BASE_URL/family/coins/grant" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer $TOKEN" \
      -d "{\"child_user_id\":\"$CHILD1_ID\",\"amount\":20,\"reason\":\"初始零花钱\"}" > /dev/null
    curl -sL -X POST "$BASE_URL/family/coins/grant" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer $TOKEN" \
      -d "{\"child_user_id\":\"$CHILD1_ID\",\"amount\":30,\"reason\":\"奖励\"}" > /dev/null
    log_ok "充值: 小宝 50 星星币（2笔交易）"

    curl -sL -X POST "$BASE_URL/family/coins/grant" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer $TOKEN" \
      -d "{\"child_user_id\":\"$CHILD2_ID\",\"amount\":50,\"reason\":\"初始零花钱\"}" > /dev/null
    curl -sL -X POST "$BASE_URL/family/coins/grant" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer $TOKEN" \
      -d "{\"child_user_id\":\"$CHILD2_ID\",\"amount\":40,\"reason\":\"家务奖励\"}" > /dev/null
    curl -sL -X POST "$BASE_URL/family/coins/grant" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer $TOKEN" \
      -d "{\"child_user_id\":\"$CHILD2_ID\",\"amount\":30,\"reason\":\"生日礼物\"}" > /dev/null
    log_ok "充值: 大宝 120 星星币（3笔交易）"

    # ═══════════════════════════════════════════
    # 儿童心愿完整状态流转测试（5种状态全覆盖）
    # ═══════════════════════════════════════════

    # 1. pending_review 状态（待审批）
    curl -sL -X POST "$BASE_URL/child/wishes" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer $CHILD1_TOKEN" \
      -d '{"name":"积木玩具","description":"乐高城市系列","emoji":"🧱","priority":"high"}' > /dev/null
    log_ok "创建心愿: 小宝 - 积木玩具 (pending_review)"

    # 2. rejected 状态（被拒绝）
    REJECTED_WISH_RESP=$(curl -sL -X POST "$BASE_URL/child/wishes" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer $CHILD1_TOKEN" \
      -d '{"name":"昂贵玩具","description":"太贵了","emoji":"🎮","priority":"high"}')
    REJECTED_WISH_ID=$(echo "$REJECTED_WISH_RESP" | jq -r '.data.id // .id')
    curl -sL -X POST "$BASE_URL/family/child-wishes/$REJECTED_WISH_ID/reject" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer $TOKEN" \
      -d '{"rejection_reason":"太贵了，等攒更多星星币再说"}' > /dev/null
    log_ok "拒绝心愿: 小宝 - 昂贵玩具 (rejected)"

    # 3. active 状态（已批准）
    ACTIVE_WISH_RESP=$(curl -sL -X POST "$BASE_URL/child/wishes" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer $CHILD2_TOKEN" \
      -d '{"name":"新耳机","description":"无线蓝牙耳机","emoji":"🎧","priority":"medium"}')
    ACTIVE_WISH_ID=$(echo "$ACTIVE_WISH_RESP" | jq -r '.data.id // .id')
    curl -sL -X POST "$BASE_URL/family/child-wishes/$ACTIVE_WISH_ID/approve" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer $TOKEN" \
      -d '{"star_coin_cost":80}' > /dev/null
    log_ok "批准心愿: 大宝 - 新耳机 (active, cost=80)"

    # 4. redemption_requested 状态（兑换请求）
    REDEMPT_WISH_RESP=$(curl -sL -X POST "$BASE_URL/child/wishes" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer $CHILD2_TOKEN" \
      -d '{"name":"漫画书","description":"一套漫画","emoji":"📚","priority":"low"}')
    REDEMPT_WISH_ID=$(echo "$REDEMPT_WISH_RESP" | jq -r '.data.id // .id')
    curl -sL -X POST "$BASE_URL/family/child-wishes/$REDEMPT_WISH_ID/approve" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer $TOKEN" \
      -d '{"star_coin_cost":30}' > /dev/null
    # 请求兑换
    curl -sL -X POST "$BASE_URL/child/wishes/$REDEMPT_WISH_ID/request-redemption" \
      -H "Authorization: Bearer $CHILD2_TOKEN" > /dev/null
    log_ok "兑换请求: 大宝 - 漫画书 (redemption_requested, cost=30)"

    # 5. realized 状态（已实现）
    REALIZED_CHILD_WISH_RESP=$(curl -sL -X POST "$BASE_URL/child/wishes" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer $CHILD1_TOKEN" \
      -d '{"name":"小背包","description":"上学用","emoji":"🎒","priority":"medium"}')
    REALIZED_CHILD_WISH_ID=$(echo "$REALIZED_CHILD_WISH_RESP" | jq -r '.data.id // .id')
    curl -sL -X POST "$BASE_URL/family/child-wishes/$REALIZED_CHILD_WISH_ID/approve" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer $TOKEN" \
      -d '{"star_coin_cost":40}' > /dev/null
    curl -sL -X POST "$BASE_URL/child/wishes/$REALIZED_CHILD_WISH_ID/request-redemption" \
      -H "Authorization: Bearer $CHILD1_TOKEN" > /dev/null
    # 家长确认实现
    curl -sL -X POST "$BASE_URL/family/child-wishes/$REALIZED_CHILD_WISH_ID/realize" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer $TOKEN" \
      -d '{}' > /dev/null
    log_ok "已实现心愿: 小宝 - 小背包 (realized, cost=40)"

    # 兄弟间赠送星星币
    curl -sL -X POST "$BASE_URL/family/coins/gift" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer $TOKEN" \
      -d "{\"to_child_id\":\"$CHILD1_ID\",\"amount\":10,\"emoji_reason\":\"🎁\"}" > /dev/null
    log_ok "赠送: 大宝 -> 小宝 10 星星币"

    # 创建家务模板（每日 + 每周）
    TPL1_RESP=$(curl -sL -X POST "$BASE_URL/family/chore-templates" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer $TOKEN" \
      -d '{
        "name": "整理房间",
        "emoji": "🧹",
        "coin_reward": 5,
        "frequency": "daily",
        "assignment_type": "pool"
      }')
    TPL1_ID=$(echo "$TPL1_RESP" | jq -r '.data.id // .id')
    log_ok "创建家务模板: 整理房间 (每日)"

    TPL2_RESP=$(curl -sL -X POST "$BASE_URL/family/chore-templates" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer $TOKEN" \
      -d '{
        "name": "洗碗",
        "emoji": "🍽️",
        "coin_reward": 8,
        "frequency": "daily",
        "assignment_type": "pool"
      }')
    TPL2_ID=$(echo "$TPL2_RESP" | jq -r '.data.id // .id')
    log_ok "创建家务模板: 洗碗 (每日)"

    # 每周家务模板
    TPL3_RESP=$(curl -sL -X POST "$BASE_URL/family/chore-templates" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer $TOKEN" \
      -d '{
        "name": "打扫卫生间",
        "emoji": "🚿",
        "coin_reward": 15,
        "frequency": "weekly",
        "assignment_type": "pool"
      }')
    TPL3_ID=$(echo "$TPL3_RESP" | jq -r '.data.id // .id')
    log_ok "创建家务模板: 打扫卫生间 (每周)"

    # 任务跨天场景：获取昨日、今日、明日家务实例
    if date -v-1d >/dev/null 2>&1; then
      YESTERDAY=$(date -v-1d +%Y-%m-%d)
      TOMORROW=$(date -v+1d +%Y-%m-%d)
    else
      YESTERDAY=$(date -d "yesterday" +%Y-%m-%d)
      TOMORROW=$(date -d "tomorrow" +%Y-%m-%d)
    fi
    TODAY=$(date +%Y-%m-%d)

    # 昨日任务 (完成并审批)
    CHORES_YEST=$(curl -sL -X GET "$BASE_URL/child/chores?date=$YESTERDAY" -H "Authorization: Bearer $CHILD2_TOKEN")
    INST_YEST=$(echo "$CHORES_YEST" | jq -r '.data[0].id // empty')
    STATUS_YEST=$(echo "$CHORES_YEST" | jq -r '.data[0].status // empty')
    if [ -n "$INST_YEST" ] && [ "$STATUS_YEST" = "available" ]; then
      curl -sL -X POST "$BASE_URL/child/chores/$INST_YEST/complete" -H "Authorization: Bearer $CHILD2_TOKEN" > /dev/null
      curl -sL -X POST "$BASE_URL/family/chore-approvals/$INST_YEST/approve" -H "Authorization: Bearer $TOKEN" > /dev/null
      log_ok "大宝完成昨日家务: 已审批"
    fi

    # 今日任务 (仅完成待审批)
    CHORES2=$(curl -sL -X GET "$BASE_URL/child/chores?date=$TODAY" \
      -H "Authorization: Bearer $CHILD2_TOKEN")
    INSTANCE_ID=$(echo "$CHORES2" | jq -r '.data[0].id // empty')
    STATUS_TODAY=$(echo "$CHORES2" | jq -r '.data[0].status // empty')

    if [ -n "$INSTANCE_ID" ] && [ "$STATUS_TODAY" = "available" ]; then
      curl -sL -X POST "$BASE_URL/child/chores/$INSTANCE_ID/complete" \
        -H "Authorization: Bearer $CHILD2_TOKEN" > /dev/null
      log_ok "大宝完成今日家务: 待审批"
    else
      log_ok "家务实例暂无（今日已处理或未分配）"
    fi

    # 触发生成明日任务
    curl -sL -X GET "$BASE_URL/child/chores?date=$TOMORROW" -H "Authorization: Bearer $CHILD2_TOKEN" > /dev/null
  fi

  # ═══════════════════════════════════════════
  # 2.9 盲盒数据（demouser）
  # ═══════════════════════════════════════════
  log_info "创建盲盒数据..."

  DEMO_GIFTS_RESP=$(curl -sL "$BASE_URL/blind-box/gifts" -H "Authorization: Bearer $TOKEN")
  DEMO_GIFT_COUNT=$(echo "$DEMO_GIFTS_RESP" | jq -r 'if type == "array" then length elif (.data | type) == "array" then .data | length else 0 end' 2>/dev/null || echo "0")

  if [ "$DEMO_GIFT_COUNT" = "0" ]; then
    # 启用盲盒，调整概率
    curl -sL -X PUT "$BASE_URL/blind-box/config" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer $TOKEN" \
      -d '{"enabled":true,"base_draw_prob":0.4,"special_day_prob":0.85,"surprise_prob_normal":0.1,"surprise_prob_parent_bday":0.7,"weight_scale":2.0,"surprise_threshold_coins":100}' > /dev/null
    log_ok "demouser: 盲盒配置已启用"

    # 礼物池（8 个，覆盖全部 value_score 档位）
    DG1=$(curl -sL -X POST "$BASE_URL/blind-box/gifts" \
      -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" \
      -d '{"name":"糖果一包","emoji":"🍬","value_score":1,"description":"各种口味糖果"}' | jq -r '.id // .data.id')
    log_ok "创建礼物: 糖果一包 (score=1)"

    DG2=$(curl -sL -X POST "$BASE_URL/blind-box/gifts" \
      -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" \
      -d '{"name":"贴纸套装","emoji":"🎨","value_score":2,"description":"卡通贴纸 50 张"}' | jq -r '.id // .data.id')
    log_ok "创建礼物: 贴纸套装 (score=2)"

    DG3=$(curl -sL -X POST "$BASE_URL/blind-box/gifts" \
      -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" \
      -d '{"name":"绘本一册","emoji":"📖","value_score":3,"description":"精选儿童绘本"}' | jq -r '.id // .data.id')
    log_ok "创建礼物: 绘本一册 (score=3)"

    DG4=$(curl -sL -X POST "$BASE_URL/blind-box/gifts" \
      -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" \
      -d '{"name":"小玩具","emoji":"🧸","value_score":4,"description":"随机小玩具"}' | jq -r '.id // .data.id')
    log_ok "创建礼物: 小玩具 (score=4)"

    DG5=$(curl -sL -X POST "$BASE_URL/blind-box/gifts" \
      -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" \
      -d '{"name":"冰淇淋券","emoji":"🍦","value_score":5,"description":"哈根达斯双人券"}' | jq -r '.id // .data.id')
    log_ok "创建礼物: 冰淇淋券 (score=5)"

    DG6=$(curl -sL -X POST "$BASE_URL/blind-box/gifts" \
      -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" \
      -d '{"name":"乐高小套装","emoji":"🧱","value_score":7,"description":"乐高经典系列 60 片"}' | jq -r '.id // .data.id')
    log_ok "创建礼物: 乐高小套装 (score=7, 惊喜档)"

    DG7=$(curl -sL -X POST "$BASE_URL/blind-box/gifts" \
      -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" \
      -d '{"name":"游乐园门票","emoji":"🎡","value_score":9,"description":"亲子游乐园一日票"}' | jq -r '.id // .data.id')
    log_ok "创建礼物: 游乐园门票 (score=9, 惊喜档)"

    DG8=$(curl -sL -X POST "$BASE_URL/blind-box/gifts" \
      -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" \
      -d '{"name":"Switch 游戏卡","emoji":"🎮","value_score":10,"description":"任天堂 Switch 游戏一张"}' | jq -r '.id // .data.id')
    log_ok "创建礼物: Switch 游戏卡 (score=10, 惊喜档)"

    # 从儿童心愿转入礼物池
    DEMO_CHILD_WISHES=$(curl -sL "$BASE_URL/family/child-wishes" -H "Authorization: Bearer $TOKEN" 2>/dev/null || echo "{}")
    DEMO_WISH_FOR_GIFT=$(echo "$DEMO_CHILD_WISHES" | jq -r '[.data[] // .[] | select(.status=="active")] | .[0].id // empty' 2>/dev/null | head -1)
    if [ -n "$DEMO_WISH_FOR_GIFT" ] && [ "$DEMO_WISH_FOR_GIFT" != "null" ]; then
      curl -sL -X POST "$BASE_URL/blind-box/gifts/from-wish/$DEMO_WISH_FOR_GIFT" \
        -H "Authorization: Bearer $TOKEN" > /dev/null
      log_ok "demouser: 从心愿转入礼物池 (wish_id=$DEMO_WISH_FOR_GIFT)"
    fi

    # 为小宝创建 bonus_draw（available — 可直接使用）
    NEXT_MONTH_DEMO=$(date -v+30d +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -d "+30 days" +%Y-%m-%dT%H:%M:%SZ)
    curl -sL -X POST "$BASE_URL/blind-box/bonus-draws" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer $TOKEN" \
      -d "{\"child_user_id\":\"$CHILD1_ID\",\"expires_at\":\"$NEXT_MONTH_DEMO\"}" > /dev/null 2>&1 || true
    curl -sL -X POST "$BASE_URL/blind-box/bonus-draws" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer $TOKEN" \
      -d "{\"child_user_id\":\"$CHILD1_ID\",\"expires_at\":\"$NEXT_MONTH_DEMO\"}" > /dev/null 2>&1 || true
    log_ok "demouser: 为小宝创建 2 个 bonus_draw（available）"

    # 为大宝创建 bonus_draw（available）
    curl -sL -X POST "$BASE_URL/blind-box/bonus-draws" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer $TOKEN" \
      -d "{\"child_user_id\":\"$CHILD2_ID\",\"expires_at\":\"$NEXT_MONTH_DEMO\"}" > /dev/null 2>&1 || true
    log_ok "demouser: 为大宝创建 1 个 bonus_draw（available）"

    # 大宝使用一次 bonus_draw（产生 draw 历史记录）
    if [ -n "$CHILD2_TOKEN" ] && [ "$CHILD2_TOKEN" != "null" ]; then
      BONUS_LIST=$(curl -sL "$BASE_URL/child/blind-box/bonus-draws" -H "Authorization: Bearer $CHILD2_TOKEN")
      BONUS_ID=$(echo "$BONUS_LIST" | jq -r '[(.data // .) | if type=="array" then .[] else empty end | select(.status=="available")] | .[0].id // empty' 2>/dev/null | head -1)
      if [ -n "$BONUS_ID" ] && [ "$BONUS_ID" != "null" ]; then
        DRAW_RESP=$(curl -sL -X POST "$BASE_URL/child/blind-box/bonus-draws/$BONUS_ID/use" \
          -H "Authorization: Bearer $CHILD2_TOKEN")
        DRAW_ID=$(echo "$DRAW_RESP" | jq -r '.id // .data.id')
        log_ok "demouser: 大宝使用 bonus_draw，获得抽奖记录 (draw_id=$DRAW_ID)"

        # 父母 fulfill 这条 draw（pending_fulfillment → fulfilled）
        if [ -n "$DRAW_ID" ] && [ "$DRAW_ID" != "null" ]; then
          curl -sL -X PUT "$BASE_URL/blind-box/draws/$DRAW_ID/fulfill" \
            -H "Authorization: Bearer $TOKEN" > /dev/null
          log_ok "demouser: 父母已兑现抽奖 (draw_id=$DRAW_ID, status=fulfilled)"
        fi
      fi
    fi

    log_ok "demouser: 盲盒礼物池就绪（8 个礼物 + draw 历史）"
  else
    log_info "demouser 盲盒礼物池已有 $DEMO_GIFT_COUNT 个礼物，跳过"
  fi

  log_ok "========== Part 2: 完整仿真数据完成 =========="
fi

# ========================================
# 显示统计
# ========================================
echo ""
echo "=========================================="
echo "  数据统计"
echo "=========================================="

# 固定测试账号统计
echo ""
echo "固定测试账号:"
echo "  - test_empty        (空家庭)"
echo "  - test_asset        (5 资产: in_use/idle/retired/USD/已售出)"
echo "  - test_rich         (31 资产 + 28 负债 + 29 心愿 + 负债关联 + 心愿多状态)"
echo "  - test_rich_member  (test_rich 家庭的 member 角色 + 数据隔离测试)"
echo "  - test_child        (test_rich 家庭的儿童 + 跨天家务 + 盲盒礼物池 + bonus_draw)"

if [[ "$SKIP_DEMO" == false ]]; then
  echo ""
  echo "完整仿真数据 (demouser):"
  curl -sL -X GET "$BASE_URL/dashboard/overview" \
    -H "Authorization: Bearer $TOKEN" | jq -r '
    "  总资产价值: ¥\(.data.total_assets | floor | . / 10000 | floor)万",
    "  总负债: ¥\(.data.total_liabilities | floor | . / 10000 | floor)万",
    "  净资产: ¥\(.data.net_worth | floor | . / 10000 | floor)万"
    '

  echo ""
  echo "资产数量:"
  PHYSICAL_COUNT=$(curl -sL -X GET "$BASE_URL/assets?asset_type=physical" \
    -H "Authorization: Bearer $TOKEN" | jq '.data | length')
  FINANCIAL_COUNT=$(curl -sL -X GET "$BASE_URL/assets?asset_type=financial" \
    -H "Authorization: Bearer $TOKEN" | jq '.data | length')
  LIABILITY_COUNT=$(curl -sL -X GET "$BASE_URL/liabilities" \
    -H "Authorization: Bearer $TOKEN" | jq '.data | length')
  WISH_COUNT=$(curl -sL -X GET "$BASE_URL/wishes" \
    -H "Authorization: Bearer $TOKEN" | jq '.data | length')

  echo "  实物资产: $PHYSICAL_COUNT 项"
  echo "  金融资产: $FINANCIAL_COUNT 项"
  echo "  负债: $LIABILITY_COUNT 项"
  echo "  心愿: $WISH_COUNT 项"
fi

echo ""
echo "=========================================="
echo "  所有测试数据创建完成！"
echo "=========================================="