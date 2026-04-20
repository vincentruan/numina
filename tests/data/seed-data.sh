#!/bin/bash

# 完整测试数据生成脚本
# 包含：实物资产、金融资产、负债、心愿
# 更新：补充资产新字段（currency, status, location, institution, notes等）
#       补充负债新字段（currency, start_date, end_date, institution, notes）
#       补充心愿新字段（category_id, currency, description）

set -e

BASE_URL="http://localhost/api/v1"
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
        -d '{"username":"demouser","password":"DemoPass123"}')

    TOKEN=$(echo "$response" | jq -r '.data.access_token')

    if [ -z "$TOKEN" ] || [ "$TOKEN" = "null" ]; then
        log_info "用户不存在，正在注册..."
        response=$(curl -sL -X POST "$BASE_URL/auth/register" \
            -H "Content-Type: application/json" \
            -d '{"username":"demouser","display_name":"Demo User","password":"DemoPass123","family_name":"Demo Family"}')
        TOKEN=$(echo "$response" | jq -r '.data.access_token')
    fi

    log_success "登录成功"
}

# 获取分类 ID
get_category_id() {
    local name=$1
    local asset_type=$2

    local response=$(curl -sL -X GET "$BASE_URL/categories?asset_type=$asset_type" \
        -H "Authorization: Bearer $TOKEN")

    echo "$response" | jq -r ".data[] | select(.name==\"$name\") | .id"
}

