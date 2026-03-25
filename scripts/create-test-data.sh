#!/bin/bash

# Numina Acceptance Test Data Generator
# Creates 25+ assets covering all 21 categories

BASE_URL="http://localhost/numina/api/v1"

# Get fresh token
echo "Getting auth token..."
TOKEN=$(curl -sL "$BASE_URL/auth/login" -H "Content-Type: application/json" \
  -d '{"username":"testuser","password":"TestPass123"}' | jq -r '.access_token')

if [ -z "$TOKEN" ] || [ "$TOKEN" == "null" ]; then
  echo "Failed to get token"
  exit 1
fi
echo "Token obtained: ${TOKEN:0:50}..."

# Category IDs
CATEGORIES='{
  "房产": "ea710967-87d5-488f-9425-f1b9322f2c12",
  "车辆": "272db1c7-dd6d-4bb7-8375-3698d1e40417",
  "数码": "77cd36a0-8af7-401e-9fc8-b7c7c7ff2db5",
  "家电": "ce0cdeca-f188-466e-9a41-ee3bceeef70d",
  "家具": "6a79ac18-f33b-4aeb-92ed-8f04341d101d",
  "珠宝": "6e3f408e-6fcd-4a43-bbaf-35aecae825aa",
  "服饰": "c53bb554-0f99-476c-84b6-e642291c7262",
  "美妆": "4c577375-cc57-4d65-9a39-6fa2c63a1a6c",
  "运动": "acd36f93-d9eb-4d28-8309-86e169bac306",
  "玩具": "071d83f8-5cf8-4e91-af74-aeb60ef6008f",
  "宠物": "3814eb9c-e34f-4650-9c12-42a59e3dff02",
  "乐器": "42c241ba-8e45-4efb-9a44-b98eb2564819",
  "箱包": "d3c74ced-81db-4d50-8501-6a36a0e64ce7",
  "存款": "bbd7162d-88a5-4a8b-80af-041e0191216a",
  "基金": "844a1045-6efb-4e43-9fe4-ba002233cb7c",
  "股票": "2a2a22c4-9885-42fb-b00b-f46d99c87e10",
  "债券": "1074a1e1-eb75-4cd3-89f4-5044723c3769",
  "保险": "97637e80-5125-4b51-9a32-874a5d0b1840",
  "理财产品": "54003e93-bb24-4949-b56f-869d4db353f6",
  "数字货币": "9dd48cf1-f4e5-4551-aa45-67d5774da808",
  "其他金融": "0cebb1e4-f24d-4dd1-b099-71091f704fbe"
}'

# Helper function to get category ID
get_cat_id() {
  echo "$CATEGORIES" | jq -r ".[\"$1\"]"
}

# Function to create physical asset
create_physical_asset() {
  local name="$1"
  local category_name="$2"
  local purchase_price="$3"
  local current_value="$4"
  local usage_freq="$5"
  local lifespan="$6"
  local maintenance="$7"

  local cat_id=$(get_cat_id "$category_name")

  local json=$(cat <<EOF
{
  "name": "$name",
  "category_id": "$cat_id",
  "asset_type": "physical",
  "purchase_price": $purchase_price,
  "current_value": $current_value,
  "purchase_date": "2024-01-15",
  "usage_frequency": "$usage_freq",
  "expected_lifespan_days": $lifespan,
  "annual_maintenance_cost": $maintenance,
  "status": "in_use",
  "notes": "验收测试数据 - $category_name分类"
}
EOF
)

  local result=$(curl -sL -w "\n%{http_code}" "$BASE_URL/assets/" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "$json")

  local http_code=$(echo "$result" | tail -n1)
  local body=$(echo "$result" | head -n -1)

  if [ "$http_code" == "201" ]; then
    echo "✓ Created: $name ($category_name)"
  else
    echo "✗ Failed: $name ($category_name) - HTTP $http_code"
    echo "  Response: $body"
  fi
}

