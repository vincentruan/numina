# .env 配置样板

本目录包含不同部署场景的 `.env` 配置模板。复制对应模板到项目根目录即可。

## 模板索引

### 根 `.env` (Docker 部署 + 本地开发共用)

| 文件 | 场景 | 数据库 | 说明 |
|------|------|--------|------|
| `.env.dev-sqlite` | 本地开发 | SQLite | 最简配置，无需外部依赖 |
| `.env.dev-pgsql-local` | 本地开发 | 本地 PostgreSQL | `localhost:5432`，支持 DeerFlow checkpoint |
| `.env.dev-pgsql-remote` | 本地开发 | 远程 PostgreSQL | `<HOST>:5432`，替换为实际地址 |
| `.env.docker-sqlite` | Docker 部署 | SQLite | `make up` / `make deploy-dev` |
| `.env.docker-pgsql-docker` | Docker 部署 | Docker PostgreSQL | 同一 compose 网络，`numina-postgres` 容器 |
| `.env.docker-pgsql-host` | Docker 部署 | 宿主机/远程 PostgreSQL | `host.docker.internal:5432`，需 `extra_hosts` |

### `server/.env` (仅本地开发 — `make dev-*` 命令使用)

| 文件 | 场景 | 说明 |
|------|------|------|
| `server.env.dev-sqlite` | 本地 + SQLite | 无需 PostgreSQL |
| `server.env.dev-pgsql` | 本地 + PostgreSQL | `localhost:5432` |

## 快速切换

```bash
# 方式 1: Makefile 交互式选择
make setup-env-db

# 方式 2: 手动复制
cp .env.examples/.env.docker-pgsql-host .env
cp .env.examples/server.env.dev-pgsql server/.env
```

## 关键区别: `localhost` vs `host.docker.internal` vs `numina-postgres`

| 运行环境 | PostgreSQL 地址 | 原因 |
|----------|----------------|------|
| 本地开发 (`make dev-*`) | `localhost:5432` | 进程直接在宿主机运行 |
| Docker + PG 容器 | `numina-postgres:5432` | compose 网络内 DNS 解析 |
| Docker + 宿主机 PG | `host.docker.internal:5432` | 通过 Docker gateway 访问宿主机 |
| Docker + 远程 PG | `<remote-host>:5432` | 直接网络连接 |

## `server/.env` vs 根 `.env`

- **根 `.env`**: Docker 容器使用，通过 `env_file: .env` 加载。数据库地址需用 Docker 可达的 hostname。
- **`server/.env`**: 本地开发使用，`make dev-backend` 等命令从 `server/` 目录读取。数据库地址用 `localhost`。

两个文件会同时存在。本地开发时，根 `.env` 仅供 `docker compose` 使用，`server/.env` 供本地进程使用。
