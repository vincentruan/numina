#!/bin/bash
TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIzZmI4ZGE5Ni1iMjQzLTQzYjgtOTI2My02M2U1M2M0MGE2MzYiLCJleHAiOjE3NzM5MjQ1MzUsInR5cGUiOiJhY2Nlc3MifQ.j7s_bREsYEFIXG33Zo98eHSScOUxlQFoktcuQZoBo8o"
BASE="http://localhost/numina/api/v1"

# 实物资产
declare -A PHYSICAL=(
  ["ea710967-87d5-488f-9425-f1b9322f2c12"]="深圳湾一号|25000000|28000000|daily|36500|50000"
  ["272db1c7-dd6d-4bb7-8375-3698d1e40417"]="宝马X5|450000|380000|daily|3650|15000"
  ["77cd36a0-8af7-401e-9fc8-b7c7c7ff2db5"]="MacBook Pro|18000|15000|daily|1825|0"
  ["77cd36a0-8af7-401e-9fc8-b7c7c7ff2db5"]="iPad Pro|8000|6500|weekly|1825|0"
  ["ce0cdeca-f188-466e-9a41-ee3bceeef70d"]="戴森吸尘器|4500|3500|weekly|1825|200"
  ["ce0cdeca-f188-466e-9a41-ee3bceeef70d"]="美的空调|6000|5000|daily|3650|100"
  ["6a79ac18-f33b-4aeb-92ed-8f04341d101d"]="实木沙发|12000|10000|daily|7300|0"
  ["6a79ac18-f33b-4aeb-92ed-8f04341d101d"]="餐桌椅套装|8000|7000|daily|7300|0"
  ["6e3f408e-6fcd-4a43-bbaf-35aecae825aa"]="黄金项链|15000|18000|monthly|36500|0"
  ["6e3f408e-6fcd-4a43-bbaf-35aecae825aa"]="钻石戒指|30000|35000|rarely|36500|0"
  ["c53bb554-0f99-476c-84b6-e642291c7262"]="羽绒服|2000|1500|weekly|1825|0"
  ["c53bb554-0f99-476c-84b6-e642291c7262"]="西装套装|5000|4000|monthly|1825|200"
  ["4c577375-cc57-4d65-9a39-6fa2c63a1a6c"]="SK-II套装|3000|2500|daily|730|0"
  ["acd36f93-d9eb-4d28-8309-86e169bac306"]="跑步机|5000|4000|weekly|3650|100"
  ["acd36f93-d9eb-4d28-8309-86e169bac306"]="自行车|3000|2500|monthly|3650|50"
  ["071d83f8-5cf8-4e91-af74-aeb60ef6008f"]="乐高积木|2000|1500|monthly|1825|0"
  ["3814eb9c-e34f-4650-9c12-42a59e3dff02"]="金毛犬|5000|4000|daily|3650|3000"
  ["42c241ba-8e45-4efb-9a44-b98eb2564819"]="雅马哈钢琴|30000|28000|weekly|18250|500"
  ["d3c74ced-81db-4d50-8501-6a36a0e64ce7"]="LV包|15000|12000|monthly|3650|0"
)

# 金融资产
declare -A FINANCIAL=(
  ["bbd7162d-88a5-4a8b-80af-041e0191216a"]="招商银行定存|300000|315000|2.5|2027-01-01"
  ["bbd7162d-88a5-4a8b-80af-041e0191216a"]="工商银行活期|200000|202000|0.3|"
  ["844a1045-6efb-4e43-9fe4-ba002233cb7c"]="易方达蓝筹|150000|120000|"
  ["844a1045-6efb-4e43-9fe4-ba002233cb7c"]="华夏成长|80000|75000|"
  ["2a2a22c4-9885-42fb-b00b-f46d99c87e10"]="贵州茅台|100000|95000|"
  ["2a2a22c4-9885-42fb-b00b-f46d99c87e10"]="腾讯控股|50000|42000|"
  ["1074a1e1-eb75-4cd3-89f4-5044723c3769"]="国债|100000|105000|3.2|2028-01-01"
  ["97637e80-5125-4b51-9a32-874a5d0b1840"]="重疾险|50000|50000|"
  ["54003e93-bb24-4949-b56f-869d4db353f6"]="银行理财|200000|208000|4.0|2025-06-01"
  ["9dd48cf1-f4e5-4551-aa45-67d5774da808"]="比特币|30000|25000|"
  ["0cebb1e4-f24d-4dd1-b099-71091f704fbe"]="P2P理财|20000|15000|"
)