# 创建实物资产
create_physical_assets() {
    log_info "========== 创建实物资产 =========="

    # 房产 - 高价值资产
    local cat_house=$(get_category_id "房产" "physical")
    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{
            \"name\":\"深圳湾一号\",
            \"asset_type\":\"physical\",
            \"category_id\":\"$cat_house\",
            \"purchase_price\":25000000,
            \"current_value\":28000000,
            \"currency\":\"CNY\",
            \"purchase_date\":\"2020-01-15\",
            \"status\":\"in_use\",
            \"location\":\"深圳市南山区\",
            \"usage_frequency\":\"daily\",
            \"expected_lifespan_days\":36500,
            \"annual_maintenance_cost\":50000,
            \"notes\":\"豪宅，南山区海景房\",
            \"target_daily_cost\":800
        }" > /dev/null
    log_success "创建: 深圳湾一号"

    # 车辆 - 中等价值
    local cat_car=$(get_category_id "车辆" "physical")
    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{
            \"name\":\"宝马X5\",
            \"asset_type\":\"physical\",
            \"category_id\":\"$cat_car\",
            \"purchase_price\":450000,
            \"current_value\":380000,
            \"currency\":\"CNY\",
            \"purchase_date\":\"2022-06-01\",
            \"status\":\"in_use\",
            \"location\":\"深圳\",
            \"usage_frequency\":\"daily\",
            \"expected_lifespan_days\":3650,
            \"annual_maintenance_cost\":15000,
            \"notes\":\"2022款 xDrive40i\",
            \"target_daily_cost\":150
        }" > /dev/null
    log_success "创建: 宝马X5"

    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{
            \"name\":\"特斯拉Model 3\",
            \"asset_type\":\"physical\",
            \"category_id\":\"$cat_car\",
            \"purchase_price\":280000,
            \"current_value\":220000,
            \"currency\":\"CNY\",
            \"purchase_date\":\"2023-03-15\",
            \"status\":\"in_use\",
            \"location\":\"深圳\",
            \"usage_frequency\":\"daily\",
            \"expected_lifespan_days\":3650,
            \"annual_maintenance_cost\":5000,
            \"notes\":\"电动车，充电成本低\"
        }" > /dev/null
    log_success "创建: 特斯拉Model 3"

    # 数码 - 高频使用
    local cat_digital=$(get_category_id "数码" "physical")
    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{
            \"name\":\"MacBook Pro\",
            \"asset_type\":\"physical\",
            \"category_id\":\"$cat_digital\",
            \"purchase_price\":18000,
            \"current_value\":15000,
            \"currency\":\"CNY\",
            \"purchase_date\":\"2023-01-15\",
            \"status\":\"in_use\",
            \"location\":\"家中书房\",
            \"usage_frequency\":\"daily\",
            \"expected_lifespan_days\":1825,
            \"notes\":\"14寸 M2 Pro\",
            \"target_daily_cost\":15
        }" > /dev/null
    log_success "创建: MacBook Pro"

    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{
            \"name\":\"iPad Pro\",
            \"asset_type\":\"physical\",
            \"category_id\":\"$cat_digital\",
            \"purchase_price\":8000,
            \"current_value\":6500,
            \"currency\":\"CNY\",
            \"purchase_date\":\"2023-03-20\",
            \"status\":\"in_use\",
            \"location\":\"客厅\",
            \"usage_frequency\":\"weekly\",
            \"expected_lifespan_days\":1825,
            \"notes\":\"12.9寸 WiFi版\"
        }" > /dev/null
    log_success "创建: iPad Pro"

    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{
            \"name\":\"iPhone 15 Pro\",
            \"asset_type\":\"physical\",
            \"category_id\":\"$cat_digital\",
            \"purchase_price\":8999,
            \"current_value\":8000,
            \"currency\":\"CNY\",
            \"purchase_date\":\"2023-09-22\",
            \"status\":\"in_use\",
            \"location\":\"随身\",
            \"usage_frequency\":\"daily\",
            \"expected_lifespan_days\":1095,
            \"notes\":\"256GB 钛金属蓝色\"
        }" > /dev/null
    log_success "创建: iPhone 15 Pro"

    # 家电
    local cat_appliance=$(get_category_id "家电" "physical")
    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{
            \"name\":\"戴森吸尘器\",
            \"asset_type\":\"physical\",
            \"category_id\":\"$cat_appliance\",
            \"purchase_price\":4500,
            \"current_value\":3500,
            \"currency\":\"CNY\",
            \"purchase_date\":\"2023-05-10\",
            \"status\":\"in_use\",
            \"location\":\"客厅\",
            \"usage_frequency\":\"weekly\",
            \"expected_lifespan_days\":1825,
            \"annual_maintenance_cost\":200,
            \"notes\":\"V15 Detect\"
        }" > /dev/null
    log_success "创建: 戴森吸尘器"

    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{
            \"name\":\"美的空调\",
            \"asset_type\":\"physical\",
            \"category_id\":\"$cat_appliance\",
            \"purchase_price\":6000,
            \"current_value\":5000,
            \"currency\":\"CNY\",
            \"purchase_date\":\"2022-07-01\",
            \"status\":\"in_use\",
            \"location\":\"主卧\",
            \"usage_frequency\":\"daily\",
            \"expected_lifespan_days\":3650,
            \"annual_maintenance_cost\":100,
            \"notes\":\"1.5匹 变频\"
        }" > /dev/null
    log_success "创建: 美的空调"

    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{
            \"name\":\"西门子洗衣机\",
            \"asset_type\":\"physical\",
            \"category_id\":\"$cat_appliance\",
            \"purchase_price\":5500,
            \"current_value\":4500,
            \"currency\":\"CNY\",
            \"purchase_date\":\"2022-03-01\",
            \"status\":\"in_use\",
            \"location\":\"阳台\",
            \"usage_frequency\":\"weekly\",
            \"expected_lifespan_days\":3650,
            \"annual_maintenance_cost\":50,
            \"notes\":\"10公斤 滚筒\"
        }" > /dev/null
    log_success "创建: 西门子洗衣机"

    # 家具
    local cat_furniture=$(get_category_id "家具" "physical")
    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{
            \"name\":\"实木沙发\",
            \"asset_type\":\"physical\",
            \"category_id\":\"$cat_furniture\",
            \"purchase_price\":12000,
            \"current_value\":10000,
            \"currency\":\"CNY\",
            \"purchase_date\":\"2021-03-15\",
            \"status\":\"in_use\",
            \"location\":\"客厅\",
            \"usage_frequency\":\"daily\",
            \"expected_lifespan_days\":7300,
            \"notes\":\"北美黑胡桃木\"
        }" > /dev/null
    log_success "创建: 实木沙发"

    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{
            \"name\":\"餐桌椅套装\",
            \"asset_type\":\"physical\",
            \"category_id\":\"$cat_furniture\",
            \"purchase_price\":8000,
            \"current_value\":7000,
            \"currency\":\"CNY\",
            \"purchase_date\":\"2021-03-15\",
            \"status\":\"in_use\",
            \"location\":\"餐厅\",
            \"usage_frequency\":\"daily\",
            \"expected_lifespan_days\":7300,
            \"notes\":\"一桌六椅\"
        }" > /dev/null
    log_success "创建: 餐桌椅套装"

    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{
            \"name\":\"乳胶床垫\",
            \"asset_type\":\"physical\",
            \"category_id\":\"$cat_furniture\",
            \"purchase_price\":15000,
            \"current_value\":12000,
            \"currency\":\"CNY\",
            \"purchase_date\":\"2022-01-01\",
            \"status\":\"in_use\",
            \"location\":\"主卧\",
            \"usage_frequency\":\"daily\",
            \"expected_lifespan_days\":3650,
            \"notes\":\"King size 天然乳胶\"
        }" > /dev/null
    log_success "创建: 乳胶床垫"

    # 珠宝 - 保值资产
    local cat_jewelry=$(get_category_id "珠宝" "physical")
    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{
            \"name\":\"黄金项链\",
            \"asset_type\":\"physical\",
            \"category_id\":\"$cat_jewelry\",
            \"purchase_price\":15000,
            \"current_value\":18000,
            \"currency\":\"CNY\",
            \"purchase_date\":\"2020-12-20\",
            \"status\":\"in_use\",
            \"location\":\"保险箱\",
            \"usage_frequency\":\"monthly\",
            \"expected_lifespan_days\":36500,
            \"notes\":\"50克 足金\"
        }" > /dev/null
    log_success "创建: 黄金项链"

    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{
            \"name\":\"钻石戒指\",
            \"asset_type\":\"physical\",
            \"category_id\":\"$cat_jewelry\",
            \"purchase_price\":30000,
            \"current_value\":35000,
            \"currency\":\"CNY\",
            \"purchase_date\":\"2019-05-20\",
            \"status\":\"in_use\",
            \"location\":\"保险箱\",
            \"usage_frequency\":\"rarely\",
            \"expected_lifespan_days\":36500,
            \"notes\":\"1克拉 VS1净度\"
        }" > /dev/null
    log_success "创建: 钻石戒指"

    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{
            \"name\":\"黄金手镯\",
            \"asset_type\":\"physical\",
            \"category_id\":\"$cat_jewelry\",
            \"purchase_price\":25000,
            \"current_value\":32000,
            \"currency\":\"CNY\",
            \"purchase_date\":\"2021-02-14\",
            \"status\":\"in_use\",
            \"location\":\"保险箱\",
            \"usage_frequency\":\"monthly\",
            \"expected_lifespan_days\":36500,
            \"notes\":\"80克 古法金\"
        }" > /dev/null
    log_success "创建: 黄金手镯"

    # 服饰
    local cat_clothing=$(get_category_id "服饰" "physical")
    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{
            \"name\":\"羽绒服\",
            \"asset_type\":\"physical\",
            \"category_id\":\"$cat_clothing\",
            \"purchase_price\":2000,
            \"current_value\":1500,
            \"currency\":\"CNY\",
            \"purchase_date\":\"2023-11-01\",
            \"status\":\"in_use\",
            \"location\":\"衣帽间\",
            \"usage_frequency\":\"weekly\",
            \"expected_lifespan_days\":1825,
            \"notes\":\"Canada Goose\"
        }" > /dev/null
    log_success "创建: 羽绒服"

    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{
            \"name\":\"西装套装\",
            \"asset_type\":\"physical\",
            \"category_id\":\"$cat_clothing\",
            \"purchase_price\":5000,
            \"current_value\":4000,
            \"currency\":\"CNY\",
            \"purchase_date\":\"2023-03-01\",
            \"status\":\"in_use\",
            \"location\":\"衣帽间\",
            \"usage_frequency\":\"monthly\",
            \"expected_lifespan_days\":1825,
            \"annual_maintenance_cost\":200,
            \"notes\":\"定制款 意大利面料\"
        }" > /dev/null
    log_success "创建: 西装套装"

    # 美妆 - 消耗品
    local cat_beauty=$(get_category_id "美妆" "physical")
    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{
            \"name\":\"SK-II套装\",
            \"asset_type\":\"physical\",
            \"category_id\":\"$cat_beauty\",
            \"purchase_price\":3000,
            \"current_value\":2500,
            \"currency\":\"CNY\",
            \"purchase_date\":\"2024-01-01\",
            \"status\":\"in_use\",
            \"location\":\"浴室\",
            \"usage_frequency\":\"daily\",
            \"expected_lifespan_days\":730,
            \"notes\":\"神仙水+精华+面霜\"
        }" > /dev/null
    log_success "创建: SK-II套装"

    # 运动
    local cat_sports=$(get_category_id "运动" "physical")
    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{
            \"name\":\"跑步机\",
            \"asset_type\":\"physical\",
            \"category_id\":\"$cat_sports\",
            \"purchase_price\":5000,
            \"current_value\":4000,
            \"currency\":\"CNY\",
            \"purchase_date\":\"2022-09-01\",
            \"status\":\"in_use\",
            \"location\":\"健身房\",
            \"usage_frequency\":\"weekly\",
            \"expected_lifespan_days\":3650,
            \"annual_maintenance_cost\":100,
            \"notes\":\"NordicTrack\"
        }" > /dev/null
    log_success "创建: 跑步机"

    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{
            \"name\":\"自行车\",
            \"asset_type\":\"physical\",
            \"category_id\":\"$cat_sports\",
            \"purchase_price\":3000,
            \"current_value\":2500,
            \"currency\":\"CNY\",
            \"purchase_date\":\"2023-04-15\",
            \"status\":\"in_use\",
            \"location\":\"阳台\",
            \"usage_frequency\":\"monthly\",
            \"expected_lifespan_days\":3650,
            \"annual_maintenance_cost\":50,
            \"notes\":\"捷安特 山地车\"
        }" > /dev/null
    log_success "创建: 自行车"

    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{
            \"name\":\"哑铃套装\",
            \"asset_type\":\"physical\",
            \"category_id\":\"$cat_sports\",
            \"purchase_price\":2000,
            \"current_value\":1800,
            \"currency\":\"CNY\",
            \"purchase_date\":\"2023-06-01\",
            \"status\":\"in_use\",
            \"location\":\"健身房\",
            \"usage_frequency\":\"weekly\",
            \"expected_lifespan_days\":18250,
            \"notes\":\"可调节 2-24kg\"
        }" > /dev/null
    log_success "创建: 哑铃套装"

    # 玩具
    local cat_toys=$(get_category_id "玩具" "physical")
    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{
            \"name\":\"乐高积木\",
            \"asset_type\":\"physical\",
            \"category_id\":\"$cat_toys\",
            \"purchase_price\":2000,
            \"current_value\":1500,
            \"currency\":\"CNY\",
            \"purchase_date\":\"2023-12-25\",
            \"status\":\"in_use\",
            \"location\":\"儿童房\",
            \"usage_frequency\":\"monthly\",
            \"expected_lifespan_days\":1825,
            \"notes\":\"星球大战系列\"
        }" > /dev/null
    log_success "创建: 乐高积木"

    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{
            \"name\":\"Switch游戏机\",
            \"asset_type\":\"physical\",
            \"category_id\":\"$cat_toys\",
            \"purchase_price\":2500,
            \"current_value\":2000,
            \"currency\":\"CNY\",
            \"purchase_date\":\"2022-12-01\",
            \"status\":\"in_use\",
            \"location\":\"客厅\",
            \"usage_frequency\":\"weekly\",
            \"expected_lifespan_days\":1825,
            \"notes\":\"OLED版 含塞尔达\"
        }" > /dev/null
    log_success "创建: Switch游戏机"

    # 宠物
    local cat_pets=$(get_category_id "宠物" "physical")
    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{
            \"name\":\"金毛犬\",
            \"asset_type\":\"physical\",
            \"category_id\":\"$cat_pets\",
            \"purchase_price\":5000,
            \"current_value\":4000,
            \"currency\":\"CNY\",
            \"purchase_date\":\"2022-01-10\",
            \"status\":\"in_use\",
            \"location\":\"家中\",
            \"usage_frequency\":\"daily\",
            \"expected_lifespan_days\":3650,
            \"annual_maintenance_cost\":3000,
            \"notes\":\"名叫\"旺财\" 2岁\"
        }" > /dev/null
    log_success "创建: 金毛犬"

    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{
            \"name\":\"英短蓝猫\",
            \"asset_type\":\"physical\",
            \"category_id\":\"$cat_pets\",
            \"purchase_price\":3000,
            \"current_value\":2500,
            \"currency\":\"CNY\",
            \"purchase_date\":\"2023-03-01\",
            \"status\":\"in_use\",
            \"location\":\"家中\",
            \"usage_frequency\":\"daily\",
            \"expected_lifespan_days\":5475,
            \"annual_maintenance_cost\":2000,
            \"notes\":\"名叫\"小蓝\" 1岁\"
        }" > /dev/null
    log_success "创建: 英短蓝猫"

    # 乐器
    local cat_instrument=$(get_category_id "乐器" "physical")
    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{
            \"name\":\"雅马哈钢琴\",
            \"asset_type\":\"physical\",
            \"category_id\":\"$cat_instrument\",
            \"purchase_price\":30000,
            \"current_value\":28000,
            \"currency\":\"CNY\",
            \"purchase_date\":\"2020-08-15\",
            \"status\":\"in_use\",
            \"location\":\"琴房\",
            \"usage_frequency\":\"weekly\",
            \"expected_lifespan_days\":18250,
            \"annual_maintenance_cost\":500,
            \"notes\":\"U1 立式钢琴\"
        }" > /dev/null
    log_success "创建: 雅马哈钢琴"

    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{
            \"name\":\"吉他\",
            \"asset_type\":\"physical\",
            \"category_id\":\"$cat_instrument\",
            \"purchase_price\":5000,
            \"current_value\":4000,
            \"currency\":\"CNY\",
            \"purchase_date\":\"2022-05-01\",
            \"status\":\"in_use\",
            \"location\":\"书房\",
            \"usage_frequency\":\"weekly\",
            \"expected_lifespan_days\":7300,
            \"notes\":\"Martin D28\"
        }" > /dev/null
    log_success "创建: 吉他"

    # 箱包
    local cat_bags=$(get_category_id "箱包" "physical")
    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{
            \"name\":\"LV包\",
            \"asset_type\":\"physical\",
            \"category_id\":\"$cat_bags\",
            \"purchase_price\":15000,
            \"current_value\":12000,
            \"currency\":\"CNY\",
            \"purchase_date\":\"2022-11-11\",
            \"status\":\"in_use\",
            \"location\":\"衣帽间\",
            \"usage_frequency\":\"monthly\",
            \"expected_lifespan_days\":3650,
            \"notes\":\"Neverfull 中号\"
        }" > /dev/null
    log_success "创建: LV包"

    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{
            \"name\":\"Rimowa行李箱\",
            \"asset_type\":\"physical\",
            \"category_id\":\"$cat_bags\",
            \"purchase_price\":8000,
            \"current_value\":6500,
            \"currency\":\"CNY\",
            \"purchase_date\":\"2021-06-01\",
            \"status\":\"in_use\",
            \"location\":\"储物间\",
            \"usage_frequency\":\"rarely\",
            \"expected_lifespan_days\":7300,
            \"notes\":\"Classic 28寸\"
        }" > /dev/null
    log_success "创建: Rimowa行李箱"
}

