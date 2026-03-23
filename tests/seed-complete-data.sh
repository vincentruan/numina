#!/bin/bash

# 完整测试数据生成脚本
# 包含：实物资产、金融资产、负债、心愿

set -e

BASE_URL="http://localhost/numina/api/v1"
TOKEN=""

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

log_info() {
    echo -e "${YELLOW}ℹ $1${NC}"
}

# 登录获取 token
get_token() {
    log_info "登录获取 token..."

    local response=$(curl -sL -X POST "$BASE_URL/auth/login" \
        -H "Content-Type: application/json" \
        -d '{"username":"testuser","password":"TestPass123"}')

    TOKEN=$(echo "$response" | jq -r '.access_token')

    if [ -z "$TOKEN" ] || [ "$TOKEN" = "null" ]; then
        log_info "用户不存在，正在注册..."
        response=$(curl -sL -X POST "$BASE_URL/auth/register" \
            -H "Content-Type: application/json" \
            -d '{"username":"testuser","display_name":"Test User","password":"TestPass123","family_name":"Test Family"}')
        TOKEN=$(echo "$response" | jq -r '.access_token')
    fi

    log_success "登录成功"
}

# 获取分类 ID
get_category_id() {
    local name=$1
    local asset_type=$2

    local response=$(curl -sL -X GET "$BASE_URL/categories?asset_type=$asset_type" \
        -H "Authorization: Bearer $TOKEN")

    echo "$response" | jq -r ".[] | select(.name==\"$name\") | .id"
}

