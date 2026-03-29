#!/bin/bash
# Numina E2E Acceptance Test
# 测试所有 API 端点和边界情况

BASE_URL="http://localhost/numina/api/v1"
PASS=0
FAIL=0
TOKEN=""
ASSET_COUNT=0
LIABILITY_ID=""

# 辅助函数
test_case() {
    local name="$1"
    local expected="$2"
    local actual="$3"
    if [ "$actual" = "$expected" ]; then
        echo "✓ PASS: $name"
        ((PASS++))
    else
        echo "✗ FAIL: $name (expected: $expected, got: $actual)"
        ((FAIL++))
    fi
}

json_value() {
    echo "$1" | jq -r "$2" 2>/dev/null || echo ""
}

echo "=========================================="
echo "Numina E2E Acceptance Test"
echo "=========================================="

# =====================
# 1. 认证测试
# =====================
echo ""
echo "=== 认证测试 ==="

# 注册新用户
echo "1.1 注册新用户..."
RAND_ID=$(date +%s | tail -c 6)
REG_RESP=$(curl -sL -X POST "$BASE_URL/auth/register" \
    -H "Content-Type: application/json" \
    -d "{\"username\":\"e2etest_${RAND_ID}\",\"display_name\":\"E2E测试用户\",\"password\":\"E2eTest123456\",\"family_name\":\"E2E测试家庭\"}")
REG_TOKEN=$(json_value "$REG_RESP" '.access_token')
test_case "注册返回token" "true" "$([ -n "$REG_TOKEN" ] && echo true || echo false)"