# 创建金融资产
create_financial_assets() {
    log_info "========== 创建金融资产 =========="

    # 存款
    local cat_deposit=$(get_category_id "存款" "financial")
    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{
            \"name\":\"招商银行定存\",
            \"asset_type\":\"financial\",
            \"category_id\":\"$cat_deposit\",
            \"purchase_price\":300000,
            \"current_value\":315000,
            \"currency\":\"CNY\",
            \"purchase_date\":\"2023-01-15\",
            \"status\":\"in_use\",
            \"institution\":\"招商银行\",
            \"interest_rate\":2.5,
            \"maturity_date\":\"2027-01-01\",
            \"notes\":\"三年期大额存单\"
        }" > /dev/null
    log_success "创建: 招商银行定存"

    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{
            \"name\":\"工商银行活期\",
            \"asset_type\":\"financial\",
            \"category_id\":\"$cat_deposit\",
            \"purchase_price\":200000,
            \"current_value\":202000,
            \"currency\":\"CNY\",
            \"purchase_date\":\"2023-01-15\",
            \"status\":\"in_use\",
            \"institution\":\"工商银行\",
            \"interest_rate\":0.3,
            \"notes\":\"日常开支账户\"
        }" > /dev/null
    log_success "创建: 工商银行活期"

    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{
            \"name\":\"美元存款\",
            \"asset_type\":\"financial\",
            \"category_id\":\"$cat_deposit\",
            \"purchase_price\":50000,
            \"current_value\":52000,
            \"currency\":\"USD\",
            \"purchase_date\":\"2023-06-01\",
            \"status\":\"in_use\",
            \"institution\":\"中国银行\",
            \"interest_rate\":4.5,
            \"maturity_date\":\"2025-06-01\",
            \"notes\":\"两年期美元定存\"
        }" > /dev/null
    log_success "创建: 美元存款"

    # 基金
    local cat_fund=$(get_category_id "基金" "financial")
    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{
            \"name\":\"易方达蓝筹\",
            \"asset_type\":\"financial\",
            \"category_id\":\"$cat_fund\",
            \"purchase_price\":150000,
            \"current_value\":120000,
            \"currency\":\"CNY\",
            \"purchase_date\":\"2023-01-15\",
            \"status\":\"in_use\",
            \"institution\":\"易方达基金\",
            \"notes\":\"混合型基金 代码005827\"
        }" > /dev/null
    log_success "创建: 易方达蓝筹"

    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{
            \"name\":\"华夏成长\",
            \"asset_type\":\"financial\",
            \"category_id\":\"$cat_fund\",
            \"purchase_price\":80000,
            \"current_value\":75000,
            \"currency\":\"CNY\",
            \"purchase_date\":\"2023-01-15\",
            \"status\":\"in_use\",
            \"institution\":\"华夏基金\",
            \"notes\":\"股票型基金 代码000001\"
        }" > /dev/null
    log_success "创建: 华夏成长"

    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{
            \"name\":\"沪深300ETF\",
            \"asset_type\":\"financial\",
            \"category_id\":\"$cat_fund\",
            \"purchase_price\":100000,
            \"current_value\":95000,
            \"currency\":\"CNY\",
            \"purchase_date\":\"2022-07-01\",
            \"status\":\"in_use\",
            \"institution\":\"华泰柏瑞\",
            \"notes\":\"指数基金 代码510300\"
        }" > /dev/null
    log_success "创建: 沪深300ETF"

    # 股票
    local cat_stock=$(get_category_id "股票" "financial")
    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{
            \"name\":\"贵州茅台\",
            \"asset_type\":\"financial\",
            \"category_id\":\"$cat_stock\",
            \"purchase_price\":100000,
            \"current_value\":95000,
            \"currency\":\"CNY\",
            \"purchase_date\":\"2023-01-15\",
            \"status\":\"in_use\",
            \"institution\":\"中信证券\",
            \"notes\":\"50股 成本价2000元/股\"
        }" > /dev/null
    log_success "创建: 贵州茅台"

    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{
            \"name\":\"腾讯控股\",
            \"asset_type\":\"financial\",
            \"category_id\":\"$cat_stock\",
            \"purchase_price\":50000,
            \"current_value\":42000,
            \"currency\":\"HKD\",
            \"purchase_date\":\"2023-01-15\",
            \"status\":\"in_use\",
            \"institution\":\"富途证券\",
            \"notes\":\"港股 100股\"
        }" > /dev/null
    log_success "创建: 腾讯控股"

    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{
            \"name\":\"苹果股票\",
            \"asset_type\":\"financial\",
            \"category_id\":\"$cat_stock\",
            \"purchase_price\":80000,
            \"current_value\":95000,
            \"currency\":\"USD\",
            \"purchase_date\":\"2022-06-01\",
            \"status\":\"in_use\",
            \"institution\":\"盈透证券\",
            \"notes\":\"美股 AAPL 50股\"
        }" > /dev/null
    log_success "创建: 苹果股票"

    # 债券
    local cat_bond=$(get_category_id "债券" "financial")
    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{
            \"name\":\"国债\",
            \"asset_type\":\"financial\",
            \"category_id\":\"$cat_bond\",
            \"purchase_price\":100000,
            \"current_value\":105000,
            \"currency\":\"CNY\",
            \"purchase_date\":\"2023-01-15\",
            \"status\":\"in_use\",
            \"institution\":\"中国国债登记结算\",
            \"interest_rate\":3.2,
            \"maturity_date\":\"2028-01-01\",
            \"notes\":\"五年期储蓄国债\"
        }" > /dev/null
    log_success "创建: 国债"

    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{
            \"name\":\"企业债\",
            \"asset_type\":\"financial\",
            \"category_id\":\"$cat_bond\",
            \"purchase_price\":50000,
            \"current_value\":52000,
            \"currency\":\"CNY\",
            \"purchase_date\":\"2023-03-01\",
            \"status\":\"in_use\",
            \"institution\":\"深圳证券交易所\",
            \"interest_rate\":4.5,
            \"maturity_date\":\"2026-03-01\",
            \"notes\":\"万科企业债\"
        }" > /dev/null
    log_success "创建: 企业债"

    # 保险
    local cat_insurance=$(get_category_id "保险" "financial")
    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{
            \"name\":\"重疾险\",
            \"asset_type\":\"financial\",
            \"category_id\":\"$cat_insurance\",
            \"purchase_price\":50000,
            \"current_value\":50000,
            \"currency\":\"CNY\",
            \"purchase_date\":\"2023-01-15\",
            \"status\":\"in_use\",
            \"institution\":\"中国人寿\",
            \"notes\":\"保额50万 20年缴费\"
        }" > /dev/null
    log_success "创建: 重疾险"

    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{
            \"name\":\"年金险\",
            \"asset_type\":\"financial\",
            \"category_id\":\"$cat_insurance\",
            \"purchase_price\":100000,
            \"current_value\":105000,
            \"currency\":\"CNY\",
            \"purchase_date\":\"2022-01-01\",
            \"status\":\"in_use\",
            \"institution\":\"平安保险\",
            \"notes\":\"养老年金 60岁起领\"
        }" > /dev/null
    log_success "创建: 年金险"

    # 理财产品
    local cat_wealth=$(get_category_id "理财产品" "financial")
    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{
            \"name\":\"银行理财\",
            \"asset_type\":\"financial\",
            \"category_id\":\"$cat_wealth\",
            \"purchase_price\":200000,
            \"current_value\":208000,
            \"currency\":\"CNY\",
            \"purchase_date\":\"2023-01-15\",
            \"status\":\"in_use\",
            \"institution\":\"招商银行\",
            \"interest_rate\":4.0,
            \"maturity_date\":\"2025-06-01\",
            \"notes\":\"R2风险等级\"
        }" > /dev/null
    log_success "创建: 银行理财"

    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{
            \"name\":\"信托产品\",
            \"asset_type\":\"financial\",
            \"category_id\":\"$cat_wealth\",
            \"purchase_price\":300000,
            \"current_value\":315000,
            \"currency\":\"CNY\",
            \"purchase_date\":\"2022-09-01\",
            \"status\":\"in_use\",
            \"institution\":\"中融信托\",
            \"interest_rate\":6.5,
            \"maturity_date\":\"2025-09-01\",
            \"notes\":\"房地产信托\"
        }" > /dev/null
    log_success "创建: 信托产品"

    # 数字货币
    local cat_crypto=$(get_category_id "数字货币" "financial")
    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{
            \"name\":\"比特币\",
            \"asset_type\":\"financial\",
            \"category_id\":\"$cat_crypto\",
            \"purchase_price\":30000,
            \"current_value\":25000,
            \"currency\":\"USD\",
            \"purchase_date\":\"2023-01-15\",
            \"status\":\"in_use\",
            \"institution\":\"Coinbase\",
            \"notes\":\"0.5 BTC\"
        }" > /dev/null
    log_success "创建: 比特币"

    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{
            \"name\":\"以太坊\",
            \"asset_type\":\"financial\",
            \"category_id\":\"$cat_crypto\",
            \"purchase_price\":20000,
            \"current_value\":18000,
            \"currency\":\"USD\",
            \"purchase_date\":\"2023-03-01\",
            \"status\":\"in_use\",
            \"institution\":\"Binance\",
            \"notes\":\"10 ETH\"
        }" > /dev/null
    log_success "创建: 以太坊"

    # 其他金融
    local cat_other=$(get_category_id "其他金融" "financial")
    curl -sL -X POST "$BASE_URL/assets" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{
            \"name\":\"P2P理财\",
            \"asset_type\":\"financial\",
            \"category_id\":\"$cat_other\",
            \"purchase_price\":20000,
            \"current_value\":15000,
            \"currency\":\"CNY\",
            \"purchase_date\":\"2022-01-01\",
            \"status\":\"idle\",
            \"institution\":\"陆金所\",
            \"notes\":\"已退出 平台清算中\"
        }" > /dev/null
    log_success "创建: P2P理财"
}