# Function to create financial asset
create_financial_asset() {
  local name="$1"
  local category_name="$2"
  local amount="$3"
  local rate="$4"
  local maturity="$5"

  local cat_id=$(get_cat_id "$category_name")

  local json=$(cat <<EOF
{
  "name": "$name",
  "category_id": "$cat_id",
  "asset_type": "financial",
  "purchase_price": $amount,
  "current_value": $amount,
  "purchase_date": "2024-03-01",
  "interest_rate": $rate,
  "maturity_date": "$maturity",
  "status": "in_use",
  "notes": "验收测试数据 - $category_name分类"
}
EOF
)

  local result=$(curl -sL -w "\n%{http_code}" "$BASE_URL/assets/" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "$json")

  local http_code=$(echo "$result" | tail -n1)
  local body=$(echo "$result" | head -n -1)

  if [ "$http_code" == "201" ]; then
    echo "✓ Created: $name ($category_name)"
  else
    echo "✗ Failed: $name ($category_name) - HTTP $http_code"
    echo "  Response: $body"
  fi
}

# Function to create liability
create_liability() {
  local name="$1"
  local type="$2"
  local amount="$3"
  local remaining="$4"
  local rate="$5"

  local json=$(cat <<EOF
{
  "name": "$name",
  "liability_type": "$type",
  "original_amount": $amount,
  "remaining_amount": $remaining,
  "interest_rate": $rate,
  "start_date": "2023-06-01",
  "is_active": true,
  "notes": "验收测试数据"
}
EOF
)

  local result=$(curl -sL -w "\n%{http_code}" "$BASE_URL/liabilities/" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "$json")

  local http_code=$(echo "$result" | tail -n1)
  local body=$(echo "$result" | head -n -1)

  if [ "$http_code" == "201" ]; then
    echo "✓ Created liability: $name"
  else
    echo "✗ Failed liability: $name - HTTP $http_code"
    echo "  Response: $body"
  fi
}

# Function to create wish
create_wish() {
  local name="$1"
  local price="$2"
  local target_date="$3"
  local priority="$4"

  local json=$(cat <<EOF
{
  "name": "$name",
  "expected_price": $price,
  "target_date": "$target_date",
  "priority": $priority,
  "notes": "验收测试心愿"
}
EOF
)

  local result=$(curl -sL -w "\n%{http_code}" "$BASE_URL/wishes/" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "$json")

  local http_code=$(echo "$result" | tail -n1)
  local body=$(echo "$result" | head -n -1)

  if [ "$http_code" == "201" ]; then
    echo "✓ Created wish: $name (priority $priority)"
  else
    echo "✗ Failed wish: $name - HTTP $http_code"
    echo "  Response: $body"
  fi
}

echo ""
echo "=========================================="
echo "Creating Physical Assets (13 categories)"
echo "=========================================="

# Physical assets - 13 categories, 2 assets each for some = ~18 physical
create_physical_asset "北京朝阳区公寓" "房产" 3500000 3800000 "daily" 36500 8000
create_physical_asset "上海浦东别墅" "房产" 8000000 8500000 "daily" 36500 15000

create_physical_asset "特斯拉Model 3" "车辆" 280000 220000 "daily" 3650 5000
create_physical_asset "宝马X5" "车辆" 650000 550000 "weekly" 3650 12000

create_physical_asset "MacBook Pro 16寸" "数码" 18999 15000 "daily" 1095 500
create_physical_asset "iPhone 15 Pro Max" "数码" 9999 8000 "daily" 730 0

create_physical_asset "索尼65寸电视" "家电" 12000 9000 "daily" 1825 200
create_physical_asset "戴森吸尘器" "家电" 4500 3500 "weekly" 1095 100

create_physical_asset "北欧实木沙发" "家具" 18000 16000 "daily" 3650 200
create_physical_asset "红木餐桌套装" "家具" 35000 32000 "weekly" 3650 300

create_physical_asset "卡地亚戒指" "珠宝" 85000 90000 "monthly" 36500 500
create_physical_asset "钻石项链" "珠宝" 120000 130000 "rarely" 36500 800

create_physical_asset "阿玛尼西装" "服饰" 15000 12000 "weekly" 730 200
create_physical_asset "羽绒服" "服饰" 3000 2000 "rarely" 730 50

