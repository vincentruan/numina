# Numina 仿真测试数据

独立 Python 脚本，向任意数据库注入结构化测试数据，覆盖项目全场景功能。

## 快速开始

```bash
cd tests/data

# 使用测试库
python seed_data.py --db-url sqlite:///test.db

# 使用生产库（需 --force 绕过安全检查）
python seed_data.py --db-url postgresql://... --force

# 重建所有 seed 账号
python seed_data.py --db-url ... --reset

# 跳过 demouser 完整数据
python seed_data.py --db-url ... --skip-demo

# 读取环境变量
TEST_DATABASE_URL=sqlite:///test.db python seed_data.py
```

## 测试账户

### 成人账户

| 用户名 | 密码 | 角色 | 场景 |
|--------|------|------|------|
| `test_empty` | `TestEmpty123!` | owner | 空家庭，无任何数据 |
| `test_asset` | `TestAsset123!` | owner | 单资产（MacBook Pro） |
| `test_rich` | `TestRich123!` | owner | 完整数据（5资产+2负债+3心愿+1儿童） |
| `demouser` | `DemoPass123` | owner | 完整仿真（见下方详情） |
| `demouser_spouse` | `DemoPass123` | member | demouser 的配偶账号 |

### 儿童账户（demouser 家庭）

儿童账号无用户名，通过家庭 ID + PIN 登录儿童端 app。

| 显示名 | PIN | 星星币余额 | 说明 |
|--------|-----|-----------|------|
| 小宝 | `🐰🥕🌈` | 200 + 任务奖励 | 有已完成任务实例（最近3天） |
| 大宝 | `🐻🍯🌟` | 150 | 有待审核心愿 |

## 数据场景详情

### test_empty — 空家庭

- 家庭已创建，无资产、负债、心愿、儿童

### test_asset — 单资产

- 1 个实物资产：MacBook Pro 16寸（数码类）
- 无负债、无心愿

### test_rich — 完整数据

- **5 资产**：住宅、宝马5系、MacBook Pro、iPhone 15 Pro、沪深300基金
- **2 负债**：住房贷款（关联住宅）、车贷（关联宝马）
- **3 心愿**：特斯拉 Model Y（pending）、日本旅行（pending）、欧洲蜜月（realized）
- **1 儿童**：小明（无 PIN，无任务数据）

### demouser — 完整仿真

#### 资产（30 项）

**19 实物资产**

| 名称 | 分类 | 购入价 | 当前价值 |
|------|------|--------|---------|
| 上海浦东新区住宅 | 房产 | 350万 | 420万 |
| 宝马 5 系 | 车辆 | 38万 | 28万 |
| MacBook Pro 16寸 | 数码 | 19,999 | 14,000 |
| iPhone 15 Pro Max | 数码 | 9,999 | 8,500 |
| iPad Pro 12.9寸 | 数码 | 8,999 | 7,000 |
| 索尼 A7M4 相机 | 数码 | 18,000 | 15,000 |
| LG 65寸 OLED 电视 | 家电 | 12,000 | 9,000 |
| 戴森吸尘器 V15 | 家电 | 4,500 | 3,500 |
| 美的空调 3匹 | 家电 | 6,800 | 5,000 |
| 宜家沙发三人位 | 家具 | 5,999 | 4,000 |
| 实木餐桌六人位 | 家具 | 8,800 | 7,000 |
| 卡地亚戒指 | 珠宝 | 25,000 | 28,000 |
| Hermès 铂金包 | 箱包 | 80,000 | 95,000 |
| 耐克跑步机 | 运动 | 8,000 | 5,000 |
| 雅马哈钢琴 | 乐器 | 35,000 | 30,000 |
| 乐高 42143 法拉利 | 玩具 | 1,299 | 800 |
| 柯基犬 — 豆豆 | 宠物 | 5,000 | 5,000 |
| Chanel 香水套装 | 美妆 | 3,200 | 2,000 |
| 百达翡丽手表 | 珠宝 | 120,000 | 135,000 |

**11 金融资产**