# 创建负债
create_liabilities() {
    log_info "========== 创建负债 =========="

    # 房贷 - 最大负债
    curl -sL -X POST "$BASE_URL/liabilities" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d '{
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
        }' > /dev/null
    log_success "创建: 房贷"

    # 车贷
    curl -sL -X POST "$BASE_URL/liabilities" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d '{
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
        }' > /dev/null
    log_success "创建: 宝马车贷"

    # 信用卡
    curl -sL -X POST "$BASE_URL/liabilities" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d '{
            "name":"招商信用卡",
            "category":"credit_card",
            "original_amount":50000,
            "remaining_amount":30000,
            "monthly_payment":3000,
            "interest_rate":18,
            "institution":"招商银行",
            "currency":"CNY",
            "notes":"AE白金卡 本期账单分期"
        }' > /dev/null
    log_success "创建: 招商信用卡"

    curl -sL -X POST "$BASE_URL/liabilities" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d '{
            "name":"工商信用卡",
            "category":"credit_card",
            "original_amount":30000,
            "remaining_amount":15000,
            "monthly_payment":1500,
            "interest_rate":15,
            "institution":"工商银行",
            "currency":"CNY",
            "notes":"工资卡关联 自动还款"
        }' > /dev/null
    log_success "创建: 工商信用卡"

    # 个人贷款
    curl -sL -X POST "$BASE_URL/liabilities" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d '{
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
        }' > /dev/null
    log_success "创建: 装修贷款"

    curl -sL -X POST "$BASE_URL/liabilities" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d '{
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
        }' > /dev/null
    log_success "创建: 教育贷款"

    # 其他负债
    curl -sL -X POST "$BASE_URL/liabilities" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d '{
            "name":"亲友借款",
            "category":"other",
            "original_amount":30000,
            "remaining_amount":20000,
            "monthly_payment":2000,
            "interest_rate":0,
            "institution":"",
            "currency":"CNY",
            "notes":"向亲戚借款 无息"
        }' > /dev/null
    log_success "创建: 亲友借款"
}