echo "创建实物资产..."
for key in "${!PHYSICAL[@]}"; do
  IFS='|' read -r name purchase current usage lifespan maint <<< "${PHYSICAL[$key]}"
  curl -sL -X POST "$BASE/assets" -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" \
    -d "{\"name\":\"$name\",\"asset_type\":\"physical\",\"category_id\":\"$key\",\"purchase_price\":$purchase,\"current_value\":$current,\"purchase_date\":\"2023-01-15\",\"usage_frequency\":\"$usage\",\"expected_lifespan_days\":$lifespan,\"annual_maintenance_cost\":$maint}" > /dev/null
  echo "  创建: $name"
done

echo "创建金融资产..."
for key in "${!FINANCIAL[@]}"; do
  IFS='|' read -r name purchase current rate maturity <<< "${FINANCIAL[$key]}"
  extra=""
  [ -n "$rate" ] && extra=",\"interest_rate\":$rate"
  [ -n "$maturity" ] && extra="$extra,\"maturity_date\":\"$maturity\""
  curl -sL -X POST "$BASE/assets" -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" \
    -d "{\"name\":\"$name\",\"asset_type\":\"financial\",\"category_id\":\"$key\",\"purchase_price\":$purchase,\"current_value\":$current,\"purchase_date\":\"2023-01-15\"$extra}" > /dev/null
  echo "  创建: $name"
done

echo "创建负债..."
# 信用卡
curl -sL -X POST "$BASE/liabilities" -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" \
  -d '{"name":"招商信用卡","category":"credit_card","original_amount":50000,"remaining_amount":30000,"monthly_payment":3000,"interest_rate":18}' > /dev/null
echo "  创建: 招商信用卡"

# 个人贷款
curl -sL -X POST "$BASE/liabilities" -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" \
  -d '{"name":"装修贷款","category":"personal_loan","original_amount":200000,"remaining_amount":150000,"monthly_payment":5000,"interest_rate":6}' > /dev/null
echo "  创建: 装修贷款"

# 其他负债
curl -sL -X POST "$BASE/liabilities" -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" \
  -d '{"name":"亲友借款","category":"other","original_amount":30000,"remaining_amount":20000,"monthly_payment":2000,"interest_rate":0}' > /dev/null
echo "  创建: 亲友借款"

echo "创建心愿单..."
for i in 1 2 3 4 5; do
  case $i in
    1) name="换新房"; price=5000000; target="2028-01-01"; priority=5 ;;
    2) name="买新车"; price=500000; target="2025-01-01"; priority=4 ;;
    3) name="出国旅游"; price=50000; target="2025-06-01"; priority=3 ;;
    4) name="换手机"; price=10000; target="2024-12-01"; priority=2 ;;
    5) name="买相机"; price=20000; target="2025-03-01"; priority=3 ;;
  esac
  curl -sL -X POST "$BASE/wishes" -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" \
    -d "{\"name\":\"$name\",\"expected_price\":$price,\"target_date\":\"$target\",\"priority\":$priority}" > /dev/null
  echo "  创建: $name"
done

echo "生成快照..."
curl -sL -X POST "$BASE/family/snapshots/generate" -H "Authorization: Bearer $TOKEN" > /dev/null
echo "  快照已生成"

echo "完成！"