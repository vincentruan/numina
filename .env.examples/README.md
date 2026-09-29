# .env 配置样板

本目录包含不同部署场景的 `.env` 配置模板。复制对应模板到项目根目录即可。

## 模板索引

### 根 `.env` (Docker 部署使用)

| 文件 | 场景 | 数据库 | Redis | 说明 |
|------|------|--------|-------|------|
| `.env-production` | 标准部署 | PostgreSQL | 可选 | 生产/测试/本地 PG 验证 |
| `.env-dev` | 开发部署 | SQLite | 无 | 快速本地验证, 零配置 |

### `server/.env` (本地开发 — `make dev-*` 命令使用)

| 文件 | 场景 | 说明 |
|------|------|------|
| `server.env.dev` | 本地开发 | 支持 SQLite / PostgreSQL 切换 |

## 快速切换

```bash
# 方式 1: Makefile 交互式选择
make setup-env-db

# 方式 2: 手动复制
cp .env.examples/.env-production .env       # 标准部署
cp .env.examples/.env-dev .env              # 开发部署
cp .env.examples/server.env.dev server/.env # 本地开发
```

## 两种部署模式对比

| 特性 | 标准部署 (production) | 开发部署 (dev) |
|------|----------------------|----------------|
| Compose 文件 | `docker-compose.yml` | `docker-compose.dev.yml` |
| 数据库 | PostgreSQL (容器) | SQLite (零配置) |
| Redis | 默认启用 (AI 能力依赖) | 无 |
| CAPTCHA | 启用 | 关闭 |
| 安全密钥 | 必须配置 | 有开发默认值 |
| 适用场景 | 生产/测试/正式验证 | 快速验证/开发调试 |

## Redis 何时可以关闭?

**默认启用 (推荐):** AI 能力依赖 Redis 的 StreamBridge 跨进程事件分发和共享缓存

**可关闭场景:** 纯资产管理, 完全不使用 AI 功能 (AI 聊天/报告/教练/叙事等)

关闭方式:
```bash
# 1. docker-compose.yml 中注释掉 redis 服务定义
# 2. 注释掉各服务中 Redis 相关环境变量:
#    REDIS_URL / CACHE_BACKEND / STREAM_BRIDGE_TYPE
# 3. 删除 depends_on redis 条件
# 4. .env 中设置:
STREAM_BRIDGE_TYPE=memory
CACHE_BACKEND=memory
```

## `server/.env` vs 根 `.env`

- **根 `.env`**: Docker 容器使用, 通过 `env_file: .env` 加载。数据库地址需用 Docker 可达的 hostname (`numina-postgres`)。
- **`server/.env`**: 本地开发使用, `make dev-backend` 等命令从 `server/` 目录读取。数据库地址用 `localhost`。

两个文件在本地开发时共存。根 `.env` 仅供 `docker compose` 使用, `server/.env` 供本地进程使用。

## 关键区别: 数据库地址

| 运行环境 | PostgreSQL 地址 | 原因 |
|----------|----------------|------|
| 本地开发 (`make dev-*`) | `localhost:5432` | 进程直接在宿主机运行 |
| Docker 标准部署 | `numina-postgres:5432` | compose 网络内 DNS 解析 |
| Docker + 宿主机 PG | `host.docker.internal:5432` | 通过 Docker gateway 访问宿主机 |