# 创建心愿
create_wishes() {
    log_info "========== 创建心愿 =========="

    local cat_house=$(get_category_id "房产" "physical")
    local cat_car=$(get_category_id "车辆" "physical")
    local cat_digital=$(get_category_id "数码" "physical")
    local cat_sports=$(get_category_id "运动" "physical")
    local cat_instrument=$(get_category_id "乐器" "physical")
    local cat_jewelry=$(get_category_id "珠宝" "physical")

    # 高优先级心愿
    curl -sL -X POST "$BASE_URL/wishes" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{
            \"name\":\"换新房\",
            \"expected_price\":8000000,
            \"priority\":\"high\",
            \"category_id\":\"$cat_house\",
            \"currency\":\"CNY\",
            \"description\":\"在福田区购买一套四室两厅，改善居住环境\"
        }" > /dev/null
    log_success "创建: 换新房"

    curl -sL -X POST "$BASE_URL/wishes" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{
            \"name\":\"买新车\",
            \"expected_price\":600000,
            \"priority\":\"high\",
            \"category_id\":\"$cat_car\",
            \"currency\":\"CNY\",
            \"description\":\"保时捷 Cayenne 或 奔驰 GLE\"
        }" > /dev/null
    log_success "创建: 买新车"

    # 中优先级心愿
    curl -sL -X POST "$BASE_URL/wishes" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{
            \"name\":\"出国旅游\",
            \"expected_price\":80000,
            \"priority\":\"medium\",
            \"currency\":\"CNY\",
            \"description\":\"去欧洲旅游两周，意大利+法国+瑞士\"
        }" > /dev/null
    log_success "创建: 出国旅游"

    curl -sL -X POST "$BASE_URL/wishes" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{
            \"name\":\"买相机\",
            \"expected_price\":30000,
            \"priority\":\"medium\",
            \"category_id\":\"$cat_digital\",
            \"currency\":\"CNY\",
            \"description\":\"索尼 A7M4 全画幅微单 + 24-70mm 镜头\"
        }" > /dev/null
    log_success "创建: 买相机"

    curl -sL -X POST "$BASE_URL/wishes" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{
            \"name\":\"儿童钢琴\",
            \"expected_price\":50000,
            \"priority\":\"medium\",
            \"category_id\":\"$cat_instrument\",
            \"currency\":\"CNY\",
            \"description\":\"给孩子买一台雅马哈电钢琴\"
        }" > /dev/null
    log_success "创建: 儿童钢琴"

    curl -sL -X POST "$BASE_URL/wishes" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{
            \"name\":\"运动手表\",
            \"expected_price\":5000,
            \"priority\":\"medium\",
            \"category_id\":\"$cat_sports\",
            \"currency\":\"CNY\",
            \"description\":\"Apple Watch Ultra 或 Garmin Fenix\"
        }" > /dev/null
    log_success "创建: 运动手表"

    # 低优先级心愿
    curl -sL -X POST "$BASE_URL/wishes" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{
            \"name\":\"换手机\",
            \"expected_price\":12000,
            \"priority\":\"low\",
            \"category_id\":\"$cat_digital\",
            \"currency\":\"CNY\",
            \"description\":\"iPhone 16 Pro Max 256GB\"
        }" > /dev/null
    log_success "创建: 换手机"

    curl -sL -X POST "$BASE_URL/wishes" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{
            \"name\":\"名表\",
            \"expected_price\":150000,
            \"priority\":\"low\",
            \"category_id\":\"$cat_jewelry\",
            \"currency\":\"CNY\",
            \"description\":\"劳力士 Submariner 潜航者\"
        }" > /dev/null
    log_success "创建: 名表"

    curl -sL -X POST "$BASE_URL/wishes" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{
            \"name\":\"家庭影院\",
            \"expected_price\":40000,
            \"priority\":\"low\",
            \"currency\":\"CNY\",
            \"description\":\"投影仪+音响系统+电动幕布\"
        }" > /dev/null
    log_success "创建: 家庭影院"
}

