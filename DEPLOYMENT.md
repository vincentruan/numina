# Numina 部署指南

本文档记录 Numina 家庭资产管理系统的部署流程。所有操作均通过 `make` 完成。

## 目录

- [前置条件](#前置条件)
- [快速开始](#快速开始)
- [初始化配置](#初始化配置)
- [数据库选择](#数据库选择)
- [域名与 HTTPS](#域名与-https)
- [生产部署](#生产部署)
- [更新与回滚](#更新与回滚)
- [备份与恢复](#备份与恢复)
- [常见问题](#常见问题)

## 前置条件

### 服务器要求

- **操作系统**: Linux (Ubuntu 20.04+ / CentOS 8+ 推荐)
- **内存**: 最低 1GB，推荐 2GB+
- **磁盘**: 最低 10GB 可用空间
- **网络**: 公网 IP，开放 80/443 端口

### 软件要求

- Docker 20.10+ 与 Docker Compose v2+
- Git
- OpenSSL（用于生成密钥）
- Python 3.10+（用于生成 Fernet 加密密钥）

## 快速开始

最简三步完成部署：

```bash
# 1. 克隆代码
git clone https://github.com/YOUR_USERNAME/numina.git
cd numina

# 2. 交互式初始化（自动生成密钥、.env、数据目录）
make setup

# 3. 启动服务（本地构建）
make deploy
```

部署完成后访问 http://localhost，然后生成邀请码：

```bash
make setup-invitation-codes
```

### 使用预构建镜像（推荐）

如果不想在服务器上编译，可以直接拉取 GitHub Actions 构建的镜像：

```bash
make setup
make deploy-images    # 自动从 GHCR 拉取最新镜像
```

> 首次运行会自动将 GHCR 地址写入 `.env`，无需手动配置。

## 初始化配置

### 一键初始化

```bash
make setup
```

该命令会依次执行：
1. **创建数据目录** — `.numina/data/{db,uploads}`
2. **生成 .env 配置** — 自动填充所有安全密钥（如已存在则检查补全）
3. **初始化数据库** — 默认 SQLite（可通过 `NUMINA_DB` 变量选择）

### 分步初始化

如需更精细的控制：

```bash
# 仅生成安全密钥（不写入文件）
make setup-keys

# 仅生成 .env（从模板创建，自动填充密钥）
make setup-env

# 仅创建数据目录
make setup-data

# 初始化数据库（默认 SQLite）
make setup-db

# 使用 MySQL
NUMINA_DB=mysql make setup-db

# 使用 PostgreSQL
NUMINA_DB=postgres make setup-db
```

### 安全密钥说明

| 密钥 | 用途 | 格式 | 生成方式 |
|------|------|------|----------|
| `SECRET_KEY` | JWT 签名 | hex (64 字符) | `openssl rand -hex 32` |
| `ALTCHA_HMAC_KEY` | CAPTCHA 验证 | hex (64 字符) | `openssl rand -hex 32` |
| `AI_ENCRYPTION_KEY` | AI API Key 加密 | Fernet (base64) | `python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `STORAGE_ENCRYPTION_KEY` | 文件存储加密 | Fernet (base64) | 同上 |
| `SECRET_KEY` | 用户认证 | hex (64 字符) | `openssl rand -hex 32` |

> `make setup` 会自动生成全部密钥，无需手动操作。

## 数据库选择

Numina 支持三种数据库：

### SQLite（默认）

零配置，适合小规模家庭使用（< 5 个用户）。

```bash
# 默认即为 SQLite，无需额外操作
make setup
make deploy
```

数据文件位于 `.numina/data/db/numina.db`。

### MySQL

适合中大规模部署，需要额外的 MySQL 容器。

```bash
# 1. 启动 MySQL 容器
make setup-db-mysql

# 2. 编辑 .env，修改 DATABASE_URL
#    DATABASE_URL=mysql+pymysql://numina:numinapass@numina-mysql:3306/numina

# 3. 启动服务
make deploy
```

MySQL 容器凭据可通过环境变量覆盖：

```bash
MYSQL_ROOT_PASSWORD=mysecret MYSQL_PASSWORD=mysecret make setup-db-mysql
```

### PostgreSQL

```bash
# 1. 启动 PostgreSQL 容器
make setup-db-postgres

# 2. 编辑 .env，修改 DATABASE_URL
#    DATABASE_URL=postgresql+psycopg://numina:numinapass@numina-postgres:5432/numina

# 3. 启动服务
make deploy
```

## 域名与 HTTPS

### 方案一：Cloudflare 代理 + 源站 Origin 证书（推荐）

1. 将域名 DNS 托管到 Cloudflare
2. 添加 A 记录指向服务器 IP（代理状态：已代理 / Proxied）
3. 在 Cloudflare 控制台生成源站证书（**SSL/TLS -> Origin Server -> Create Certificate**）：
   - 下载证书并保存为 `.numina/data/secrets/origin.crt`
   - 下载私钥并保存为 `.numina/data/secrets/origin.key`
4. SSL/TLS 加密模式设为 **Full (strict)**（源站配置 443 SSL 证书）
5. 编辑 `.env`，更新 `CORS_ORIGINS`：
   ```
   CORS_ORIGINS=["https://numina.example.com"]
   ```

### 方案二：Let's Encrypt

需自行配置 certbot 申请证书，并修改 `nginx.production.conf` 添加 SSL 配置。

## 生产部署

### 首次部署

```bash
# 1. 初始化
make setup

# 2. 编辑 .env（配置域名、数据库等）
# vim .env

# 3. 启动
make deploy

# 4. 生成邀请码（用户注册需要）
make setup-invitation-codes
```

### 验证部署

```bash
# 检查容器状态
make ps

# 检查 API 健康
curl http://localhost/api/health

# 查看日志
make logs
```

### 家庭邀请码

生产环境必须通过邀请码才能注册新用户：

```bash
# 生成 20 个邀请码
make setup-invitation-codes

# 自定义数量
INVITATION_CODE_COUNT=50 make setup-invitation-codes

# 在 backend 容器内手动管理
docker exec -it numina-backend uv run --no-dev python scripts/family_invitation_codes.py list
docker exec -it numina-backend uv run --no-dev python scripts/family_invitation_codes.py revoke --codes CODE1,CODE2
```

### 开发模式部署（含种子数据）

```bash
make deploy-dev
```

该命令会：
- 设置 `ENVIRONMENT=development`（跳过 CAPTCHA）
- 自动初始化演示数据（demouser / DemoPass123 等）
- 启动全部服务

## 更新与回滚

### 常规更新

```bash
git pull origin main
make deploy           # 本地构建模式
# 或
make deploy-images    # 拉取预构建镜像模式
```

### 数据库迁移

迁移在 backend 启动时自动执行。如需手动操作：

```bash
# 查看当前版本
make migrate-current

# 手动执行迁移
make migrate

# 回退一步
make migrate-down

# 生成新迁移
make migrate-revision m="描述"
```

### 回滚

```bash
# 查看历史版本
git log --oneline -10

# 回滚到指定版本
git checkout <commit-hash>
make deploy
```

## 备份与恢复

### 备份

```bash
# 备份数据目录（数据库 + 上传文件）
tar -czvf numina-backup-$(date +%Y%m%d).tar.gz .numina/data/

# 备份配置
tar -czvf numina-config-$(date +%Y%m%d).tar.gz .env nginx.production.conf
```

### 恢复

```bash
# 停止服务
make down

# 恢复数据
tar -xzvf numina-backup-YYYYMMDD.tar.gz -C .

# 重启
make deploy
```

## 常用命令速查

| 操作 | 命令 |
|------|------|
| 初始化 | `make setup` |
| 部署（本地构建） | `make deploy` |
| 部署（拉取镜像） | `make deploy-images` |
| 开发模式部署 | `make deploy-dev` |
| 停止服务 | `make down` |
| 查看状态 | `make ps` |
| 查看日志 | `make logs` |
| 生成邀请码 | `make setup-invitation-codes` |
| 重建单个服务 | `docker compose build backend && docker compose up -d backend` |
| 进入容器 | `make shell` |
| 数据库迁移 | `make migrate` |

## 常见问题

### Q: 注册失败 — FAMILY_INVITATION_CODE_NOT_FOUND

生产环境需要邀请码才能注册。运行 `make setup-invitation-codes` 生成。

### Q: 前端页面重建后 502 Bad Gateway

nginx 缓存了旧的容器 IP。重建前端后需重载 nginx：

```bash
docker compose build frontend-main frontend-child && docker compose up -d frontend-main frontend-child
docker exec numina-nginx nginx -s reload
```

### Q: Backend 启动失败 — 密钥未配置

确保 `.env` 中所有密钥已正确配置。运行 `make setup-env` 自动检查并补全。

### Q: 数据库 schema 错误

```bash
# 方案一：运行迁移（推荐）
make migrate

# 方案二：删除旧数据库重建（仅限测试环境）
make down
rm -f .numina/data/db/numina.db
make deploy
```

### Q: 上传文件无法访问

```bash
chmod -R 755 .numina/data/uploads
docker compose restart backend nginx
```

### Q: 如何切换到 MySQL/PostgreSQL

```bash
# 1. 启动对应数据库容器
NUMINA_DB=mysql make setup-db
# 或
NUMINA_DB=postgres make setup-db

# 2. 编辑 .env 中的 DATABASE_URL
# 3. 重启服务
make deploy
```

---
**最后更新**: 2026-08-02