| 名称 | 分类 | 机构 |
|------|------|------|
| 招商银行活期 | 存款 | 招商银行 |
| 工商银行定期 3年 | 存款 | 工商银行 |
| 沪深300指数基金 | 基金 | 支付宝 |
| 医疗行业基金 | 基金 | 天天基金 |
| 贵州茅台股票 | 股票 | 华泰证券 |
| 腾讯控股港股 | 股票 | 富途证券 |
| 国债 2024-05 | 债券 | 中国银行 |
| 平安重疾险 | 保险 | 平安保险 |
| 招商银行理财 R2 | 理财产品 | 招商银行 |
| 比特币 0.5 BTC | 数字货币 | 欧易 |
| 以太坊 5 ETH | 数字货币 | 币安 |

#### 负债（7 项）

| 名称 | 类型 | 关联资产 |
|------|------|---------|
| 住房贷款 | mortgage | 上海住宅 |
| 车贷 | car_loan | 宝马 5 系 |
| 信用卡 — 招行 | credit_card | — |
| 信用卡 — 建行 | credit_card | — |
| 消费贷 — 装修 | consumer_loan | — |
| 花呗 | consumer_loan | — |
| 京东白条 | consumer_loan | — |

#### 心愿（9 项）

| 名称 | 状态 | 优先级 |
|------|------|--------|
| 特斯拉 Model Y | pending | high |
| 日本家庭旅行 | pending | high |
| 钢琴课程年卡 | pending | medium |
| Dyson 空气净化器 | pending | medium |
| Switch 游戏机 | pending | low |
| 家庭健身器材 | pending | medium |
| 欧洲蜜月旅行 | **realized** | high |
| MacBook Air M2 | **realized** | medium |
| 咖啡机 | **cancelled** | low |

#### 儿童功能

**任务模板（5 个）**

| 任务 | 奖励 | 频率 | 分配方式 |
|------|------|------|---------|
| 整理房间 🧹 | 10 星星币 | daily | pool |
| 洗碗 🍽️ | 8 星星币 | daily | pool |
| 倒垃圾 🗑️ | 5 星星币 | daily | assigned |
| 完成作业 📚 | 15 星星币 | daily | pool |
| 浇花 🌱 | 5 星星币 | daily | assigned |

**任务实例**：小宝最近 3 天每个模板各有 1 条 `approved` 实例（共 15 条）

**星星币**：小宝 200（期末考试奖励 🏆），大宝 150（生日礼物 🎂）

**儿童心愿（5 项）**

| 儿童 | 心愿 | 费用 | 状态 |
|------|------|------|------|
| 小宝 | 乐高星球大战 🧱 | 200 | active |
| 小宝 | 任天堂 Switch 🎮 | 500 | pending_review |
| 小宝 | 画画课程 🎨 | 150 | active |
| 大宝 | 芭比娃娃套装 🪆 | 120 | active |
| 大宝 | 迪士尼乐园门票 🏰 | 300 | pending_review |

**盲盒**：已启用，5 个礼物（冰淇淋、电影票、披萨、游乐场、新玩具）

## 目录结构

```
tests/data/
├── seed_data.py          # 主入口 CLI
├── db.py                 # 数据库连接初始化
├── models.py             # 独立 ORM 模型（不依赖 backend）
├── safety.py             # 生产库安全检查
├── factories/
│   ├── users.py          # UserFactory, FamilyFactory
│   ├── assets.py         # AssetFactory
│   ├── liabilities.py    # LiabilityFactory
│   ├── wishes.py         # WishFactory, ChildWishFactory
│   ├── children.py       # ChoreFactory, CoinFactory
│   └── blindbox.py       # BlindBoxFactory
└── scenarios/
    ├── empty.py          # test_empty
    ├── single_asset.py   # test_asset
    ├── full.py           # test_rich
    └── demo.py           # demouser（完整仿真）
```

## 依赖

```
sqlalchemy
bcrypt
```

无需安装 backend 依赖，models.py 是独立的 ORM 定义。兼容 Python 3.9+。
