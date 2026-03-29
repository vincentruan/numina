# Numina 测试套件

## 目录结构

```
tests/
├── data/                    # 测试数据生成脚本
│   └── seed-data.sh         # 完整测试数据生成（demouser）
│
├── e2e/                     # E2E 端到端测试
│   ├── acceptance.sh        # API 验收测试
│   ├── extended.sh          # 扩展 API 测试
│   └── wishes-liabilities.sh # 心愿负债专项测试
│
├── screenshot/              # 截图测试
│   ├── capture.js           # 截图脚本（17个页面）
│   └── screenshots/         # 截图输出目录
│
└── docs/                    # 测试文档
    ├── TEST_DATA_SUMMARY.md
    └── WISHES_LIABILITIES_TEST_SUMMARY.md
```

## 统一测试账号

所有测试脚本统一使用 `demouser` 账号：

- **用户名**: `demouser`
- **密码**: `DemoPass123`
- **家庭**: `Demo Family`

## 使用方法

### 1. 生成测试数据

```bash
# 确保服务运行中
cd tests/data
./seed-data.sh
```

生成内容：
- 实物资产：房产、车辆、数码、家电、家具、珠宝、服饰、美妆、运动、玩具、宠物、乐器、箱包
- 金融资产：存款、基金、股票、债券、保险、理财产品、数字货币
- 负债：信用卡、贷款、其他负债
- 心愿：多个优先级的心愿

### 2. E2E API 测试

```bash
cd tests/e2e

# 基础验收测试
./acceptance.sh

# 扩展测试（CRUD、分类、标签、成员等）
./extended.sh

# 心愿负债专项测试
./wishes-liabilities.sh
```

### 3. 截图测试

```bash
cd tests/screenshot

# 安装依赖
npm install puppeteer

# 运行截图
node capture.js
```

截图输出到 `tests/screenshot/screenshots/` 目录。

## 测试覆盖

### API 端点

| 模块 | 覆盖端点 |
|------|---------|
| 认证 | 登录、注册、刷新 token |
| 资产 | CRUD、估值、统计 |
| 负债 | CRUD、详情 |
| 心愿 | CRUD、优先级 |
| 分类 | CRUD、图标 |
| 标签 | CRUD、关联 |
| 家庭 | 成员管理、邀请码 |
| 仪表盘 | 总览、趋势、分布 |
| 快照 | 生成、历史 |

### 页面截图

1. 登录页面
2. 注册页面
3. 加入家庭页面
4. 仪表盘总览
5. 仪表盘图表
6. 资产列表
7. 资产筛选
8. 资产详情
9. 资产创建表单
10. 负债列表
11. 负债详情
12. 心愿列表
13. 统计页面
14. 家庭页面
15. 设置页面
16. 分类管理
17. 标签管理

## 维护说明

- 测试数据脚本使用动态 token，无需手动更新
- 截图脚本使用 Puppeteer，需要 Chromium 环境
- E2E 测试依赖 `jq` 命令处理 JSON