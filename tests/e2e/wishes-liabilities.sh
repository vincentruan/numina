#!/bin/bash

# 心愿和负债仿真测试脚本
# 测试场景：
# 1. 心愿录入（全字段）
# 2. 负债录入（全字段，包括关联资产）
# 3. 列表展示功能验证

set -e

# 配置
BASE_URL="http://localhost/api/v1"
TOKEN=""

# 颜色输出
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 辅助函数
log_success() {
    echo -e "${GREEN}✓ $1${NC}" >&2
}

log_error() {
    echo -e "${RED}✗ $1${NC}" >&2
}

log_info() {
    echo -e "${YELLOW}ℹ $1${NC}" >&2
}

# 辅助函数：解包 API 响应信封
json_value() {
    local input="$1"
    local path="$2"
    local has_envelope
    has_envelope=$(echo "$input" | jq -r 'if has("data") then "yes" else "no" end' 2>/dev/null)
    if [ "$has_envelope" = "yes" ]; then
        echo "$input" | jq -r ".data | $path" 2>/dev/null | sed 's/^null$//'
    else
        echo "$input" | jq -r "$path" 2>/dev/null | sed 's/^null$//'
    fi
}

# 检查响应状态
check_response() {
    local response=$1
    local expected_status=$2
    local description=$3

    # 检查是否有错误字段（detail 通常表示错误）
    local error=$(echo "$response" | jq -r '.detail // empty')

    if [ -n "$error" ]; then
        log_error "$description - 错误: $error"
        echo "$response" | jq '.'
        return 1
    else
        log_success "$description"
        return 0
    fi
}

# 注册或登录获取 token
get_token() {
    log_info "尝试登录..."

    local login_response=$(curl -sL -X POST "$BASE_URL/auth/login" \
        -H "Content-Type: application/json" \
        -d '{
            "username": "demouser",
            "password": "DemoPass123"
        }')

    TOKEN=$(echo "$login_response" | jq -r 'if has("data") then .data.access_token else .access_token end')

    # 如果登录失败，尝试注册
    if [ -z "$TOKEN" ] || [ "$TOKEN" = "null" ]; then
        log_info "用户不存在，正在注册..."

        local register_response=$(curl -sL -X POST "$BASE_URL/auth/register" \
            -H "Content-Type: application/json" \
            -d '{
                "username": "demouser",
                "display_name": "Demo User",
                "password": "DemoPass123",
                "family_name": "Demo Family"
            }')

        TOKEN=$(echo "$register_response" | jq -r 'if has("data") then .data.access_token else .access_token end')

        if [ -z "$TOKEN" ] || [ "$TOKEN" = "null" ]; then
            log_error "注册失败"
            echo "$register_response" | jq '.'
            exit 1
        fi

        log_success "注册成功"
    else
        log_success "登录成功"
    fi
}

# 获取分类 ID（用于心愿关联）
get_category_id() {
    local asset_type=$1
    local response=$(curl -sL -X GET "$BASE_URL/categories?asset_type=$asset_type" \
        -H "Authorization: Bearer $TOKEN")

    echo "$response" | jq -r 'if has("data") then .data[0].id else .[0].id end'
}

