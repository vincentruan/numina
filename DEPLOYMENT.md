# Numina 部署指南

本文档记录 Numina 家庭资产管理系统的生产环境部署流程。

## 目录

- [前置条件](#前置条件)
- [服务器准备](#服务器准备)
- [域名与 HTTPS 配置](#域名与-https-配置)
- [部署步骤](#部署步骤)
- [更新部署](#更新部署)
- [常见问题](#常见问题)

## 前置条件

### 服务器要求

- **操作系统**: Linux (CentOS 7+ / Ubuntu 18.04+)
- **内存**: 最低 1GB，推荐 2GB+
- **磁盘**: 最低 10GB 可用空间
- **网络**: 公网 IP，开放 80/443 端口

### 软件要求

- Docker 20.10+
- Docker Compose v2+
- Git

### 域名要求

- 已备案域名（国内服务器）
- 域名 DNS 已解析到服务器 IP
- 推荐使用 Cloudflare 代理获得免费 HTTPS

## 服务器准备

### 1. 安装 Docker

```bash
# CentOS 7
yum install -y yum-utils
yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
yum install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
systemctl enable --now docker

# 将当前用户加入 docker 组（免 sudo）
usermod -aG docker $USER
# 重新登录生效
```

### 2. 创建部署目录

```bash
mkdir -p ~/data/numina
cd ~/data/numina
```

### 3. 克隆代码仓库

```bash
git clone https://github.com/YOUR_USERNAME/numina.git .
```

## 域名与 HTTPS 配置

### 方案一：Cloudflare 代理（推荐）

1. 将域名 DNS 托管到 Cloudflare
2. 添加 A 记录指向服务器 IP
   - 类型: A
   - 名称: numina（或 @ 使用根域名）
   - 内容: 服务器 IP
   - 代理状态: 已代理（橙色云朵）
3. SSL/TLS 设置
   - 加密模式: **Flexible**（源服务器 HTTP，Cloudflare 提供 HTTPS）
4. 安全设置（可选）
   - 开启 "Always Use HTTPS"
   - 开启 "Auto Minify"
   - 开启 "Brotli"

### 方案二：Let's Encrypt 证书

如果服务器有公网域名且未使用 Cloudflare：

```bash
# 安装 certbot
yum install -y certbot

# 申请证书
certbot certonly --standalone -d numina.example.com

# 证书续期（cron）
echo "0 3 * * * certbot renew --quiet" | crontab -
```

## 本地开发部署

快速在本地启动完整服务栈（用于开发和测试）。

### 前置条件

- Docker Desktop（macOS/Windows）或 Docker Engine（Linux）
- `jq`（用于测试脚本）：`brew install jq`

### 启动服务

```bash
# 复制本地环境配置（已包含开发用默认值）
cp .env.local .env   # 或直接使用已有的 .env

# 构建并启动所有服务
docker-compose up -d --build

# 查看服务状态
docker ps --format "{{.Names}}\t{{.Status}}" | grep numina
```

服务启动后访问：
- 成人端：http://localhost/
- 儿童端：http://localhost/child/
- API 健康检查：http://localhost/api/health

### 初始化测试数据

```bash
# 创建所有测试账号（幂等，可重复执行）
./tests/data/seed-data.sh

# 测试账号说明：
# demouser / DemoPass123     — 完整演示数据（含儿童：小宝/大宝）
# test_rich / TestRich123!   — 完整回归数据（含儿童：testchild）
# test_empty / TestEmpty123! — 空家庭
```

### 运行验收测试

```bash
./tests/e2e/acceptance.sh
```

### 重建单个服务

```bash
# 重建 agent（依赖变更后需要）
docker-compose build agent && docker-compose up -d agent

# 重建前端
docker-compose build frontend frontend-child && docker-compose up -d frontend frontend-child
```

### Agent 依赖管理

Agent 使用 `uv` 管理依赖，`requirements.txt` 由 `uv.lock` 导出，确保 Docker 构建使用锁定版本：

```bash
# 更新依赖后重新生成 requirements.txt
cd agent && uv lock && uv export --no-dev --no-hashes -o requirements.txt
```

## 部署步骤

### 1. 配置环境变量

```bash
cd ~/data/numina

# 生成安全密钥
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# 生成所有必要密钥
SECRET_KEY=$(openssl rand -hex 32)
ALTCHA_HMAC_KEY=$(openssl rand -hex 32)
AI_ENCRYPTION_KEY=$(openssl rand -hex 32)
AGENT_INTERNAL_TOKEN=$(openssl rand -hex 32)
# Fernet key (base64url of 32 random bytes)
STORAGE_ENCRYPTION_KEY=$(python3 -c "import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())")

# 创建环境配置
cat > .env.production << EOF
# Numina Production Environment Configuration
SECRET_KEY=${SECRET_KEY}
ENVIRONMENT=production

# CORS - 配置你的域名
CORS_ORIGINS=["https://numina.example.com"]

# Database
DATABASE_URL=sqlite:////app/data/numina.db

# Token expiration
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# CAPTCHA (必须配置，否则生产环境无法启动)
ALTCHA_HMAC_KEY=${ALTCHA_HMAC_KEY}

# Agent / AI 加密 (必须配置)
AI_ENCRYPTION_KEY=${AI_ENCRYPTION_KEY}
AGENT_INTERNAL_TOKEN=${AGENT_INTERNAL_TOKEN}
STORAGE_ENCRYPTION_KEY=${STORAGE_ENCRYPTION_KEY}
EOF
```

### 2. 创建数据目录

```bash
mkdir -p data/uploads
```

### 3. 启动服务

```bash
docker compose -f docker-compose.production.yml up -d --build
```

### 4. 生成家庭邀请码（首次部署）

生产环境需要家庭邀请码才能注册新用户：

```bash
# 生成 20 个邀请码
docker exec numina-backend uv run --no-dev python scripts/family_invitation_codes.py generate --count 20

# 查看已生成的邀请码
docker exec numina-backend uv run --no-dev python scripts/family_invitation_codes.py list
```

### 5. 初始化测试数据（可选）

如需初始化演示数据（demouser 账号 + 完整资产数据）：

```bash
# 临时切换到 development 模式（跳过 CAPTCHA 验证）
sed -i.bak 's/^ENVIRONMENT=production/ENVIRONMENT=development/' .env.production
docker compose -f docker-compose.production.yml up -d backend

# 等待服务启动
sleep 10

# 生成足够的邀请码（需要约 10 个）
docker exec numina-backend uv run --no-dev python scripts/family_invitation_codes.py generate --count 15

# 运行种子数据脚本
FAMILY_INVITATION_CODES=$(docker exec numina-backend uv run --no-dev python scripts/family_invitation_codes.py list --format csv | head -15 | tr '\n' ',')
BASE_URL=http://localhost/api/v1 bash tests/data/seed-data.sh

# 恢复生产模式
sed -i 's/^ENVIRONMENT=development/ENVIRONMENT=production/' .env.production
docker compose -f docker-compose.production.yml up -d backend
```

**测试账号：**
- `demouser` / `DemoPass123` — 完整演示数据（19 实物资产 + 11 金融资产 + 负债 + 心愿 + 儿童）
- `test_empty` / `TestEmpty123!` — 空家庭
- `test_asset` / `TestAsset123!` — 5 个资产（多状态测试）
- `test_rich` / `TestRich123!` — 完整数据（31 资产 + 28 负债 + 29 心愿）

### 6. 验证部署

```bash
# 检查容器状态
docker ps

# 检查健康状态
curl http://localhost/api/health

# 查看日志
docker logs numina-backend --tail 50
docker logs numina-nginx --tail 50
```

### 5. 外部访问验证

```bash
# 通过域名访问（Cloudflare HTTPS）
curl https://numina.example.com/api/health

# 浏览器访问
# https://numina.example.com/
```

## 更新部署

### 常规更新流程

```bash
cd ~/data/numina

# 1. 拉取最新代码
git pull origin main

# 2. 重新构建并启动
docker compose -f docker-compose.production.yml up -d --build

# 3. 验证更新
curl https://numina.example.com/api/health
```

### 数据库迁移

如果更新涉及数据库结构变更：

```bash
# 进入 backend 容器
docker exec -it numina-backend bash

# 执行迁移
alembic upgrade head

# 退出容器
exit
```

### 回滚操作

```bash
# 查看历史版本
git log --oneline -10

# 回滚到指定版本
git checkout <commit-hash>

# 重新部署
docker compose -f docker-compose.production.yml up -d --build
```

## 文件结构

部署后的目录结构：

```
~/data/numina/
├── backend/                 # 后端代码
├── agent/                   # AI Agent 微服务
├── frontend/                # 前端 monorepo
│   ├── apps/
│   │   ├── main/            # 成人端 SPA（原 frontend/）
│   │   └── child/           # 儿童端 SPA（原 frontend-child/）
│   └── packages/
│       └── auth/            # 共享认证包
├── data/                    # 数据目录（持久化）
│   ├── numina.db           # SQLite 数据库
│   └── uploads/            # 上传文件
├── nginx.production.conf    # Nginx 配置
├── docker-compose.production.yml
└── .env.production          # 环境变量（不提交到 git）
```

## 安全加固清单

- [x] SECRET_KEY 使用强随机密钥
- [x] ENVIRONMENT 设置为 production
- [x] CORS_ORIGINS 限制为生产域名
- [x] Nginx 安全 Headers（X-Frame-Options, X-Content-Type-Options 等）
- [x] 隐藏 Nginx 版本号（server_tokens off）
- [x] 后端服务不直接暴露端口
- [x] 敏感文件访问阻断（.env, .git 等）
- [x] HTTPS 加密（Cloudflare / Let's Encrypt）

## 常见问题

### Q: 521 Web Server Is Down

**原因**: Cloudflare 无法连接到源服务器

**解决**:
1. 确认 Docker 容器正常运行
2. 确认服务器防火墙开放 80 端口
3. 检查 Cloudflare SSL 模式是否为 Flexible

### Q: 前端页面空白

**原因**: Vue 路由配置问题或 API 请求失败

**解决**:
1. 检查浏览器控制台错误
2. 确认 API 健康检查正常
3. 检查 CORS 配置是否包含当前域名

### Q: 数据库文件丢失

**原因**: Docker 卷未正确挂载

**解决**:
1. 确认 `./data` 目录存在
2. 检查 docker-compose.production.yml 中的 volumes 配置
3. 定期备份数据目录

### Q: Backend 启动失败 — ALTCHA_HMAC_KEY 未配置

**原因**: 生产环境缺少必要的环境变量

**解决**:
```bash
# 生成缺失的密钥
ALTCHA_HMAC_KEY=$(openssl rand -hex 32)
AI_ENCRYPTION_KEY=$(openssl rand -hex 32)
AGENT_INTERNAL_TOKEN=$(openssl rand -hex 32)
STORAGE_ENCRYPTION_KEY=$(python3 -c "import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())")

# 添加到 .env.production
cat >> .env.production << EOF
ALTCHA_HMAC_KEY=${ALTCHA_HMAC_KEY}
AI_ENCRYPTION_KEY=${AI_ENCRYPTION_KEY}
AGENT_INTERNAL_TOKEN=${AGENT_INTERNAL_TOKEN}
STORAGE_ENCRYPTION_KEY=${STORAGE_ENCRYPTION_KEY}
EOF

# 重新创建容器（restart 不会重新加载 env 文件）
docker compose -f docker-compose.production.yml up -d backend
```

### Q: 数据库 schema 错误 — no such column

**原因**: 数据库是旧版本创建的，缺少新增的列

**解决**:
```bash
# 方案一：删除旧数据库，重新创建（仅适用于测试环境）
docker compose -f docker-compose.production.yml stop backend
rm -f data/numina.db
docker compose -f docker-compose.production.yml up -d backend

# 方案二：运行 Alembic 迁移（生产环境推荐）
# 注意：当前项目 Alembic 迁移尚未完整覆盖所有 schema 变更
# 建议在生产环境首次部署时使用全新数据库
```

### Q: 注册失败 — FAMILY_INVITATION_CODE_NOT_FOUND

**原因**: 生产环境需要家庭邀请码才能注册

**解决**:
```bash
# 生成邀请码
docker exec numina-backend uv run --no-dev python scripts/family_invitation_codes.py generate --count 10

# 查看可用邀请码
docker exec numina-backend uv run --no-dev python scripts/family_invitation_codes.py list
```

### Q: 上传文件无法访问

**原因**: uploads 目录权限问题

**解决**:
```bash
chmod -R 755 ~/data/numina/data/uploads
docker restart numina-backend numina-nginx
```

## 备份与恢复

### 备份

```bash
# 备份数据目录
tar -czvf numina-backup-$(date +%Y%m%d).tar.gz ~/data/numina/data/

# 备份配置文件
tar -czvf numina-config-$(date +%Y%m%d).tar.gz \
  ~/data/numina/.env.production \
  ~/data/numina/nginx.production.conf
```

### 恢复

```bash
# 停止服务
docker compose -f docker-compose.production.yml down

# 恢复数据
tar -xzvf numina-backup-YYYYMMDD.tar.gz -C /

# 重启服务
docker compose -f docker-compose.production.yml up -d
```

## 监控与日志

### 查看日志

```bash
# 实时日志
docker logs -f numina-backend

# 最近 100 行日志
docker logs numina-backend --tail 100

# 所有容器状态
docker compose -f docker-compose.production.yml ps
```

### 日志轮转

Docker 默认会管理日志轮转，如需自定义：

```json
// /etc/docker/daemon.json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

---

### Q: Agent 容器启动失败 — ImportError: cannot import name 'ExecutionInfo'

**原因**: `langgraph-prebuilt` 版本与 `langgraph` 核心版本不兼容。`langgraph<1.1.0` 的 `runtime` 模块不含 `ExecutionInfo` 符号，但 `langgraph-prebuilt>=1.0.9` 依赖它。

**解决**:
```bash
cd agent
# 放宽 deerflow-harness 中的 langgraph 版本约束（已修复）
# 重新生成锁定的 requirements.txt
uv lock && uv export --no-dev --no-hashes -o requirements.txt
# 重建 agent 镜像
docker-compose build agent && docker-compose up -d agent
```

### Q: seed-data.sh 失败 — jq: error: Cannot iterate over null

**原因**: 脚本中 `$BASE_URL/family/` 带尾斜杠，nginx 返回 307 重定向，curl 跟随后 FastAPI 返回 404，导致 jq 解析 null。

**解决**: 已修复脚本，将 `family/` 改为 `family`（无尾斜杠）。如遇类似问题，检查 API 调用是否有多余的尾斜杠。

---

**文档版本**: 1.1
**最后更新**: 2026-04-29
**维护者**: Numina Team