create_physical_asset "兰蔻护肤套装" "美妆" 2500 1800 "daily" 365 100
create_physical_asset "雅诗兰黛精华" "美妆" 1200 900 "daily" 365 50

create_physical_asset "健身器材套装" "运动" 5000 4500 "daily" 1825 100
create_physical_asset "瑜伽垫配件" "运动" 500 400 "weekly" 730 0

create_physical_asset "PlayStation 5" "玩具" 4500 4000 "weekly" 1825 0
create_physical_asset "乐高收藏版" "玩具" 3000 3500 "rarely" 3650 0

create_physical_asset "金毛犬" "宠物" 5000 3000 "daily" 3650 3000
create_physical_asset "英短蓝猫" "宠物" 3000 2500 "daily" 3650 1500

create_physical_asset "雅马哈吉他" "乐器" 8000 7500 "weekly" 3650 100
create_physical_asset "电子琴" "乐器" 5000 4500 "monthly" 3650 50

create_physical_asset "LV手提包" "箱包" 25000 23000 "weekly" 1825 200
create_physical_asset "新秀丽行李箱" "箱包" 2000 1800 "rarely" 1825 0

echo ""
echo "=========================================="
echo "Creating Financial Assets (8 categories)"
echo "=========================================="

# Financial assets - 8 categories, 1 each = 8 financial
create_financial_asset "工商银行定期存款" "存款" 100000 0.025 "2025-03-01"
create_financial_asset "招商银行活期" "存款" 50000 0.003 "2025-12-31"

create_financial_asset "易方达蓝筹精选" "基金" 80000 0.08 "2025-06-01"
create_financial_asset "华夏沪深300ETF" "基金" 50000 0.06 "2025-09-01"

create_financial_asset "贵州茅台" "股票" 120000 0.12 "2025-12-01"
create_financial_asset "宁德时代" "股票" 60000 -0.15 "2025-12-01"

create_financial_asset "国债2024" "债券" 30000 0.035 "2027-03-01"
create_financial_asset "企业债" "债券" 20000 0.045 "2026-06-01"

create_financial_asset "平安重疾险" "保险" 50000 0.0 "2030-03-01"
create_financial_asset "人寿意外险" "保险" 10000 0.0 "2030-03-01"

create_financial_asset "招银理财季季盈" "理财产品" 150000 0.04 "2024-06-01"
create_financial_asset "工银理财周周利" "理财产品" 80000 0.03 "2024-04-01"

create_financial_asset "比特币" "数字货币" 30000 0.25 "2025-12-01"
create_financial_asset "以太坊" "数字货币" 15000 0.18 "2025-12-01"

create_financial_asset "黄金积存" "其他金融" 40000 0.05 "2025-12-01"

echo ""
echo "=========================================="
echo "Creating Additional Liabilities"
echo "=========================================="

create_liability "招商银行信用卡" "credit_card" 50000 28000 0.18
create_liability "个人消费贷款" "personal_loan" 100000 75000 0.08
create_liability "京东白条" "other" 8000 5000 0.12

echo ""
echo "=========================================="
echo "Creating Wishes"
echo "=========================================="

create_wish "MacBook Air M3" 12000 "2024-06-01" 1
create_wish "Apple Watch Ultra" 6500 "2024-08-01" 2
create_wish "日本东京旅行" 20000 "2024-10-01" 3
create_wish "戴森吹风机" 3200 "2024-07-01" 2
create_wish "iPad Pro" 9000 "2024-12-01" 4

echo ""
echo "=========================================="
echo "Summary"
echo "=========================================="

# Count results
ASSET_COUNT=$(curl -sL "$BASE_URL/assets/" -H "Authorization: Bearer $TOKEN" | jq 'if type == "array" then length else .items | length end')
LIAB_COUNT=$(curl -sL "$BASE_URL/liabilities/" -H "Authorization: Bearer $TOKEN" | jq 'if type == "array" then length else .items | length end')

echo "Total assets: $ASSET_COUNT"
echo "Total liabilities: $LIAB_COUNT"
echo ""
echo "Test data creation completed!"