# 生成快照
generate_snapshots() {
    log_info "========== 生成快照 =========="

    curl -sL -X POST "$BASE_URL/family/snapshots/generate" \
        -H "Authorization: Bearer $TOKEN" > /dev/null
    log_success "快照已生成"
}

# 显示统计
show_summary() {
    log_info "========== 数据统计 =========="

    echo ""
    echo "资产统计:"
    curl -sL -X GET "$BASE_URL/dashboard/overview" \
        -H "Authorization: Bearer $TOKEN" | jq -r '
        "  总资产价值: ¥\(.data.total_assets | floor | . / 10000 | floor)万",
        "  总负债: ¥\(.data.total_liabilities | floor | . / 10000 | floor)万",
        "  净资产: ¥\(.data.net_worth | floor | . / 10000 | floor)万"
        '

    echo ""
    echo "资产数量:"
    local physical_count=$(curl -sL -X GET "$BASE_URL/assets?asset_type=physical" \
        -H "Authorization: Bearer $TOKEN" | jq '.data | length')
    local financial_count=$(curl -sL -X GET "$BASE_URL/assets?asset_type=financial" \
        -H "Authorization: Bearer $TOKEN" | jq '.data | length')
    local liability_count=$(curl -sL -X GET "$BASE_URL/liabilities" \
        -H "Authorization: Bearer $TOKEN" | jq '.data | length')
    local wish_count=$(curl -sL -X GET "$BASE_URL/wishes" \
        -H "Authorization: Bearer $TOKEN" | jq '.data | length')

    echo "  实物资产: $physical_count 项"
    echo "  金融资产: $financial_count 项"
    echo "  负债: $liability_count 项"
    echo "  心愿: $wish_count 项"
    echo ""
}

