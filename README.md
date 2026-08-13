# Numina - 家庭资产可视化管理系统

<div align="center">

**隐私优先的自托管家庭财务管理平台**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Vue 3](https://img.shields.io/badge/vue-3.x-green.svg)](https://vuejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)

[English](./README.en.md) | 简体中文

</div>

## 📖 项目简介

Numina 是一个完全自托管的家庭资产可视化管理系统，帮助家庭成员共同追踪、管理和可视化资产与负债。核心设计理念是**隐私安全**——所有财务数据完全掌握在自己手中，可部署在家庭局域网或私有云服务器。

### ✨ 核心特性

- 🏠 **全资产覆盖** — 实物资产（房产、车辆、数码等）+ 金融资产（存款、基金、股票等）
- 💳 **负债管理** — 房贷、车贷、信用卡追踪，自动计算净资产
- 👨‍👩‍👧‍👦 **多用户家庭** — 成员各自记录，家庭级汇总视图，数据完全隔离
- 📊 **数据可视化** — 财务仪表盘、净资产趋势、资产配置分布
- 💰 **智能分析** — 日耗计算、低使用率提醒、投资收益排行
- 🤖 **AI 助理** — 对话式财务助理、财务教练、心愿建议、资产报告、PDF 导入（DeerFlow/LangChain 多 Provider）
- ⭐ **儿童激励系统** — 家务赚星星币、心愿兑现、三级货币体系，培养财务意识
- 🔐 **隐私安全** — 完全自托管，JWT 认证，bcrypt 加密
- 📱 **移动优先** — 响应式设计，适配手机浏览器
- 🐳 **一键部署** — Docker Compose 快速启动

## 🛠️ 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Vue 3 + TypeScript + Vite + Vant 4 + ECharts |
| 后端 | Python 3.12+ + FastAPI + SQLAlchemy + Alembic |
| Agent | Python 3.12+ + FastAPI + DeerFlow/LangChain |
| 数据库 | SQLite |
| 部署 | Docker + docker-compose + Nginx |

## 🚀 快速开始

### 前置要求

- Docker 和 Docker Compose
- （可选）Python 3.12+ 和 Node.js 18+ 以及 [uv](https://docs.astral.sh/uv/) 用于本地开发

### Docker 部署（推荐）

```bash
# 1. 克隆仓库
git clone https://github.com/vincentruan/numina.git
cd numina

# 2. 初始化（自动生成密钥 + .env + 数据目录）
make setup

# 3. 启动服务
make deploy

# 4. 生成家庭邀请码（注册需要）
make setup-invitation-codes

# 5. 访问应用 — 浏览器打开 http://localhost
```

> **预构建镜像：** 运行 `make deploy-images` 可直接拉取 GHCR 最新镜像，无需本地编译。

**环境变量**（可选，`make setup` 已自动生成）：

```env
PORT=8080                                    # Nginx 端口
SECRET_KEY=your-secret-key-here              # JWT 签名密钥（生产环境必须设置）
DATABASE_URL=sqlite:////app/.numina/data/numina.db   # 数据库路径
SNOWFLAKE_MACHINE_ID=1                       # Snowflake ID 机器编号（0-1023）
```

完整配置参考：[docs/configuration.md](docs/configuration.md)

### 更新

```bash
git pull origin main
make deploy           # 本地构建
# 或
make deploy-images    # 拉取预构建镜像
```

### 数据备份

SQLite 数据库位于 `./.numina/data/db/numina.db`，定期备份此文件即可。

```bash
cp ./.numina/data/db/numina.db ./backups/numina-$(date +%Y%m%d).db
```

### 本地开发

各模块的开发说明见对应 README：[后端](./server/apps/backend/README.md) · [前端](./frontend/apps/main/README.md) · [Agent](./server/apps/agent/README.md)

## 🗂️ 项目结构

```
numina/
├── server/                     # Python 服务端 monorepo (uv)
│   ├── apps/
│   │   ├── backend/            # FastAPI 核心后端
│   │   ├── agent/              # AI 分析微服务
│   │   └── scheduler_worker/   # 定时任务执行器
│   ├── packages/               # 共享 Python 包 (core/db/domain/security/storage)
│   ├── tests/                  # 统一测试集
│   └── pyproject.toml
├── frontend/                   # Vue 3 前端 monorepo (pnpm)
│   ├── apps/
│   │   ├── main/               # 成人端
│   │   └── child/              # 儿童端
│   └── packages/               # 共享包 (auth/math)
├── docker-compose.yml
├── nginx.conf
└── docs/                       # 项目文档
```

## 📚 文档与开发

| 文档 | 说明 |
|------|------|
| [架构文档](./docs/ARCHITECTURE.md) | 系统架构、模块划分 |
| [数据模型](./docs/DATA_MODELS.md) | 实体关系、字段定义 |
| [API 规范](./docs/API_SPEC.md) | 端点列表、请求响应格式 |
| [测试规范](./tests/docs/TEST_SPEC.md) | 测试账号、E2E 测试 |

后端启动后访问自动生成的 API 文档：Swagger UI `http://localhost:8000/docs` · ReDoc `http://localhost:8000/redoc`

## 🤝 贡献

欢迎贡献代码、报告问题或提出建议！Fork → 特性分支 → Commit → Push → Pull Request。

## 📄 许可证

[MIT License](LICENSE)

---

<div align="center">

**用心记录，明智决策 💰**

Made with ❤️ by Numina Team

</div>