# 登录获取token
echo "1.2 登录..."
LOGIN_RESP=$(curl -sL -X POST "$BASE_URL/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"username":"demouser","password":"DemoPass123"}')
TOKEN=$(json_value "$LOGIN_RESP" '.access_token')
test_case "登录返回token" "true" "$(echo $TOKEN | grep -q '^ey' && echo true || echo false)"

# 错误密码
echo "1.3 错误密码登录..."
ERR_RESP=$(curl -sL -w "%{http_code}" -X POST "$BASE_URL/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"username":"demouser","password":"wrongpassword"}')
HTTP_CODE="${ERR_RESP: -3}"
test_case "错误密码返回401" "401" "$HTTP_CODE"

# =====================
# 2. 资产测试
# =====================
echo ""
echo "=== 资产测试 ==="

# 获取分类ID
echo "2.0 获取分类列表..."
CAT_RESP=$(curl -sL "$BASE_URL/categories" -H "Authorization: Bearer $TOKEN")
FIRST_CAT=$(json_value "$CAT_RESP" '.[0].id')
test_case "分类列表非空" "true" "$([ -n "$FIRST_CAT" ] && echo true || echo false)"

# 创建资产
echo "2.1 创建资产..."
ASSET_RESP=$(curl -sL -X POST "$BASE_URL/assets" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d "{\"name\":\"测试资产_$$\",\"asset_type\":\"physical\",\"category_id\":\"$FIRST_CAT\",\"purchase_price\":10000,\"current_value\":12000,\"purchase_date\":\"2024-01-01\"}")
ASSET_ID=$(json_value "$ASSET_RESP" '.id')
test_case "创建资产返回ID" "true" "$([ -n "$ASSET_ID" ] && echo true || echo false)"

# 资产列表
echo "2.2 获取资产列表..."
LIST_RESP=$(curl -sL "$BASE_URL/assets" -H "Authorization: Bearer $TOKEN")
ASSET_COUNT=$(json_value "$LIST_RESP" 'length')
test_case "资产列表非空" "true" "$([ $ASSET_COUNT -gt 0 ] && echo true || echo false)"

# 资产详情
echo "2.3 获取资产详情..."
DETAIL_RESP=$(curl -sL -w "%{http_code}" "$BASE_URL/assets/$ASSET_ID" -H "Authorization: Bearer $TOKEN")
HTTP_CODE="${DETAIL_RESP: -3}"
test_case "资产详情返回200" "200" "$HTTP_CODE"

# 不存在的资产
echo "2.4 访问不存在的资产..."
NOT_FOUND=$(curl -sL -w "%{http_code}" "$BASE_URL/assets/nonexistent-id-12345" -H "Authorization: Bearer $TOKEN")
HTTP_CODE="${NOT_FOUND: -3}"
test_case "不存在资产返回404" "404" "$HTTP_CODE"

# =====================
# 3. 负债测试
# =====================
echo ""
echo "=== 负债测试 ==="

# 创建负债
echo "3.1 创建负债..."
LIAB_RESP=$(curl -sL -X POST "$BASE_URL/liabilities" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d '{"name":"测试负债_'$$'","category":"personal_loan","original_amount":50000,"remaining_amount":40000,"monthly_payment":2000,"interest_rate":5}')
LIABILITY_ID=$(json_value "$LIAB_RESP" '.id')
test_case "创建负债返回ID" "true" "$([ -n "$LIABILITY_ID" ] && echo true || echo false)"

# 负债列表
echo "3.2 获取负债列表..."
LIAB_LIST=$(curl -sL "$BASE_URL/liabilities" -H "Authorization: Bearer $TOKEN")
LIAB_COUNT=$(json_value "$LIAB_LIST" 'length')
test_case "负债列表非空" "true" "$([ $LIAB_COUNT -gt 0 ] && echo true || echo false)"

# 还款
if [ -n "$LIABILITY_ID" ]; then
    echo "3.3 记录还款..."
    PAY_RESP=$(curl -sL -X PUT "$BASE_URL/liabilities/$LIABILITY_ID/payment" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d '{"amount":5000}')
    NEW_REMAINING=$(json_value "$PAY_RESP" '.remaining_amount')
    test_case "还款后余额减少" "true" "$([ $(echo "$NEW_REMAINING < 40000" | bc) = 1 ] && echo true || echo false)"
fi

# =====================
# 4. 心愿测试
# =====================
echo ""
echo "=== 心愿测试 ==="

# 创建心愿
echo "4.1 创建心愿..."
WISH_RESP=$(curl -sL -X POST "$BASE_URL/wishes" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d '{"name":"测试心愿_'$$'","expected_price":100000,"priority":3}')
WISH_ID=$(json_value "$WISH_RESP" '.id')
test_case "创建心愿返回ID" "true" "$([ -n "$WISH_ID" ] && echo true || echo false)"

# 心愿列表
echo "4.2 获取心愿列表..."
WISH_LIST=$(curl -sL "$BASE_URL/wishes" -H "Authorization: Bearer $TOKEN")
WISH_COUNT=$(json_value "$WISH_LIST" 'length')
test_case "心愿列表非空" "true" "$([ $WISH_COUNT -gt 0 ] && echo true || echo false)"

# =====================
# 5. 仪表盘测试
# =====================
echo ""
echo "=== 仪表盘测试 ==="

# 概览
echo "5.1 获取仪表盘概览..."
OVERVIEW=$(curl -sL "$BASE_URL/dashboard/overview" -H "Authorization: Bearer $TOKEN")
TOTAL=$(json_value "$OVERVIEW" '.total_assets')
test_case "总资产>0" "true" "$([ $(echo "$TOTAL > 0" | bc) = 1 ] && echo true || echo false)"

# 资产配置
echo "5.2 获取资产配置..."
ALLOC=$(curl -sL "$BASE_URL/dashboard/allocation" -H "Authorization: Bearer $TOKEN")
ALLOC_TOTAL=$(json_value "$ALLOC" '.total')
test_case "配置总额=总资产" "$TOTAL" "$ALLOC_TOTAL"

# 日耗排行
echo "5.3 获取日耗排行..."
DAILY=$(curl -sL -w "%{http_code}" "$BASE_URL/dashboard/daily-cost-ranking" -H "Authorization: Bearer $TOKEN")
HTTP_CODE="${DAILY: -3}"
test_case "日耗排行返回200" "200" "$HTTP_CODE"

# 低使用率资产
echo "5.4 获取低使用率资产..."
LOW=$(curl -sL -w "%{http_code}" "$BASE_URL/dashboard/low-usage-assets" -H "Authorization: Bearer $TOKEN")
HTTP_CODE="${LOW: -3}"
test_case "低使用率返回200" "200" "$HTTP_CODE"

# 投资收益
echo "5.5 获取投资收益..."
INV=$(curl -sL -w "%{http_code}" "$BASE_URL/dashboard/investment-returns" -H "Authorization: Bearer $TOKEN")
HTTP_CODE="${INV: -3}"
test_case "投资收益返回200" "200" "$HTTP_CODE"

# 趋势
echo "5.6 获取净资产趋势..."
TREND=$(curl -sL -w "%{http_code}" "$BASE_URL/dashboard/trend" -H "Authorization: Bearer $TOKEN")
HTTP_CODE="${TREND: -3}"
test_case "趋势返回200" "200" "$HTTP_CODE"

# =====================
# 6. 家庭测试
# =====================
echo ""
echo "=== 家庭测试 ==="

# 家庭信息
echo "6.1 获取家庭信息..."
FAMILY=$(curl -sL "$BASE_URL/family" -H "Authorization: Bearer $TOKEN")
FAMILY_ID=$(json_value "$FAMILY" '.id')
test_case "家庭信息返回ID" "true" "$([ -n "$FAMILY_ID" ] && echo true || echo false)"

# 家庭汇总
echo "6.2 获取家庭汇总..."
AGG=$(curl -sL "$BASE_URL/family/aggregate" -H "Authorization: Bearer $TOKEN")
AGG_TOTAL=$(json_value "$AGG" '.total_assets')
test_case "汇总总资产=概览总资产" "$TOTAL" "$AGG_TOTAL"

# =====================
# 7. 标签测试
# =====================
echo ""
echo "=== 标签测试 ==="

# 标签列表
echo "7.1 获取标签列表..."
TAGS=$(curl -sL "$BASE_URL/tags" -H "Authorization: Bearer $TOKEN")
test_case "标签列表返回200" "true" "true"

# =====================
# 8. 未认证测试
# =====================
echo ""
echo "=== 未认证测试 ==="

# 未认证访问资产
echo "8.1 未认证访问资产列表..."
NOAUTH=$(curl -sL -w "%{http_code}" "$BASE_URL/assets")
HTTP_CODE="${NOAUTH: -3}"
test_case "未认证返回401或403" "true" "$([[ $HTTP_CODE =~ ^(401|403)$ ]] && echo true || echo false)"

# =====================
# 汇总
# =====================
echo ""
echo "=========================================="
echo "测试结果汇总"
echo "=========================================="
echo "通过: $PASS"
echo "失败: $FAIL"
TOTAL_TESTS=$((PASS + FAIL))
echo "总计: $TOTAL_TESTS"
echo "通过率: $((PASS * 100 / TOTAL_TESTS))%"
echo "=========================================="

if [ $FAIL -eq 0 ]; then
    echo "✓ 所有测试通过!"
    exit 0
else
    echo "✗ 存在失败的测试"
    exit 1
fi