# 创建资产（用于负债关联）
create_test_asset() {
    log_info "创建测试资产（用于负债关联）..."

    local category_id=$(get_category_id "physical")

    local response=$(curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{
            \"name\": \"测试房产\",
            \"asset_type\": \"physical\",
            \"category_id\": \"$category_id\",
            \"purchase_price\": 3000000,
            \"current_value\": 3500000,
            \"purchase_date\": \"2020-01-01\",
            \"usage_frequency\": \"daily\",
            \"expected_lifespan_days\": 18250,
            \"annual_maintenance_cost\": 10000
        }")

    local asset_id=$(echo "$response" | jq -r 'if has("data") then .data.id else .id end')

    if [ -z "$asset_id" ] || [ "$asset_id" = "null" ]; then
        log_error "创建测试资产失败"
        echo "$response" | jq '.' >&2
        exit 1
    fi

    log_success "创建测试资产成功: $asset_id"
    echo "$asset_id"
}

# ============================================
# 测试 1: 心愿录入（全字段）
# ============================================
test_wish_creation() {
    echo ""
    log_info "========== 测试 1: 心愿录入（全字段） =========="

    local category_id=$(get_category_id "physical")

    # 测试用例 1: 完整字段心愿
    log_info "创建心愿 1: 换新房（完整字段）"
    local wish1=$(curl -sL -X POST "$BASE_URL/wishes" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{
            \"name\": \"换新房\",
            \"description\": \"在市中心购买一套三室两厅的房子，靠近地铁站，周边配套设施齐全\",
            \"expected_price\": 5000000,
            \"priority\": \"high\",
            \"category_id\": \"$category_id\"
        }")

    check_response "$wish1" 201 "创建心愿 1"
    local wish1_id=$(echo "$wish1" | jq -r 'if has("data") then .data.id else .id end')

    # 测试用例 2: 最小字段心愿
    log_info "创建心愿 2: 换手机（最小字段）"
    local wish2=$(curl -sL -X POST "$BASE_URL/wishes" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d '{
            "name": "换手机"
        }')

    check_response "$wish2" 201 "创建心愿 2"

    # 测试用例 3: 中等优先级心愿
    log_info "创建心愿 3: 出国旅游（中等优先级）"
    local wish3=$(curl -sL -X POST "$BASE_URL/wishes" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d '{
            "name": "出国旅游",
            "description": "去欧洲旅游两周，游览法国、意大利、瑞士",
            "expected_price": 50000,
            "priority": "medium"
        }')

    check_response "$wish3" 201 "创建心愿 3"

    # 测试用例 4: 低优先级心愿
    log_info "创建心愿 4: 买相机（低优先级）"
    local wish4=$(curl -sL -X POST "$BASE_URL/wishes" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d '{
            "name": "买相机",
            "description": "索尼 A7M4 全画幅微单相机",
            "expected_price": 20000,
            "priority": "low"
        }')

    check_response "$wish4" 201 "创建心愿 4"

    # 测试用例 5: 买新车
    log_info "创建心愿 5: 买新车"
    local wish5=$(curl -sL -X POST "$BASE_URL/wishes" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d '{
            "name": "买新车",
            "description": "特斯拉 Model 3 或比亚迪汉 EV",
            "expected_price": 300000,
            "priority": "high"
        }')

    check_response "$wish5" 201 "创建心愿 5"

    log_success "心愿录入测试完成"
    echo "$wish1_id"
}

# ============================================
# 测试 2: 负债录入（全字段）
# ============================================
test_liability_creation() {
    echo ""
    log_info "========== 测试 2: 负债录入（全字段） =========="

    local asset_id=$1

    # 测试用例 1: 房贷（完整字段，关联资产）
    log_info "创建负债 1: 房贷（完整字段 + 关联资产）"
    local json_data=$(printf '{"category":"mortgage","name":"深圳湾一号房贷","original_amount":2000000,"remaining_amount":1500000,"monthly_payment":12000,"interest_rate":4.9,"start_date":"2020-01-01","end_date":"2040-01-01","institution":"中国工商银行","linked_asset_id":"%s","notes":"20年期商业贷款，等额本息还款"}' "$asset_id")
    local liability1=$(curl -sL -X POST "$BASE_URL/liabilities" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "$json_data")

    check_response "$liability1" 201 "创建负债 1"
    local liability1_id=$(echo "$liability1" | jq -r 'if has("data") then .data.id else .id end')

    # 测试用例 2: 车贷（完整字段）
    log_info "创建负债 2: 车贷（完整字段）"
    local liability2=$(curl -sL -X POST "$BASE_URL/liabilities" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d '{
            "category": "car_loan",
            "name": "宝马X5车贷",
            "original_amount": 300000,
            "remaining_amount": 180000,
            "monthly_payment": 8000,
            "interest_rate": 5.5,
            "start_date": "2022-06-01",
            "end_date": "2025-06-01",
            "institution": "招商银行",
            "notes": "3年期车贷，等额本息"
        }')

    check_response "$liability2" 201 "创建负债 2"

    # 测试用例 3: 信用卡（部分字段）
    log_info "创建负债 3: 信用卡（部分字段）"
    local liability3=$(curl -sL -X POST "$BASE_URL/liabilities" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d '{
            "category": "credit_card",
            "name": "招商信用卡",
            "original_amount": 50000,
            "remaining_amount": 30000,
            "monthly_payment": 3000,
            "interest_rate": 18.0,
            "institution": "招商银行"
        }')

    check_response "$liability3" 201 "创建负债 3"

    # 测试用例 4: 个人贷款
    log_info "创建负债 4: 个人贷款"
    local liability4=$(curl -sL -X POST "$BASE_URL/liabilities" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d '{
            "category": "personal_loan",
            "name": "装修贷款",
            "original_amount": 200000,
            "remaining_amount": 150000,
            "monthly_payment": 5000,
            "interest_rate": 6.0,
            "start_date": "2023-01-01",
            "end_date": "2026-01-01",
            "institution": "中国建设银行",
            "notes": "3年期装修贷款"
        }')

    check_response "$liability4" 201 "创建负债 4"

    # 测试用例 5: 其他负债（最小字段）
    log_info "创建负债 5: 其他负债（最小字段）"
    local liability5=$(curl -sL -X POST "$BASE_URL/liabilities" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d '{
            "category": "other",
            "name": "亲友借款",
            "original_amount": 30000,
            "remaining_amount": 20000,
            "monthly_payment": 2000,
            "interest_rate": 0
        }')

    check_response "$liability5" 201 "创建负债 5"

    log_success "负债录入测试完成"
    echo "$liability1_id"
}

# ============================================
# 测试 3: 列表展示功能验证
# ============================================
test_list_display() {
    echo ""
    log_info "========== 测试 3: 列表展示功能验证 =========="

    # 测试 3.1: 心愿列表（全部）
    log_info "测试 3.1: 获取全部心愿列表"
    local all_wishes=$(curl -sL -X GET "$BASE_URL/wishes" \
        -H "Authorization: Bearer $TOKEN")

    local wish_count=$(echo "$all_wishes" | jq 'if has("data") then .data | length else length end')
    log_success "获取到 $wish_count 条心愿记录"

    # 测试 3.2: 心愿列表（按状态筛选）
    log_info "测试 3.2: 获取待实现心愿列表"
    local pending_wishes=$(curl -sL -X GET "$BASE_URL/wishes?status=pending" \
        -H "Authorization: Bearer $TOKEN")

    local pending_count=$(echo "$pending_wishes" | jq 'if has("data") then .data | length else length end')
    log_success "获取到 $pending_count 条待实现心愿"

    # 测试 3.3: 负债列表（全部）
    log_info "测试 3.3: 获取全部负债列表"
    local all_liabilities=$(curl -sL -X GET "$BASE_URL/liabilities" \
        -H "Authorization: Bearer $TOKEN")

    local liability_count=$(echo "$all_liabilities" | jq 'if has("data") then .data | length else length end')
    log_success "获取到 $liability_count 条负债记录"

    # 测试 3.4: 负债列表（仅活跃）
    log_info "测试 3.4: 获取活跃负债列表"
    local active_liabilities=$(curl -sL -X GET "$BASE_URL/liabilities?is_active=true" \
        -H "Authorization: Bearer $TOKEN")

    local active_count=$(echo "$active_liabilities" | jq 'if has("data") then .data | length else length end')
    log_success "获取到 $active_count 条活跃负债"

    # 测试 3.5: 负债列表（仅已还清）
    log_info "测试 3.5: 获取已还清负债列表"
    local inactive_liabilities=$(curl -sL -X GET "$BASE_URL/liabilities?is_active=false" \
        -H "Authorization: Bearer $TOKEN")

    local inactive_count=$(echo "$inactive_liabilities" | jq 'if has("data") then .data | length else length end')
    log_success "获取到 $inactive_count 条已还清负债"

    # 显示详细信息
    echo ""
    log_info "========== 心愿列表详情 =========="
    echo "$all_wishes" | jq -r 'if has("data") then .data[] else .[] end | "[\(.priority)] \(.name) - ¥\(.expected_price // 0) - \(.status)"'

    echo ""
    log_info "========== 负债列表详情 =========="
    echo "$all_liabilities" | jq -r 'if has("data") then .data[] else .[] end | "[\(.category)] \(.name) - 剩余: ¥\(.remaining_amount) / 总额: ¥\(.original_amount) - \(if .is_active then "活跃" else "已还清" end)"'

    log_success "列表展示功能验证完成"
}

# ============================================
# 测试 4: 心愿实现功能
# ============================================
test_wish_realization() {
    echo ""
    log_info "========== 测试 4: 心愿实现功能 =========="

    local wish_id=$1
    local category_id=$(get_category_id "physical")

    log_info "实现心愿: $wish_id"
    local response=$(curl -sL -X POST "$BASE_URL/wishes/$wish_id/realize" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{
            \"purchase_price\": 4800000,
            \"purchase_date\": \"2024-03-20\",
            \"category_id\": \"$category_id\"
        }")

    check_response "$response" 201 "心愿实现"

    local asset_id=$(echo "$response" | jq -r 'if has("data") then .data.id else .id end')
    log_success "心愿已实现，创建资产: $asset_id"
}

# ============================================
# 测试 5: 负债还款功能
# ============================================
test_liability_payment() {
    echo ""
    log_info "========== 测试 5: 负债还款功能 =========="

    local liability_id=$1

    log_info "记录还款: $liability_id"
    local response=$(curl -sL -X PUT "$BASE_URL/liabilities/$liability_id/payment" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d '{
            "amount": 50000
        }')

    check_response "$response" 200 "记录还款"

    local remaining=$(echo "$response" | jq -r 'if has("data") then .data.remaining_amount else .remaining_amount end')
    log_success "还款成功，剩余金额: ¥$remaining"
}

# ============================================
# 主流程
# ============================================
main() {
    echo ""
    log_info "=========================================="
    log_info "  心愿和负债仿真测试"
    log_info "=========================================="

    # 获取 token
    get_token

    # 创建测试资产
    asset_id=$(create_test_asset)

    # 测试 1: 心愿录入
    wish_id=$(test_wish_creation)

    # 测试 2: 负债录入
    liability_id=$(test_liability_creation "$asset_id")

    # 测试 3: 列表展示
    test_list_display

    # 测试 4: 心愿实现
    test_wish_realization "$wish_id"

    # 测试 5: 负债还款
    test_liability_payment "$liability_id"

    echo ""
    log_success "=========================================="
    log_success "  所有测试完成！"
    log_success "=========================================="
}

# 运行主流程
main