# 创建实物资产
create_physical_assets() {
    log_info "========== 创建实物资产 =========="

    # 房产
    local cat_house=$(get_category_id "房产" "physical")
    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{\"name\":\"深圳湾一号\",\"asset_type\":\"physical\",\"category_id\":\"$cat_house\",\"purchase_price\":25000000,\"current_value\":28000000,\"purchase_date\":\"2020-01-15\",\"usage_frequency\":\"daily\",\"expected_lifespan_days\":36500,\"annual_maintenance_cost\":50000}" > /dev/null
    log_success "创建: 深圳湾一号"

    # 车辆
    local cat_car=$(get_category_id "车辆" "physical")
    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{\"name\":\"宝马X5\",\"asset_type\":\"physical\",\"category_id\":\"$cat_car\",\"purchase_price\":450000,\"current_value\":380000,\"purchase_date\":\"2022-06-01\",\"usage_frequency\":\"daily\",\"expected_lifespan_days\":3650,\"annual_maintenance_cost\":15000}" > /dev/null
    log_success "创建: 宝马X5"

    # 数码
    local cat_digital=$(get_category_id "数码" "physical")
    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{\"name\":\"MacBook Pro\",\"asset_type\":\"physical\",\"category_id\":\"$cat_digital\",\"purchase_price\":18000,\"current_value\":15000,\"purchase_date\":\"2023-01-15\",\"usage_frequency\":\"daily\",\"expected_lifespan_days\":1825,\"annual_maintenance_cost\":0}" > /dev/null
    log_success "创建: MacBook Pro"

    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{\"name\":\"iPad Pro\",\"asset_type\":\"physical\",\"category_id\":\"$cat_digital\",\"purchase_price\":8000,\"current_value\":6500,\"purchase_date\":\"2023-03-20\",\"usage_frequency\":\"weekly\",\"expected_lifespan_days\":1825,\"annual_maintenance_cost\":0}" > /dev/null
    log_success "创建: iPad Pro"

    # 家电
    local cat_appliance=$(get_category_id "家电" "physical")
    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{\"name\":\"戴森吸尘器\",\"asset_type\":\"physical\",\"category_id\":\"$cat_appliance\",\"purchase_price\":4500,\"current_value\":3500,\"purchase_date\":\"2023-05-10\",\"usage_frequency\":\"weekly\",\"expected_lifespan_days\":1825,\"annual_maintenance_cost\":200}" > /dev/null
    log_success "创建: 戴森吸尘器"

    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{\"name\":\"美的空调\",\"asset_type\":\"physical\",\"category_id\":\"$cat_appliance\",\"purchase_price\":6000,\"current_value\":5000,\"purchase_date\":\"2022-07-01\",\"usage_frequency\":\"daily\",\"expected_lifespan_days\":3650,\"annual_maintenance_cost\":100}" > /dev/null
    log_success "创建: 美的空调"

    # 家具
    local cat_furniture=$(get_category_id "家具" "physical")
    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{\"name\":\"实木沙发\",\"asset_type\":\"physical\",\"category_id\":\"$cat_furniture\",\"purchase_price\":12000,\"current_value\":10000,\"purchase_date\":\"2021-03-15\",\"usage_frequency\":\"daily\",\"expected_lifespan_days\":7300,\"annual_maintenance_cost\":0}" > /dev/null
    log_success "创建: 实木沙发"

    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{\"name\":\"餐桌椅套装\",\"asset_type\":\"physical\",\"category_id\":\"$cat_furniture\",\"purchase_price\":8000,\"current_value\":7000,\"purchase_date\":\"2021-03-15\",\"usage_frequency\":\"daily\",\"expected_lifespan_days\":7300,\"annual_maintenance_cost\":0}" > /dev/null
    log_success "创建: 餐桌椅套装"

    # 珠宝
    local cat_jewelry=$(get_category_id "珠宝" "physical")
    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{\"name\":\"黄金项链\",\"asset_type\":\"physical\",\"category_id\":\"$cat_jewelry\",\"purchase_price\":15000,\"current_value\":18000,\"purchase_date\":\"2020-12-20\",\"usage_frequency\":\"monthly\",\"expected_lifespan_days\":36500,\"annual_maintenance_cost\":0}" > /dev/null
    log_success "创建: 黄金项链"

    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{\"name\":\"钻石戒指\",\"asset_type\":\"physical\",\"category_id\":\"$cat_jewelry\",\"purchase_price\":30000,\"current_value\":35000,\"purchase_date\":\"2019-05-20\",\"usage_frequency\":\"rarely\",\"expected_lifespan_days\":36500,\"annual_maintenance_cost\":0}" > /dev/null
    log_success "创建: 钻石戒指"

    # 服饰
    local cat_clothing=$(get_category_id "服饰" "physical")
    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{\"name\":\"羽绒服\",\"asset_type\":\"physical\",\"category_id\":\"$cat_clothing\",\"purchase_price\":2000,\"current_value\":1500,\"purchase_date\":\"2023-11-01\",\"usage_frequency\":\"weekly\",\"expected_lifespan_days\":1825,\"annual_maintenance_cost\":0}" > /dev/null
    log_success "创建: 羽绒服"

    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{\"name\":\"西装套装\",\"asset_type\":\"physical\",\"category_id\":\"$cat_clothing\",\"purchase_price\":5000,\"current_value\":4000,\"purchase_date\":\"2023-03-01\",\"usage_frequency\":\"monthly\",\"expected_lifespan_days\":1825,\"annual_maintenance_cost\":200}" > /dev/null
    log_success "创建: 西装套装"

    # 美妆
    local cat_beauty=$(get_category_id "美妆" "physical")
    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{\"name\":\"SK-II套装\",\"asset_type\":\"physical\",\"category_id\":\"$cat_beauty\",\"purchase_price\":3000,\"current_value\":2500,\"purchase_date\":\"2024-01-01\",\"usage_frequency\":\"daily\",\"expected_lifespan_days\":730,\"annual_maintenance_cost\":0}" > /dev/null
    log_success "创建: SK-II套装"

    # 运动
    local cat_sports=$(get_category_id "运动" "physical")
    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{\"name\":\"跑步机\",\"asset_type\":\"physical\",\"category_id\":\"$cat_sports\",\"purchase_price\":5000,\"current_value\":4000,\"purchase_date\":\"2022-09-01\",\"usage_frequency\":\"weekly\",\"expected_lifespan_days\":3650,\"annual_maintenance_cost\":100}" > /dev/null
    log_success "创建: 跑步机"

    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{\"name\":\"自行车\",\"asset_type\":\"physical\",\"category_id\":\"$cat_sports\",\"purchase_price\":3000,\"current_value\":2500,\"purchase_date\":\"2023-04-15\",\"usage_frequency\":\"monthly\",\"expected_lifespan_days\":3650,\"annual_maintenance_cost\":50}" > /dev/null
    log_success "创建: 自行车"

    # 玩具
    local cat_toys=$(get_category_id "玩具" "physical")
    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{\"name\":\"乐高积木\",\"asset_type\":\"physical\",\"category_id\":\"$cat_toys\",\"purchase_price\":2000,\"current_value\":1500,\"purchase_date\":\"2023-12-25\",\"usage_frequency\":\"monthly\",\"expected_lifespan_days\":1825,\"annual_maintenance_cost\":0}" > /dev/null
    log_success "创建: 乐高积木"

    # 宠物
    local cat_pets=$(get_category_id "宠物" "physical")
    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{\"name\":\"金毛犬\",\"asset_type\":\"physical\",\"category_id\":\"$cat_pets\",\"purchase_price\":5000,\"current_value\":4000,\"purchase_date\":\"2022-01-10\",\"usage_frequency\":\"daily\",\"expected_lifespan_days\":3650,\"annual_maintenance_cost\":3000}" > /dev/null
    log_success "创建: 金毛犬"

    # 乐器
    local cat_instrument=$(get_category_id "乐器" "physical")
    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{\"name\":\"雅马哈钢琴\",\"asset_type\":\"physical\",\"category_id\":\"$cat_instrument\",\"purchase_price\":30000,\"current_value\":28000,\"purchase_date\":\"2020-08-15\",\"usage_frequency\":\"weekly\",\"expected_lifespan_days\":18250,\"annual_maintenance_cost\":500}" > /dev/null
    log_success "创建: 雅马哈钢琴"

    # 箱包
    local cat_bags=$(get_category_id "箱包" "physical")
    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{\"name\":\"LV包\",\"asset_type\":\"physical\",\"category_id\":\"$cat_bags\",\"purchase_price\":15000,\"current_value\":12000,\"purchase_date\":\"2022-11-11\",\"usage_frequency\":\"monthly\",\"expected_lifespan_days\":3650,\"annual_maintenance_cost\":0}" > /dev/null
    log_success "创建: LV包"
}

# 创建金融资产
create_financial_assets() {
    log_info "========== 创建金融资产 =========="

    # 存款
    local cat_deposit=$(get_category_id "存款" "financial")
    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{\"name\":\"招商银行定存\",\"asset_type\":\"financial\",\"category_id\":\"$cat_deposit\",\"purchase_price\":300000,\"current_value\":315000,\"purchase_date\":\"2023-01-15\",\"interest_rate\":2.5,\"maturity_date\":\"2027-01-01\"}" > /dev/null
    log_success "创建: 招商银行定存"

    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{\"name\":\"工商银行活期\",\"asset_type\":\"financial\",\"category_id\":\"$cat_deposit\",\"purchase_price\":200000,\"current_value\":202000,\"purchase_date\":\"2023-01-15\",\"interest_rate\":0.3}" > /dev/null
    log_success "创建: 工商银行活期"

    # 基金
    local cat_fund=$(get_category_id "基金" "financial")
    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{\"name\":\"易方达蓝筹\",\"asset_type\":\"financial\",\"category_id\":\"$cat_fund\",\"purchase_price\":150000,\"current_value\":120000,\"purchase_date\":\"2023-01-15\"}" > /dev/null
    log_success "创建: 易方达蓝筹"

    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{\"name\":\"华夏成长\",\"asset_type\":\"financial\",\"category_id\":\"$cat_fund\",\"purchase_price\":80000,\"current_value\":75000,\"purchase_date\":\"2023-01-15\"}" > /dev/null
    log_success "创建: 华夏成长"

    # 股票
    local cat_stock=$(get_category_id "股票" "financial")
    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{\"name\":\"贵州茅台\",\"asset_type\":\"financial\",\"category_id\":\"$cat_stock\",\"purchase_price\":100000,\"current_value\":95000,\"purchase_date\":\"2023-01-15\"}" > /dev/null
    log_success "创建: 贵州茅台"

    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{\"name\":\"腾讯控股\",\"asset_type\":\"financial\",\"category_id\":\"$cat_stock\",\"purchase_price\":50000,\"current_value\":42000,\"purchase_date\":\"2023-01-15\"}" > /dev/null
    log_success "创建: 腾讯控股"

    # 债券
    local cat_bond=$(get_category_id "债券" "financial")
    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{\"name\":\"国债\",\"asset_type\":\"financial\",\"category_id\":\"$cat_bond\",\"purchase_price\":100000,\"current_value\":105000,\"purchase_date\":\"2023-01-15\",\"interest_rate\":3.2,\"maturity_date\":\"2028-01-01\"}" > /dev/null
    log_success "创建: 国债"

    # 保险
    local cat_insurance=$(get_category_id "保险" "financial")
    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{\"name\":\"重疾险\",\"asset_type\":\"financial\",\"category_id\":\"$cat_insurance\",\"purchase_price\":50000,\"current_value\":50000,\"purchase_date\":\"2023-01-15\"}" > /dev/null
    log_success "创建: 重疾险"

    # 理财产品
    local cat_wealth=$(get_category_id "理财产品" "financial")
    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{\"name\":\"银行理财\",\"asset_type\":\"financial\",\"category_id\":\"$cat_wealth\",\"purchase_price\":200000,\"current_value\":208000,\"purchase_date\":\"2023-01-15\",\"interest_rate\":4.0,\"maturity_date\":\"2025-06-01\"}" > /dev/null
    log_success "创建: 银行理财"

    # 数字货币
    local cat_crypto=$(get_category_id "数字货币" "financial")
    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{\"name\":\"比特币\",\"asset_type\":\"financial\",\"category_id\":\"$cat_crypto\",\"purchase_price\":30000,\"current_value\":25000,\"purchase_date\":\"2023-01-15\"}" > /dev/null
    log_success "创建: 比特币"

    # 其他金融
    local cat_other=$(get_category_id "其他金融" "financial")
    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{\"name\":\"P2P理财\",\"asset_type\":\"financial\",\"category_id\":\"$cat_other\",\"purchase_price\":20000,\"current_value\":15000,\"purchase_date\":\"2023-01-15\"}" > /dev/null
    log_success "创建: P2P理财"
}

# 创建负债
create_liabilities() {
    log_info "========== 创建负债 =========="

    curl -sL -X POST "$BASE_URL/liabilities" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d '{"name":"招商信用卡","category":"credit_card","original_amount":50000,"remaining_amount":30000,"monthly_payment":3000,"interest_rate":18}' > /dev/null
    log_success "创建: 招商信用卡"

    curl -sL -X POST "$BASE_URL/liabilities" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d '{"name":"装修贷款","category":"personal_loan","original_amount":200000,"remaining_amount":150000,"monthly_payment":5000,"interest_rate":6}' > /dev/null
    log_success "创建: 装修贷款"

    curl -sL -X POST "$BASE_URL/liabilities" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d '{"name":"亲友借款","category":"other","original_amount":30000,"remaining_amount":20000,"monthly_payment":2000,"interest_rate":0}' > /dev/null
    log_success "创建: 亲友借款"
}

# 创建心愿
create_wishes() {
    log_info "========== 创建心愿 =========="

    curl -sL -X POST "$BASE_URL/wishes" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d '{"name":"换新房","expected_price":5000000,"priority":"high","description":"在市中心购买一套三室两厅"}' > /dev/null
    log_success "创建: 换新房"

    curl -sL -X POST "$BASE_URL/wishes" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d '{"name":"买新车","expected_price":500000,"priority":"high","description":"特斯拉 Model 3 或比亚迪汉 EV"}' > /dev/null
    log_success "创建: 买新车"

    curl -sL -X POST "$BASE_URL/wishes" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d '{"name":"出国旅游","expected_price":50000,"priority":"medium","description":"去欧洲旅游两周"}' > /dev/null
    log_success "创建: 出国旅游"

    curl -sL -X POST "$BASE_URL/wishes" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d '{"name":"换手机","expected_price":10000,"priority":"low"}' > /dev/null
    log_success "创建: 换手机"

    curl -sL -X POST "$BASE_URL/wishes" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d '{"name":"买相机","expected_price":20000,"priority":"medium","description":"索尼 A7M4 全画幅微单"}' > /dev/null
    log_success "创建: 买相机"
}

# 生成快照
generate_snapshots() {
    log_info "========== 生成快照 =========="

    curl -sL -X POST "$BASE_URL/family/snapshots/generate" \
        -H "Authorization: Bearer $TOKEN" > /dev/null
    log_success "快照已生成"
}

# 主流程
main() {
    log_info "=========================================="
    log_info "  完整测试数据生成"
    log_info "=========================================="

    get_token
    create_physical_assets
    create_financial_assets
    create_liabilities
    create_wishes
    generate_snapshots

    log_success "=========================================="
    log_success "  所有测试数据创建完成！"
    log_success "=========================================="
}

main
