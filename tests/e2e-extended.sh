#!/bin/bash
# Numina E2E Extended Acceptance Test
# 补充覆盖：资产更新/删除/估值、负债详情/更新/删除、心愿更新/删除
# 分类CRUD、标签CRUD、家庭成员管理、邀请码重新生成、快照、活动日志、数据一致性

BASE_URL="http://localhost/numina/api/v1"
PASS=0
FAIL=0
TOKEN=""

# ── 辅助函数 ──────────────────────────────────────────────
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

http_code() {
    # 返回最后3位 HTTP 状态码
    echo "${1: -3}"
}

echo "=========================================="
echo "Numina E2E Extended Test"
echo "=========================================="

# ── 登录 ─────────────────────────────────────────────────
echo ""
echo "=== 登录 ==="
LOGIN_RESP=$(curl -sL -X POST "$BASE_URL/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"username":"uxtest","password":"Test123456"}')
TOKEN=$(json_value "$LOGIN_RESP" '.access_token')
test_case "登录获取token" "true" "$(echo $TOKEN | grep -q '^ey' && echo true || echo false)"

if [ -z "$TOKEN" ]; then
    echo "❌ 无法获取 Token，终止测试"
    exit 1
fi

# 获取分类ID（用于创建资产）
CAT_RESP=$(curl -sL "$BASE_URL/categories" -H "Authorization: Bearer $TOKEN")
FIRST_CAT=$(json_value "$CAT_RESP" '.[0].id')

# =====================
# 1. 资产更新 (ASSET-UPDATE)
# =====================
echo ""
echo "=== 资产更新测试 ==="

# 先创建一个资产用于后续测试
echo "1.0 创建测试资产..."
CREATE_RESP=$(curl -sL -X POST "$BASE_URL/assets" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d "{\"name\":\"扩展测试资产_$$\",\"asset_type\":\"physical\",\"category_id\":\"$FIRST_CAT\",\"purchase_price\":20000,\"current_value\":18000,\"purchase_date\":\"2023-06-01\"}")
TEST_ASSET_ID=$(json_value "$CREATE_RESP" '.id')
test_case "创建测试资产" "true" "$([ -n "$TEST_ASSET_ID" ] && echo true || echo false)"

# 更新资产名称和备注
echo "1.1 更新资产信息..."
UPDATE_RESP=$(curl -sL -X PUT "$BASE_URL/assets/$TEST_ASSET_ID" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d '{"name":"已更新的资产名称","notes":"这是更新后的备注"}')
UPDATED_NAME=$(json_value "$UPDATE_RESP" '.name')
test_case "资产名称更新成功" "已更新的资产名称" "$UPDATED_NAME"

# 更新资产估值
echo "1.2 更新资产估值..."
VAL_RESP=$(curl -sL -X PUT "$BASE_URL/assets/$TEST_ASSET_ID/value" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d '{"current_value":25000}')
NEW_VALUE=$(json_value "$VAL_RESP" '.current_value')
test_case "资产估值更新为25000" "25000.0" "$NEW_VALUE"

# 查看估值历史
echo "1.3 查看估值历史..."
VALUATION_RESP=$(curl -sL -w "%{http_code}" "$BASE_URL/assets/$TEST_ASSET_ID/valuations" \
    -H "Authorization: Bearer $TOKEN")
test_case "估值历史返回200" "200" "$(http_code "$VALUATION_RESP")"

# 退役资产
echo "1.4 退役资产..."
RETIRE_RESP=$(curl -sL -X POST "$BASE_URL/assets/$TEST_ASSET_ID/retire" \
    -H "Authorization: Bearer $TOKEN")
RETIRE_STATUS=$(json_value "$RETIRE_RESP" '.status')
test_case "退役后状态为retired" "retired" "$RETIRE_STATUS"

# 恢复资产
echo "1.5 恢复退役资产..."
REACTIVATE_RESP=$(curl -sL -X POST "$BASE_URL/assets/$TEST_ASSET_ID/reactivate" \
    -H "Authorization: Bearer $TOKEN")
REACTIVATE_STATUS=$(json_value "$REACTIVATE_RESP" '.status')
test_case "恢复后状态为in_use" "in_use" "$REACTIVATE_STATUS"

# 数据一致性：创建资产后仪表盘总额增加
echo "1.6 数据一致性验证（创建资产后总额增加）..."
BEFORE_OVERVIEW=$(curl -sL "$BASE_URL/dashboard/overview" -H "Authorization: Bearer $TOKEN")
BEFORE_TOTAL=$(json_value "$BEFORE_OVERVIEW" '.total_assets')

NEW_ASSET_RESP=$(curl -sL -X POST "$BASE_URL/assets" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d "{\"name\":\"一致性测试资产_$$\",\"asset_type\":\"physical\",\"category_id\":\"$FIRST_CAT\",\"purchase_price\":5000,\"current_value\":5000,\"purchase_date\":\"2024-01-01\"}")
CONSISTENCY_ASSET_ID=$(json_value "$NEW_ASSET_RESP" '.id')

AFTER_OVERVIEW=$(curl -sL "$BASE_URL/dashboard/overview" -H "Authorization: Bearer $TOKEN")
AFTER_TOTAL=$(json_value "$AFTER_OVERVIEW" '.total_assets')

INCREASED=$(echo "$AFTER_TOTAL > $BEFORE_TOTAL" | bc)
test_case "创建资产后仪表盘总额增加" "1" "$INCREASED"

# 归档（软删除）资产
echo "1.7 归档资产（DELETE）..."
ARCHIVE_RESP=$(curl -sL -w "%{http_code}" -X DELETE "$BASE_URL/assets/$TEST_ASSET_ID" \
    -H "Authorization: Bearer $TOKEN")
test_case "归档资产返回200" "200" "$(http_code "$ARCHIVE_RESP")"

# 验证归档后不在列表中
echo "1.8 验证归档资产不在列表中..."
ASSET_LIST=$(curl -sL "$BASE_URL/assets" -H "Authorization: Bearer $TOKEN")
ARCHIVED_IN_LIST=$(echo "$ASSET_LIST" | jq -r "[.[] | select(.id == \"$TEST_ASSET_ID\")] | length")
test_case "归档资产不在列表中" "0" "$ARCHIVED_IN_LIST"

# 清理一致性测试资产
curl -sL -X DELETE "$BASE_URL/assets/$CONSISTENCY_ASSET_ID" -H "Authorization: Bearer $TOKEN" > /dev/null

# =====================
# 2. 负债详情/更新/删除 (LIABILITY)
# =====================
echo ""
echo "=== 负债详情/更新/删除测试 ==="

# 创建测试负债
echo "2.0 创建测试负债..."
LIAB_CREATE=$(curl -sL -X POST "$BASE_URL/liabilities" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d "{\"name\":\"扩展测试负债_$$\",\"category\":\"personal_loan\",\"original_amount\":30000,\"remaining_amount\":30000,\"monthly_payment\":1500,\"interest_rate\":4.5}")
TEST_LIAB_ID=$(json_value "$LIAB_CREATE" '.id')
test_case "创建测试负债" "true" "$([ -n "$TEST_LIAB_ID" ] && echo true || echo false)"

# 负债详情
echo "2.1 获取负债详情..."
LIAB_DETAIL=$(curl -sL -w "%{http_code}" "$BASE_URL/liabilities/$TEST_LIAB_ID" \
    -H "Authorization: Bearer $TOKEN")
test_case "负债详情返回200" "200" "$(http_code "$LIAB_DETAIL")"

# 负债详情字段验证
LIAB_DETAIL_BODY=$(curl -sL "$BASE_URL/liabilities/$TEST_LIAB_ID" \
    -H "Authorization: Bearer $TOKEN")
LIAB_NAME=$(json_value "$LIAB_DETAIL_BODY" '.name')
test_case "负债详情名称正确" "true" "$([ -n "$LIAB_NAME" ] && echo true || echo false)"

# 更新负债
echo "2.2 更新负债信息..."
LIAB_UPDATE=$(curl -sL -X PUT "$BASE_URL/liabilities/$TEST_LIAB_ID" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d '{"name":"已更新的负债名称","interest_rate":3.8}')
UPDATED_LIAB_NAME=$(json_value "$LIAB_UPDATE" '.name')
test_case "负债名称更新成功" "已更新的负债名称" "$UPDATED_LIAB_NAME"

UPDATED_RATE=$(json_value "$LIAB_UPDATE" '.interest_rate')
test_case "负债利率更新成功" "3.8" "$UPDATED_RATE"

# 还款历史
echo "2.3 查看还款历史..."
PAY_HIST=$(curl -sL -w "%{http_code}" "$BASE_URL/liabilities/$TEST_LIAB_ID/payments" \
    -H "Authorization: Bearer $TOKEN")
test_case "还款历史返回200" "200" "$(http_code "$PAY_HIST")"

# 删除负债
echo "2.4 删除负债..."
DEL_LIAB=$(curl -sL -w "%{http_code}" -X DELETE "$BASE_URL/liabilities/$TEST_LIAB_ID" \
    -H "Authorization: Bearer $TOKEN")
test_case "删除负债返回200" "200" "$(http_code "$DEL_LIAB")"

# 验证删除后404
echo "2.5 验证删除后访问返回404..."
DELETED_LIAB=$(curl -sL -w "%{http_code}" "$BASE_URL/liabilities/$TEST_LIAB_ID" \
    -H "Authorization: Bearer $TOKEN")
test_case "已删除负债返回404" "404" "$(http_code "$DELETED_LIAB")"

# =====================
# 3. 心愿更新/删除 (WISH)
# =====================
echo ""
echo "=== 心愿更新/删除测试 ==="

# 创建测试心愿
echo "3.0 创建测试心愿..."
WISH_CREATE=$(curl -sL -X POST "$BASE_URL/wishes" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d "{\"name\":\"扩展测试心愿_$$\",\"expected_price\":50000,\"priority\":2}")
TEST_WISH_ID=$(json_value "$WISH_CREATE" '.id')
test_case "创建测试心愿" "true" "$([ -n "$TEST_WISH_ID" ] && echo true || echo false)"

# 心愿详情
echo "3.1 获取心愿详情..."
WISH_DETAIL=$(curl -sL -w "%{http_code}" "$BASE_URL/wishes/$TEST_WISH_ID" \
    -H "Authorization: Bearer $TOKEN")
test_case "心愿详情返回200" "200" "$(http_code "$WISH_DETAIL")"

# 更新心愿
echo "3.2 更新心愿信息..."
WISH_UPDATE=$(curl -sL -X PUT "$BASE_URL/wishes/$TEST_WISH_ID" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d '{"name":"已更新的心愿名称","priority":5,"expected_price":80000}')
UPDATED_WISH_NAME=$(json_value "$WISH_UPDATE" '.name')
test_case "心愿名称更新成功" "已更新的心愿名称" "$UPDATED_WISH_NAME"

UPDATED_PRIORITY=$(json_value "$WISH_UPDATE" '.priority')
test_case "心愿优先级更新为5" "5" "$UPDATED_PRIORITY"

# 删除心愿
echo "3.3 删除心愿..."
DEL_WISH=$(curl -sL -w "%{http_code}" -X DELETE "$BASE_URL/wishes/$TEST_WISH_ID" \
    -H "Authorization: Bearer $TOKEN")
test_case "删除心愿返回200" "200" "$(http_code "$DEL_WISH")"

# 验证删除后404
echo "3.4 验证删除后访问返回404..."
DELETED_WISH=$(curl -sL -w "%{http_code}" "$BASE_URL/wishes/$TEST_WISH_ID" \
    -H "Authorization: Bearer $TOKEN")
test_case "已删除心愿返回404" "404" "$(http_code "$DELETED_WISH")"

# =====================
# 4. 分类 CRUD (CATEGORY)
# =====================
echo ""
echo "=== 分类 CRUD 测试 ==="

# 创建自定义分类
echo "4.1 创建自定义分类..."
CAT_CREATE=$(curl -sL -X POST "$BASE_URL/categories" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d "{\"name\":\"测试自定义分类_$$\",\"icon\":\"🎯\",\"color\":\"#FF6B6B\",\"asset_type\":\"physical\"}")
TEST_CAT_ID=$(json_value "$CAT_CREATE" '.id')
test_case "创建自定义分类" "true" "$([ -n "$TEST_CAT_ID" ] && echo true || echo false)"

# 验证分类在列表中
echo "4.2 验证自定义分类在列表中..."
CAT_LIST=$(curl -sL "$BASE_URL/categories" -H "Authorization: Bearer $TOKEN")
CAT_IN_LIST=$(echo "$CAT_LIST" | jq -r "[.[] | select(.id == \"$TEST_CAT_ID\")] | length")
test_case "自定义分类在列表中" "1" "$CAT_IN_LIST"

# 更新自定义分类
echo "4.3 更新自定义分类..."
CAT_UPDATE=$(curl -sL -X PUT "$BASE_URL/categories/$TEST_CAT_ID" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d '{"name":"已更新的分类名称","icon":"🏆"}')
UPDATED_CAT_NAME=$(json_value "$CAT_UPDATE" '.name')
test_case "分类名称更新成功" "已更新的分类名称" "$UPDATED_CAT_NAME"

# 删除自定义分类
echo "4.4 删除自定义分类..."
DEL_CAT=$(curl -sL -w "%{http_code}" -X DELETE "$BASE_URL/categories/$TEST_CAT_ID" \
    -H "Authorization: Bearer $TOKEN")
test_case "删除自定义分类返回200" "200" "$(http_code "$DEL_CAT")"

# 尝试删除系统分类（应该失败）
echo "4.5 尝试删除系统分类（应拒绝）..."
SYS_CAT_ID=$(json_value "$CAT_RESP" '.[0].id')
DEL_SYS_CAT=$(curl -sL -w "%{http_code}" -X DELETE "$BASE_URL/categories/$SYS_CAT_ID" \
    -H "Authorization: Bearer $TOKEN")
SYS_DEL_CODE=$(http_code "$DEL_SYS_CAT")
test_case "删除系统分类被拒绝(4xx)" "true" "$([[ $SYS_DEL_CODE =~ ^4 ]] && echo true || echo false)"

# =====================
# 5. 标签 CRUD (TAG)
# =====================
echo ""
echo "=== 标签 CRUD 测试 ==="

# 创建标签
echo "5.1 创建标签..."
TAG_CREATE=$(curl -sL -X POST "$BASE_URL/tags" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d "{\"name\":\"测试标签_$$\",\"color\":\"#4ECDC4\"}")
TEST_TAG_ID=$(json_value "$TAG_CREATE" '.id')
test_case "创建标签" "true" "$([ -n "$TEST_TAG_ID" ] && echo true || echo false)"

# 验证标签在列表中
echo "5.2 验证标签在列表中..."
TAG_LIST=$(curl -sL "$BASE_URL/tags" -H "Authorization: Bearer $TOKEN")
TAG_IN_LIST=$(echo "$TAG_LIST" | jq -r "[.[] | select(.id == \"$TEST_TAG_ID\")] | length")
test_case "标签在列表中" "1" "$TAG_IN_LIST"

# 更新标签
echo "5.3 更新标签..."
TAG_UPDATE=$(curl -sL -X PUT "$BASE_URL/tags/$TEST_TAG_ID" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d '{"name":"已更新的标签","color":"#FF9F43"}')
UPDATED_TAG_NAME=$(json_value "$TAG_UPDATE" '.name')
test_case "标签名称更新成功" "已更新的标签" "$UPDATED_TAG_NAME"

UPDATED_TAG_COLOR=$(json_value "$TAG_UPDATE" '.color')
test_case "标签颜色更新成功" "#FF9F43" "$UPDATED_TAG_COLOR"

# 删除标签
echo "5.4 删除标签..."
DEL_TAG=$(curl -sL -w "%{http_code}" -X DELETE "$BASE_URL/tags/$TEST_TAG_ID" \
    -H "Authorization: Bearer $TOKEN")
test_case "删除标签返回200" "200" "$(http_code "$DEL_TAG")"

# 验证删除后不在列表
echo "5.5 验证删除后标签不在列表..."
TAG_LIST_AFTER=$(curl -sL "$BASE_URL/tags" -H "Authorization: Bearer $TOKEN")
TAG_AFTER=$(echo "$TAG_LIST_AFTER" | jq -r "[.[] | select(.id == \"$TEST_TAG_ID\")] | length")
test_case "已删除标签不在列表中" "0" "$TAG_AFTER"

# =====================
# 6. 家庭成员管理 (FAMILY)
# =====================
echo ""
echo "=== 家庭成员管理测试 ==="

# 成员列表
echo "6.1 获取成员列表..."
MEMBERS=$(curl -sL "$BASE_URL/family/members" -H "Authorization: Bearer $TOKEN")
MEMBER_COUNT=$(echo "$MEMBERS" | jq 'length')
test_case "成员列表非空" "true" "$([ $MEMBER_COUNT -gt 0 ] && echo true || echo false)"

# 获取当前用户ID
ME_RESP=$(curl -sL "$BASE_URL/auth/me" -H "Authorization: Bearer $TOKEN")
MY_ID=$(json_value "$ME_RESP" '.id')
test_case "获取当前用户ID" "true" "$([ -n "$MY_ID" ] && echo true || echo false)"

# 成员详情（自己的汇总）
echo "6.2 获取成员详情汇总..."
MEMBER_SUMMARY=$(curl -sL -w "%{http_code}" "$BASE_URL/family/members/$MY_ID/summary" \
    -H "Authorization: Bearer $TOKEN")
test_case "成员详情返回200" "200" "$(http_code "$MEMBER_SUMMARY")"

# 成员汇总字段验证
SUMMARY_BODY=$(curl -sL "$BASE_URL/family/members/$MY_ID/summary" \
    -H "Authorization: Bearer $TOKEN")
SUMMARY_ASSETS=$(json_value "$SUMMARY_BODY" '.total_assets')
test_case "成员汇总包含total_assets" "true" "$([ -n "$SUMMARY_ASSETS" ] && echo true || echo false)"

# 不存在的成员
echo "6.3 访问不存在的成员..."
INVALID_MEMBER=$(curl -sL -w "%{http_code}" "$BASE_URL/family/members/nonexistent-id/summary" \
    -H "Authorization: Bearer $TOKEN")
test_case "不存在成员返回404" "404" "$(http_code "$INVALID_MEMBER")"

# =====================
# 7. 邀请码重新生成 (INVITE CODE)
# =====================
echo ""
echo "=== 邀请码重新生成测试 ==="

# 获取当前邀请码
echo "7.1 获取当前邀请码..."
FAMILY_INFO=$(curl -sL "$BASE_URL/family" -H "Authorization: Bearer $TOKEN")
OLD_INVITE=$(json_value "$FAMILY_INFO" '.invite_code')
test_case "当前邀请码非空" "true" "$([ -n "$OLD_INVITE" ] && echo true || echo false)"

# 重新生成邀请码
echo "7.2 重新生成邀请码..."
REGEN_RESP=$(curl -sL -X POST "$BASE_URL/family/invite-code" \
    -H "Authorization: Bearer $TOKEN")
NEW_INVITE=$(json_value "$REGEN_RESP" '.invite_code')
test_case "新邀请码非空" "true" "$([ -n "$NEW_INVITE" ] && echo true || echo false)"
test_case "新邀请码与旧邀请码不同" "true" "$([ "$NEW_INVITE" != "$OLD_INVITE" ] && echo true || echo false)"
test_case "邀请码为6位" "6" "$(echo -n "$NEW_INVITE" | wc -c | tr -d ' ')"

# =====================
# 8. 快照生成 (SNAPSHOT)
# =====================
echo ""
echo "=== 快照生成测试 ==="

echo "8.1 触发快照生成..."
SNAPSHOT_RESP=$(curl -sL -X POST "$BASE_URL/family/snapshots/generate" \
    -H "Authorization: Bearer $TOKEN")
SNAPSHOT_DETAIL=$(json_value "$SNAPSHOT_RESP" '.detail')
test_case "快照生成返回detail" "true" "$([ -n "$SNAPSHOT_DETAIL" ] && echo true || echo false)"

# 验证趋势数据有快照
echo "8.2 验证趋势数据包含快照..."
TREND_RESP=$(curl -sL "$BASE_URL/dashboard/trend" -H "Authorization: Bearer $TOKEN")
TREND_LEN=$(echo "$TREND_RESP" | jq 'length' 2>/dev/null || echo "0")
test_case "趋势数据非空" "true" "$([ "$TREND_LEN" -gt 0 ] && echo true || echo false)"

# =====================
# 9. 活动日志 (ACTIVITIES)
# =====================
echo ""
echo "=== 活动日志测试 ==="

echo "9.1 获取最近活动日志..."
ACT_RESP=$(curl -sL -w "%{http_code}" "$BASE_URL/activities/recent" \
    -H "Authorization: Bearer $TOKEN")
test_case "活动日志返回200" "200" "$(http_code "$ACT_RESP")"

ACT_BODY=$(curl -sL "$BASE_URL/activities/recent" -H "Authorization: Bearer $TOKEN")
ACT_COUNT=$(echo "$ACT_BODY" | jq 'length' 2>/dev/null || echo "0")
test_case "活动日志非空" "true" "$([ "$ACT_COUNT" -gt 0 ] && echo true || echo false)"

# 验证活动日志字段
echo "9.2 验证活动日志字段完整性..."
FIRST_ACT_TYPE=$(json_value "$ACT_BODY" '.[0].type')
FIRST_ACT_ENTITY=$(json_value "$ACT_BODY" '.[0].entity_type')
test_case "活动日志包含type字段" "true" "$([ -n "$FIRST_ACT_TYPE" ] && echo true || echo false)"
test_case "活动日志包含entity_type字段" "true" "$([ -n "$FIRST_ACT_ENTITY" ] && echo true || echo false)"

# limit参数
echo "9.3 活动日志limit参数..."
ACT_LIMIT=$(curl -sL "$BASE_URL/activities/recent?limit=5" -H "Authorization: Bearer $TOKEN")
ACT_LIMIT_COUNT=$(echo "$ACT_LIMIT" | jq 'length' 2>/dev/null || echo "0")
test_case "limit=5时最多返回5条" "true" "$([ "$ACT_LIMIT_COUNT" -le 5 ] && echo true || echo false)"

# =====================
# 10. 边界情况 (EDGE CASES)
# =====================
echo ""
echo "=== 边界情况测试 ==="

# 不存在的负债
echo "10.1 访问不存在的负债..."
INVALID_LIAB=$(curl -sL -w "%{http_code}" "$BASE_URL/liabilities/nonexistent-id-99999" \
    -H "Authorization: Bearer $TOKEN")
test_case "不存在负债返回404" "404" "$(http_code "$INVALID_LIAB")"

# 不存在的心愿
echo "10.2 访问不存在的心愿..."
INVALID_WISH=$(curl -sL -w "%{http_code}" "$BASE_URL/wishes/nonexistent-id-99999" \
    -H "Authorization: Bearer $TOKEN")
test_case "不存在心愿返回404" "404" "$(http_code "$INVALID_WISH")"

# 资产筛选（按类型）
echo "10.3 资产按类型筛选..."
FILTER_RESP=$(curl -sL "$BASE_URL/assets?asset_type=physical" -H "Authorization: Bearer $TOKEN")
FILTER_COUNT=$(echo "$FILTER_RESP" | jq 'length' 2>/dev/null || echo "0")
ALL_PHYSICAL=$(echo "$FILTER_RESP" | jq '[.[] | select(.asset_type == "physical")] | length' 2>/dev/null || echo "0")
test_case "筛选结果全为physical类型" "$FILTER_COUNT" "$ALL_PHYSICAL"

# 资产搜索（中文需 URL 编码，用 -G + --data-urlencode）
echo "10.4 资产关键词搜索..."
SEARCH_CODE=$(curl -sL -w "%{http_code}" -o /dev/null -G "$BASE_URL/assets" \
    --data-urlencode "search=测试" \
    -H "Authorization: Bearer $TOKEN")
test_case "搜索接口返回200" "200" "$SEARCH_CODE"

# 负债按状态筛选
echo "10.5 负债按活跃状态筛选..."
ACTIVE_LIAB=$(curl -sL "$BASE_URL/liabilities?is_active=true" -H "Authorization: Bearer $TOKEN")
ACTIVE_COUNT=$(echo "$ACTIVE_LIAB" | jq 'length' 2>/dev/null || echo "0")
ALL_ACTIVE=$(echo "$ACTIVE_LIAB" | jq '[.[] | select(.is_active == true)] | length' 2>/dev/null || echo "0")
test_case "筛选结果全为活跃负债" "$ACTIVE_COUNT" "$ALL_ACTIVE"

# =====================
# 汇总
# =====================
echo ""
echo "=========================================="
echo "扩展测试结果汇总"
echo "=========================================="
echo "通过: $PASS"
echo "失败: $FAIL"
TOTAL_TESTS=$((PASS + FAIL))
echo "总计: $TOTAL_TESTS"
if [ $TOTAL_TESTS -gt 0 ]; then
    echo "通过率: $((PASS * 100 / TOTAL_TESTS))%"
fi
echo "=========================================="

if [ $FAIL -eq 0 ]; then
    echo "✓ 所有扩展测试通过!"
    exit 0
else
    echo "✗ 存在失败的测试，请检查上方 FAIL 条目"
    exit 1
fi
