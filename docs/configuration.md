# Numina 配置参考

## 存储架构

所有持久化数据统一存放在 `DATA_ROOT` 目录下（Docker 中默认 `/app/.numina/data`）：

```
{DATA_ROOT}/
├── db/                        # SQLite 数据库
│   └── numina.db
├── workspaces/
│   ├── builtin/               # 内置 skills/agents/mcp
│   └── tenants/{family_id}/   # 每个家庭的隔离数据
│       ├── uploads/{user_id}/ # 资产图片
│       ├── skills/            # 家庭自定义 skill
│       ├── agents/            # 家庭自定义 agent
│       ├── mcp/               # 家庭自定义 MCP
│       ├── reports/           # AI 生成的报告
│       ├── chat/              # 对话历史
│       └── tmp/               # 临时文件
├── runtime/effective/         # 运行时合并配置（可删除重建）
├── logs/                      # 日志
└── backups/                   # 备份
```

### Docker 卷挂载

```yaml
volumes:
  - ./.numina/data:/app/.numina/data   # 统一挂载，包含所有数据
```

如需自定义存储路径，修改 `DATA_ROOT` 并调整挂载：

```yaml
environment:
  - DATA_ROOT=/mnt/nas/numina
volumes:
  - /mnt/nas/numina:/mnt/nas/numina
```

---

## 环境变量完整参考

### 🔴 必须配置（生产环境）

以下变量在生产环境（`ENVIRONMENT=production`）**必须设置**，否则启动失败：

| 变量 | 说明 | 生成方式 |
|------|------|----------|
| `SECRET_KEY` | JWT 签名密钥，不能为空或默认值 | `openssl rand -hex 32` |
| `ALTCHA_HMAC_KEY` | 验证码 HMAC 密钥 | `openssl rand -hex 32` |
| `AI_ENCRYPTION_KEY` | Fernet 密钥，加密 AI API Key | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `STORAGE_ENCRYPTION_KEY` | Fernet 密钥，加密存储后端凭证 | 同上（独立于 AI_ENCRYPTION_KEY） |

> `make setup` 会自动生成以上所有密钥。

### 🟡 常用配置（有默认值，按需修改）

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `ENVIRONMENT` | `production` (compose) / `development` (backend) | 环境模式：`production` 或 `development` |
| `DATABASE_URL` | `sqlite:////app/.numina/data/db/numina.db` | 数据库连接串。支持 SQLite / MySQL / PostgreSQL |
| `DATA_ROOT` | `/app/.numina/data` (compose) / `~/.numina/data` (本地) | 所有持久化数据的根目录 |
| `CORS_ORIGINS` | `["http://localhost:28080","http://localhost:80"]` | 允许的 CORS 来源（JSON 数组）。生产环境**必须配置具体域名** |
| `LOG_LEVEL` | `INFO` | 日志级别：DEBUG / INFO / WARNING / ERROR |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | JWT access token 有效期（分钟） |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | JWT refresh token 有效期（天） |
| `INIT_INVITATION_CODES` | `""` | 初始化邀请码（逗号分隔），首次部署后可用 `make setup-invitation-codes` 生成 |
| `SNOWFLAKE_MACHINE_ID` | 自动推导 | Snowflake ID 机器编号（0–1023），多实例部署时显式设置 |

### 🔵 AI Agent 配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `AI_MODEL` | `placeholder` | LLM 模型 ID |
| `AI_API_KEY` | `placeholder` | LLM API 密钥 |
| `AGENT_BASE_URL` | `http://numina-agent:8001` | Agent 服务内部地址（docker-compose 内部通信用） |
| `BACKEND_BASE_URL` | `http://numina-backend:8000` | Backend 内部地址 |

### 🟢 文件同步与存储后端

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `FILE_SYNC_INTERVAL_MINUTES` | `30` | 文件同步间隔（分钟） |
| `STORAGE_BACKEND_TYPE` | `""` | 远程存储后端：`github` / `webdav` / 空（不使用） |
| `STORAGE_BACKEND_NAME` | `""` | 存储后端显示名称 |

**GitHub 存储后端**（`STORAGE_BACKEND_TYPE=github` 时需要）：

