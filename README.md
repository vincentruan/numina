<div align="center">

<img src="./frontend/apps/main/public/favicon.svg" alt="Numina" width="80" />

# Numina

**隐私优先的自托管家庭财务管理平台**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Vue 3](https://img.shields.io/badge/vue-3.x-green.svg)](https://vuejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)

[English](./README.en.md) | 简体中文

</div>

## 项目简介

Numina 是一个完全自托管的家庭资产可视化管理系统，帮助家庭成员共同追踪、管理和可视化资产与负债。核心设计理念是**隐私安全**——所有财务数据完全掌握在自己手中，可部署在家庭局域网或私有云服务器。

### 核心特性

**资产管理**
- **全资产覆盖** — 实物资产（房产、车辆、数码等）+ 金融资产（存款、基金、股票等），支持多币种
- **负债管理** — 房贷、车贷、信用卡追踪，自动计算净资产
- **租约管理** — 房东收租 / 租客付租 / 双角色视图，押金与到期提醒
- **数据可视化** — 财务仪表盘、净资产趋势、资产配置分布、日均成本分析

**AI 能力**
- **对话式财务助理** — 基于 DeerFlow 的多 Provider AI 聊天，支持 Web 搜索和 MCP 工具
- **财务教练** — AI 驱动的个性化财务建议
- **资产报告** — AI 自动生成资产分析报告
- **心愿建议** — 智能心愿评估与建议
- **仪表盘叙事** — AI 驱动的财务摘要与洞察
- **PDF / 图片导入** — 扫描文档 AI 识别，批量导入资产

**家庭与儿童**
- **多用户家庭** — 成员各自记录，家庭级汇总视图，数据完全隔离
- **儿童激励系统** — 家务赚星星币、心愿兑现、盲盒抽奖、三级货币体系
- **财商素养** — 学习场景、徽章系统、AI 周报
- **家庭宣言** — 可签署的家庭财务目标与承诺

**安全与体验**
- **隐私安全** — 完全自托管，JWT 认证，bcrypt 加密，文件加密存储
- **移动优先** — 响应式 H5 设计，适配手机浏览器
- **暗黑模式** — 自动跟随系统主题
- **一键部署** — Docker Compose 快速启动，支持 GHCR 预构建镜像

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Vue 3 + TypeScript + Vite + Vant 4 + ECharts + Pinia |
| 后端 | Python 3.12+ · FastAPI · SQLAlchemy 2.0 · Alembic |
| AI Agent | Python 3.12+ · DeerFlow · LangChain · 多 Provider (OpenAI / Anthropic / Ollama) |
| 数据库 | SQLite (默认) · PostgreSQL · MySQL |
| 部署 | Docker Compose · Nginx · GHCR 镜像 |

## 快速开始

### 前置要求

- Docker 和 Docker Compose
- (可选) Python 3.12+ 和 Node.js 18+ 以及 [uv](https://docs.astral.sh/uv/) 用于本地开发

### Docker 部署（推荐）

```bash
# 1. 克隆仓库
git clone https://github.com/vincentruan/numina.git
cd numina

# 2. 初始化（自动生成密钥 + .env + 数据目录 + 邀请码）
make setup

# 3. 启动服务
make deploy

# 4. 访问应用 — 浏览器打开 http://localhost
```

> **预构建镜像：** 运行 `make deploy-images` 可直接拉取 GHCR 最新镜像，无需本地编译。

### 环境变量

`make setup` 已自动生成，完整配置参考：[docs/configuration.md](docs/configuration.md)

```env
PORT=8080                                    # Nginx 端口
SECRET_KEY=your-secret-key-here              # JWT 签名密钥（生产环境必须设置）
DATABASE_URL=sqlite:////app/.numina/data/numina.db   # 数据库路径
SNOWFLAKE_MACHINE_ID=1                       # Snowflake ID 机器编号（0-1023）
```

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

```bash
make install          # 安装全部依赖 (uv + pnpm)
make dev-all          # 同时启动 5 个 dev server (backend/agent/worker/frontend/child)
make stop-dev-all     # 停止全部 dev server
```

各模块的开发说明见对应 README：[后端](./server/apps/backend/README.md) · [前端](./frontend/apps/main/README.md) · [Agent](./server/apps/agent/README.md)

## 项目结构

```
numina/
├── server/                     # Python 服务端 monorepo (uv workspace)
│   ├── apps/
│   │   ├── backend/            # FastAPI 核心后端 (:8000)
│   │   ├── agent/              # AI 分析微服务 (DeerFlow, :8001)
│   │   └── scheduler_worker/   # 定时任务执行器 (:8002)
│   ├── packages/               # 共享 Python 包
│   │   ├── core/               # 基础设施 (配置、Snowflake ID、熔断器)
│   │   ├── db/                 # SQLAlchemy 模型与数据库会话
│   │   ├── domain/             # 领域逻辑与计算
│   │   ├── security/           # 认证、加密、JWT
│   │   └── storage/            # 文件存储与加密
│   ├── tests/                  # 统一测试集
│   └── pyproject.toml
├── frontend/                   # Vue 3 前端 monorepo (pnpm workspace)
│   ├── apps/
│   │   ├── main/               # 成人端 H5 (:5173)
│   │   └── child/              # 儿童端 H5 (:5174)
│   └── packages/
│       ├── auth/               # @numina/auth — 认证共享包
│       └── math/               # @numina/math — 业务计算函数
├── tests/                      # E2E / 视觉回归测试
├── docs/                       # 项目文档
├── docker-compose.yml          # 开发 / 默认部署
├── docker-compose.production.yml  # 生产部署 (GHCR 镜像)
└── Makefile                    # 统一命令入口
```

## 文档

| 文档 | 说明 |
|------|------|
| [架构文档](./docs/ARCHITECTURE.md) | 系统架构、模块划分、数据流 |
| [数据模型](./docs/DATA_MODELS.md) | 实体关系、字段定义、计算逻辑 |
| [API 规范](./docs/API_SPEC.md) | 端点列表、请求响应格式 |
| [配置参考](./docs/configuration.md) | 环境变量、数据库配置 |
| [部署指南](./docs/deployment.md) | 生产部署、镜像管理 |

后端启动后访问自动生成的 API 文档：Swagger UI `http://localhost:8000/docs` · ReDoc `http://localhost:8000/redoc`

---

<div align="center">

**用心记录，明智决策**

Made with ❤️ by Numina Team

</div>
