# Numina - 家庭资产可视化管理系统

<div align="center">

**隐私优先的自托管家庭财务管理平台**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Vue 3](https://img.shields.io/badge/vue-3.x-green.svg)](https://vuejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)

[English](./README.en.md) | 简体中文

</div>

## 📖 项目简介

Numina 是一个完全自托管的家庭资产可视化管理系统，帮助家庭成员共同追踪、管理和可视化资产与负债。核心设计理念是**隐私安全**——所有财务数据完全掌握在自己手中，可部署在家庭局域网或私有云服务器。

### ✨ 核心特性

- 🏠 **全资产覆盖** - 支持实物资产（房产、车辆、数码产品等）和金融资产（存款、基金、股票、债券等）
- 💳 **负债管理** - 房贷、车贷、信用卡等负债追踪，自动计算净资产
- 👨‍👩‍👧‍👦 **多用户家庭** - 家庭成员各自记录资产，支持家庭级汇总视图
- 📊 **数据可视化** - 财务仪表盘、净资产趋势图、资产配置饼图
- 💰 **智能分析** - 日耗计算、低使用率资产提醒、投资收益排行
- ⭐ **儿童激励系统** - 家务赚星星币、心愿兑现、三级货币体系，培养孩子财务意识
- 🔐 **隐私安全** - 完全自托管，数据不出家门，JWT 认证，bcrypt 密码加密
- 📱 **移动优先** - 响应式设计，适配手机浏览器访问
- 🐳 **一键部署** - Docker Compose 快速启动，支持局域网和云端部署


## 🛠️ 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Vue 3 + TypeScript + Vite + Vant 4 + ECharts |
| 后端 | Python 3.11+ + FastAPI + SQLAlchemy + Alembic |
| Agent | Python 3.11+ + FastAPI + DeerFlow/LangChain |
| 数据库 | SQLite |
| 认证 | JWT (access token + refresh token) |
| 部署 | Docker + docker-compose + Nginx |

## 🚀 快速开始

### 前置要求

- Docker 和 Docker Compose
- （可选）Python 3.11+ 和 Node.js 18+ 以及 [uv](https://docs.astral.sh/uv/) 用于本地开发

### 使用 Docker 部署（推荐）

```bash
# 1. 克隆仓库
git clone https://github.com/yourusername/numina.git
cd numina

# 2. 启动所有服务
docker-compose up -d

# 3. 访问应用
# 浏览器打开 http://localhost:8080
```

**环境变量配置**（可选）：

创建 `.env` 文件：

```env
PORT=8080                                    # Nginx 端口
SECRET_KEY=your-secret-key-here              # JWT 签名密钥（生产环境必须设置）
DATABASE_URL=sqlite:////app/data/numina.db   # 数据库路径
SNOWFLAKE_MACHINE_ID=1                       # Snowflake ID 机器编号（0-1023，多实例部署时设置）
```

完整配置参考（文件存储架构、所有环境变量、Docker 卷挂载、Git 备份）：[docs/configuration.md](docs/configuration.md)

### 本地开发

各模块的本地开发说明见对应模块的 README：[后端](./backend/README.md) · [前端](./frontend/README.md) · [Agent](./agent/README.md)

## 📊 功能概览

### 资产管理

- **实物资产**：房产、车辆、数码产品、家电、家具、珠宝、服饰、美妆、运动器材、玩具、宠物、乐器、箱包
- **金融资产**：存款、基金、股票、债券、保险、理财产品、数字货币
- **资产属性**：购入价格、当前价值、购入日期、使用频率、预期寿命、年维护成本
- **智能计算**：日耗成本、投资收益率、低使用率检测

### 负债管理

- **负债类型**：房贷、车贷、信用卡、个人贷款
- **负债属性**：原始金额、剩余本金、月供、年利率、起止日期、贷款机构
- **还款记录**：记录每笔还款，自动更新剩余本金，还清自动标记
- **关联资产**：负债可关联对应资产（如房贷关联房产）

### 数据可视化

- **财务仪表盘**：总资产、总负债、净资产、资产数量、月度变化
- **净资产趋势图**：按月/季/年展示净资产变化趋势
- **资产配置饼图**：各类资产占比分布
- **日耗排行榜**：展示每日使用成本最高的资产
- **低使用率提醒**：标记闲置或很少使用的资产
- **投资收益排行**：金融资产收益率排行

### 多用户与家庭

- **用户注册**：创建家庭并成为家庭所有者
- **邀请加入**：通过 6 位邀请码邀请家庭成员
- **角色管理**：所有者可管理成员角色
- **家庭汇总**：查看所有家庭成员的资产汇总
- **数据隔离**：不同家庭数据完全隔离

### ⭐ 儿童星星币系统

专为家庭中的孩子设计的激励系统，通过完成家务赚取星星币，培养财务意识和劳动习惯。

- **家务任务管理**：父母创建家务模板，分配给孩子，支持每日/每周/每月重复周期
- **星星币奖励**：孩子完成家务后提交审批，父母审核通过后自动发放星星币
- **连续完成奖励**：连续完成家务可获得额外奖励加成（连击奖励）
- **分层货币体系**：铜币 → 银币 → 金币三级兑换，兑换比例由父母在家庭设置中配置（默认 10:1）
- **星星账本**：孩子可查看完整的收支流水，支持向兄弟姐妹赠送星星币
- **心愿系统**：孩子提交心愿 → 父母审核并设定积分门槛 → 孩子攒够积分申请兑现 → 父母原子兑现并自动创建资产
- **宝贝收藏**：已兑现的心愿自动转为孩子名下的资产，在宝贝页面展示
- **父母管理仪表盘**：家庭页面展示每个孩子的余额、待审家务数、待审心愿数，快速跳转审批页面

## 📖 技术文档

| 文档 | 说明 |
|------|------|
| [架构文档](./docs/ARCHITECTURE.md) | 技术栈、系统架构、模块划分 |
| [数据模型](./docs/DATA_MODELS.md) | 实体关系、字段定义、分类体系 |
| [API 规范](./docs/API_SPEC.md) | 端点列表、认证方式、请求响应格式 |
| [前端组件](./docs/FRONTEND_COMPONENTS.md) | 页面路由、组件职责、Store 结构 |
| [编码规范](./docs/CODING_STANDARDS.md) | Vue 3 / FastAPI 编码风格 |
| [Git 工作流](./docs/GIT_WORKFLOW.md) | 分支策略、Commit 格式、PR 流程 |
| [测试规范](./tests/docs/TEST_SPEC.md) | 测试账号、测试数据、E2E 测试 |

## 🗂️ 项目结构

```
numina/
├── backend/                    # FastAPI 后端
│   ├── app/
│   │   ├── models/            # SQLAlchemy ORM 模型
│   │   ├── schemas/           # Pydantic 请求/响应模型
│   │   ├── routers/           # API 路由处理器
│   │   ├── services/          # 业务逻辑层
│   │   ├── auth/              # JWT 认证
│   │   └── seed/              # 数据库种子数据
│   ├── tests/                 # pytest 测试（566 个测试通过）
│   ├── alembic/               # 数据库迁移
│   └── Dockerfile
├── agent/                    # AI 分析微服务
│   ├── app/                  # 入口文件包
│   │   ├── main.py           # FastAPI 入口
│   │   ├── config.py         # 配置
│   │   ├── scheduler.py      # 定时任务
│   │   ├── routers/          # API 路由
│   │   ├── services/         # 业务逻辑
│   │   ├── schemas/          # 数据模型
│   │   └── core/             # 核心组件
│   └── tests/                # pytest 测试
├── frontend/                   # Vue 3 前端
│   ├── src/
│   │   ├── api/               # Axios API 客户端
│   │   ├── stores/            # Pinia 状态管理
│   │   ├── pages/             # 页面组件
│   │   ├── components/        # 可复用组件
│   │   ├── router/            # Vue Router 配置
│   │   └── types/             # TypeScript 类型定义
│   └── Dockerfile
├── docker-compose.yml          # Docker Compose 配置
├── nginx.conf                  # Nginx 反向代理配置
└── docs/                       # 项目文档
```

## 📚 模块文档

各模块的开发文档（快速启动、环境变量、架构、测试）：

| 模块 | README | 说明 |
|------|--------|------|
| 后端 | [backend/README.md](./backend/README.md) | FastAPI API 开发、数据库、测试 |
| Agent | [agent/README.md](./agent/README.md) | AI 微服务、DeerFlow 集成、技能 |
| 前端 | [frontend/README.md](./frontend/README.md) | Vue 3 UI 开发、组件、测试 |
| 测试 | [tests/README.md](./tests/README.md) | E2E 测试、数据生成、截图 |

## 🔐 安全特性

- **密码加密**：使用 bcrypt 哈希存储密码
- **JWT 认证**：access token (15分钟) + refresh token (7天)
- **自动刷新**：前端自动刷新过期 token，无感续期
- **家庭隔离**：用户只能访问自己家庭的数据
- **HTTPS 支持**：生产环境建议配置 HTTPS

## 📝 API 文档

启动后端服务后，访问以下地址查看自动生成的 API 文档：

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

完整端点列表见 [backend/README.md](./backend/README.md) 和 [agent/README.md](./agent/README.md)。

## 🧪 测试

后端包含 566 个自动化测试，覆盖认证、资产、负债、仪表盘、儿童星星币系统等核心功能。

详见各模块 README：[后端测试](./backend/README.md#测试) · [Agent 测试](./agent/README.md#测试) · [E2E 测试](./tests/README.md)

**测试结果**：✅ 566 passed

## 🚢 部署指南

### 局域网部署（家庭 NAS / 树莓派）

```bash
# 1. 克隆代码到 NAS
git clone https://github.com/yourusername/numina.git
cd numina

# 2. 启动服务
docker-compose up -d

# 3. 局域网内访问
# http://<NAS-IP>:8080
```

### 云服务器部署

```bash
# 1. 克隆代码
git clone https://github.com/yourusername/numina.git
cd numina

# 2. 配置环境变量
cat > .env << EOF
SECRET_KEY=$(openssl rand -base64 32)
PORT=8080
EOF

# 3. 启动服务
docker-compose up -d

# 4. 配置 HTTPS（推荐使用 Caddy 或 Nginx）
# 示例 Caddy 配置：
# numina.yourdomain.com {
#     reverse_proxy localhost:8080
# }
```

### 数据备份

SQLite 数据库文件位于 `./data/numina.db`，定期备份此文件即可。

```bash
# 备份数据库
cp ./data/numina.db ./backups/numina-$(date +%Y%m%d).db

# 恢复数据库
cp ./backups/numina-20260314.db ./data/numina.db
docker-compose restart backend
```

## 🗺️ 路线图

### ✅ MVP 已完成（当前版本）

- [x] 用户认证与家庭管理
- [x] 资产与负债 CRUD
- [x] 数据可视化仪表盘
- [x] 日耗计算与智能分析
- [x] Token 自动刷新
- [x] 负债还款记录
- [x] 566 个自动化测试

### ✅ 儿童星星币系统（已完成）

- [x] 家务任务管理（模板 + 分配 + 周期重复）
- [x] 星星币奖励与连击加成
- [x] 铜/银/金三级分层货币体系（父母可配置兑换比例）
- [x] 星星账本与兄弟姐妹赠币
- [x] 心愿系统（提交 → 审核 → 积分门槛 → 兑现申请 → 原子兑现）
- [x] 宝贝收藏（兑现心愿自动转为孩子名下资产）
- [x] 父母管理仪表盘（余额总览 + 待审批快捷入口）
- [x] 儿童专属 UI（独立底部导航、储蓄罐进度动效）

### ✅ Phase 2：智能分析（已完成）

- [x] 消费漏洞检测（高闲置成本、冗余持有、高维护负担三类规则 + LLM 建议）
- [x] 购买 vs 租赁对比计算器（盈亏平衡点计算、推荐结论）
- [x] 消费等价换算（日均成本、时间成本、机会成本三维度）

### 🔮 Phase 3：资产时光机（未来）

- [ ] 模拟不同消费选择的长远差异（what-if 分析）
- [ ] 基于历史数据推演未来财务状况
- [ ] 关联通胀率计算真实购买力变化

### 🔔 Phase 4：智能提醒（未来）

- [ ] 大额消费冷静期提醒
- [ ] 资产配置失衡警报
- [ ] 保险/保修到期提醒
- [ ] 理财产品到期提醒

### 📤 Phase 5：数据导入导出（未来）

- [ ] CSV/Excel 批量导入
- [ ] 月度/年度财务报告 PDF 生成

## 🤝 贡献指南

欢迎贡献代码、报告问题或提出建议！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

## 🙏 致谢

- UI 组件库：[Vant](https://vant-ui.github.io/)
- 图表库：[Apache ECharts](https://echarts.apache.org/)
- 后端框架：[FastAPI](https://fastapi.tiangolo.com/)
- 前端框架：[Vue.js](https://vuejs.org/)

## 📧 联系方式

如有问题或建议，欢迎通过以下方式联系：

- 提交 Issue: [GitHub Issues](https://github.com/yourusername/numina/issues)
- 邮箱: your.email@example.com

---

<div align="center">

**用心记录，明智决策 💰**

Made with ❤️ by Numina Team

</div>