# 主流程（由下方含儿童数据的 main() 覆盖）
# create_physical_assets, create_financial_assets 等在下方 main() 中调用

# 创建儿童数据
create_children_data() {
    log_info "========== 创建儿童数据 =========="

    # 幂等检查：如果已有儿童成员，跳过创建
    local existing_children=$(curl -sL "$BASE_URL/family/" -H "Authorization: Bearer $TOKEN" | jq '[.data.members[] | select(.role == "child")] | length')
    if [ "${existing_children:-0}" -ge 2 ] 2>/dev/null; then
        log_info "已存在 $existing_children 个儿童成员，跳过儿童数据创建（幂等保护）"
        return 0
    fi

    # 创建幼儿（6岁）
    local child1_resp=$(curl -sL -X POST "$BASE_URL/family/children" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d '{
            "display_name": "小宝",
            "avatar_color": "#FF6B6B",
            "pin": ["🐱", "🌟", "🎈", "🐶"]
        }')
    local child1_id=$(echo "$child1_resp" | jq -r '.data.id // .id')
    log_success "创建儿童: 小宝 (6岁幼儿) id=$child1_id"

    # 创建青少年（14岁）
    local child2_resp=$(curl -sL -X POST "$BASE_URL/family/children" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d '{
            "display_name": "大宝",
            "avatar_color": "#4ECDC4",
            "pin": ["🌈", "🍎", "🐸", "🦁"]
        }')
    local child2_id=$(echo "$child2_resp" | jq -r '.data.id // .id')
    log_success "创建儿童: 大宝 (14岁青少年) id=$child2_id"

    # 为两个孩子登录获取 child token
    local child1_token=$(curl -sL -X POST "$BASE_URL/auth/child/login" \
        -H "Content-Type: application/json" \
        -d "{\"child_id\":\"$child1_id\",\"pin_sequence\":[\"🐱\",\"🌟\",\"🎈\",\"🐶\"]}" \
        | jq -r '.data.access_token // .access_token')

    local child2_token=$(curl -sL -X POST "$BASE_URL/auth/child/login" \
        -H "Content-Type: application/json" \
        -d "{\"child_id\":\"$child2_id\",\"pin_sequence\":[\"🌈\",\"🍎\",\"🐸\",\"🦁\"]}" \
        | jq -r '.data.access_token // .access_token')

    # 给孩子充值星星币
    curl -sL -X POST "$BASE_URL/family/coins/grant" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{\"child_user_id\":\"$child1_id\",\"amount\":50,\"reason\":\"初始零花钱\"}" > /dev/null
    log_success "充值: 小宝 50 星星币"

    curl -sL -X POST "$BASE_URL/family/coins/grant" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d "{\"child_user_id\":\"$child2_id\",\"amount\":120,\"reason\":\"初始零花钱\"}" > /dev/null
    log_success "充值: 大宝 120 星星币"

    # 创建 child_wishes（pending_review 状态 — 孩子提交后等待家长审批）
    curl -sL -X POST "$BASE_URL/child/wishes" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $child1_token" \
        -d '{"title":"积木玩具","coin_cost":30,"description":"乐高城市系列"}' > /dev/null
    log_success "创建心愿: 小宝 - 积木玩具 (pending_review)"

    # 创建 child_wishes（active 状态 — 家长已批准）
    local wish2_resp=$(curl -sL -X POST "$BASE_URL/child/wishes" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $child2_token" \
        -d '{"title":"新耳机","coin_cost":80,"description":"无线蓝牙耳机"}')
    local wish2_id=$(echo "$wish2_resp" | jq -r '.data.id // .id')
    log_success "创建心愿: 大宝 - 新耳机 (提交审批)"

    # 家长批准心愿（变为 active）
    curl -sL -X POST "$BASE_URL/family/child-wishes/$wish2_id/approve" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d '{"coin_cost":80}' > /dev/null
    log_success "批准心愿: 大宝 - 新耳机 (active)"

    # 创建家务模板
    local tmpl1_resp=$(curl -sL -X POST "$BASE_URL/family/chore-templates" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d '{
            "title": "整理房间",
            "description": "整理床铺和书桌",
            "coin_reward": 5,
            "recurrence": "daily",
            "assigned_child_ids": []
        }')
    local tmpl1_id=$(echo "$tmpl1_resp" | jq -r '.data.id // .id')
    log_success "创建家务模板: 整理房间 (每日)"

    local tmpl2_resp=$(curl -sL -X POST "$BASE_URL/family/chore-templates" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $TOKEN" \
        -d '{
            "title": "洗碗",
            "description": "饭后洗碗",
            "coin_reward": 8,
            "recurrence": "daily",
            "assigned_child_ids": []
        }')
    local tmpl2_id=$(echo "$tmpl2_resp" | jq -r '.data.id // .id')
    log_success "创建家务模板: 洗碗 (每日)"

    # 孩子获取今日家务实例并完成一个（待审批状态）
    local today=$(date +%Y-%m-%d)
    local chores2=$(curl -sL -X GET "$BASE_URL/child/chores?date=$today" \
        -H "Authorization: Bearer $child2_token")
    local instance_id=$(echo "$chores2" | jq -r '.data[0].id // empty')

    if [ -n "$instance_id" ] && [ "$instance_id" != "null" ]; then
        curl -sL -X POST "$BASE_URL/child/chores/$instance_id/complete" \
            -H "Authorization: Bearer $child2_token" > /dev/null
        log_success "大宝完成家务: 待审批"
    else
        log_success "家务实例暂无（模板未分配给特定孩子）"
    fi
}

main() {
    log_info "=========================================="
    log_info "  完整测试数据生成（含儿童数据）"
    log_info "=========================================="

    get_token

    # 幂等检查：如果资产数量已达到预期，跳过创建
    local existing_count=$(curl -sL "$BASE_URL/assets" -H "Authorization: Bearer $TOKEN" | jq '.data | length')
    if [ "$existing_count" -ge 30 ] 2>/dev/null; then
        log_info "已存在 $existing_count 件资产，跳过资产/负债/心愿创建（幂等保护）"
    else
        create_physical_assets
        create_financial_assets
        create_liabilities
        create_wishes
        generate_snapshots
    fi

    create_children_data
    show_summary

    log_success "=========================================="
    log_success "  所有测试数据创建完成！"
    log_success "=========================================="
}

main