| 变量 | 说明 |
|------|------|
| `STORAGE_GITHUB_REPO_OWNER` | 仓库所有者 |
| `STORAGE_GITHUB_REPO_NAME` | 仓库名 |
| `STORAGE_GITHUB_BRANCH` | 分支名（默认 `main`） |
| `STORAGE_GITHUB_TOKEN` | Personal Access Token（需要 `repo` 权限） |

**WebDAV 存储后端**（`STORAGE_BACKEND_TYPE=webdav` 时需要）：

| 变量 | 说明 |
|------|------|
| `STORAGE_WEBDAV_BASE_URL` | WebDAV 服务器地址 |
| `STORAGE_WEBDAV_USERNAME` | 用户名 |
| `STORAGE_WEBDAV_PASSWORD` | 密码 |

### ⚙️ 安全配置（高级）

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `BCRYPT_ROUNDS` | `12` | 密码哈希迭代次数 |
| `PIN_BCRYPT_ROUNDS` | `8` | 儿童 PIN 哈希迭代次数 |
| `LOGIN_RATE_LIMIT_MAX_ATTEMPTS` | `5` | 登录失败锁定阈值 |
| `LOGIN_RATE_LIMIT_LOCKOUT_SECONDS` | `900` | 锁定时长（秒，默认 15 分钟） |
| `GLOBAL_RATE_LIMIT_PER_MINUTE` | `100` | 全局速率限制（次/分钟） |
| `REGISTER_RATE_LIMIT_PER_HOUR` | `5` | 注册速率限制（次/小时/IP） |
| `DISABLE_CAPTCHA` | `false` | 禁用验证码（仅建议开发环境） |
| `TRUSTED_PROXY_IPS` | `[]` | 可信代理 IP 列表（JSON 数组），用于 X-Forwarded-For 校验 |
| `WEBAUTHN_RP_ID` | `localhost` | WebAuthn 域名（不含协议和端口） |
| `WEBAUTHN_ORIGIN` | `http://localhost:8080` | WebAuthn 完整 origin |
| `DEVICE_TRUST_EXPIRE_DAYS` | `30` | 设备信任有效期（天） |

### 📊 日志配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `LOG_MAX_BYTES` | `10485760` (10MB) | 单个日志文件最大大小 |
| `LOG_BACKUP_COUNT` | `10` | 保留的日志文件数量 |
| `LOG_RETENTION_DAYS` | `30` | 日志保留天数 |
| `LOG_ROTATION_MODE` | `size` | 日志轮转模式：`size` 或 `time` |

### 🗄️ 数据库相关（MySQL/PostgreSQL）

使用 MySQL 或 PostgreSQL 时，取消 `.env` 中的注释：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `MYSQL_ROOT_PASSWORD` | `rootpass` | MySQL root 密码 |
| `MYSQL_DATABASE` | `numina` | MySQL 数据库名 |
| `MYSQL_USER` | `numina` | MySQL 用户名 |
| `MYSQL_PASSWORD` | `numinapass` | MySQL 用户密码 |
| `POSTGRES_DB` | `numina` | PostgreSQL 数据库名 |
| `POSTGRES_USER` | `numina` | PostgreSQL 用户名 |
| `POSTGRES_PASSWORD` | `numinapass` | PostgreSQL 用户密码 |

---

## 最小生产 `.env` 示例

```env
# 环境模式
ENVIRONMENT=production

# 安全密钥（make setup 自动生成）
SECRET_KEY=<openssl rand -hex 32>
ALTCHA_HMAC_KEY=<openssl rand -hex 32>
AI_ENCRYPTION_KEY=<Fernet.generate_key()>
STORAGE_ENCRYPTION_KEY=<Fernet.generate_key()>

# 数据库（默认 SQLite，无需修改）
DATABASE_URL=sqlite:////app/.numina/data/db/numina.db

# CORS 域名（必须配置实际访问域名）
CORS_ORIGINS=["https://numina.yourdomain.com"]

# AI 配置（如需 AI 功能）
AI_MODEL=your-model-id
AI_API_KEY=your-api-key
```

## Git 备份

工作空间目录可整体纳入 Git 版本控制：

```bash
cd ./.numina/data/workspaces
git init
echo "*/uploads/" >> .gitignore   # 图片体积大，按需备份
git add .
git commit -m "init workspace"
```

数据库单独备份：

```bash
cp ./.numina/data/db/numina.db ./backups/numina-$(date +%Y%m%d).db
```

---
**最后更新**: 2026-08-02
