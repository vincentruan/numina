# Numina 配置参考

## 文件存储架构

Numina 将持久化数据分为两类独立管理：

### 1. 数据库文件

| 路径 | 说明 |
|------|------|
| `data/numina.db` | SQLite 数据库（默认） |

数据库路径通过 `DATABASE_URL` 环境变量配置。需要持久化，但通常不纳入 Git 版本控制（包含敏感财务数据）。

### 2. 家庭工作空间（Workspace）

每个家庭拥有独立的工作空间目录，按 `family_id` 隔离：

```
data/workspace/
└── {family_id}/
    ├── images/     # 资产图片上传
    ├── skills/     # 技能自定义 prompt（覆盖 agent/skills/*.md）
    ├── prompts/    # 其他自定义 prompt MD 文件
    └── exports/    # 导出文件（报表、备份等）
```

工作空间路径通过 `WORKSPACE_ROOT` 环境变量配置（默认 `./data/workspace`）。

**技能 prompt 覆盖规则：** 后端读取技能 prompt 时，优先检查 `workspace/{family_id}/skills/{capability}.md`，不存在则回退到 `agent/skills/{capability}.md`。

### Docker 卷挂载

`docker-compose.yml` 中 `./data:/app/data` 单一挂载覆盖数据库和工作空间：

```yaml
volumes:
  - ./data:/app/data   # 包含 numina.db、uploads/、workspace/、chat/
```

如需将工作空间挂载到自定义路径：

```yaml
environment:
  - WORKSPACE_ROOT=/mnt/nas/numina-workspace
volumes:
  - /mnt/nas/numina-workspace:/mnt/nas/numina-workspace
```

### Git 备份

工作空间目录可整体纳入 Git 版本控制（不含数据库和上传图片）：

```bash
# 初始化工作空间 Git 仓库
cd data/workspace
git init
echo "*/images/" >> .gitignore   # 图片体积大，按需备份
git add .
git commit -m "init workspace"

# 定期备份
git add -A && git commit -m "backup $(date +%Y-%m-%d)"
```

数据库单独备份：

```bash
cp data/numina.db backups/numina-$(date +%Y%m%d).db
```

---

## 环境变量参考

### 后端（backend）

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `SECRET_KEY` | 自动生成 | **生产必填。** JWT 签名密钥。 |
| `DATABASE_URL` | `sqlite:///./data/numina.db` | 数据库连接字符串。支持 SQLite / MySQL / PostgreSQL。 |
| `WORKSPACE_ROOT` | `./data/workspace` | 家庭工作空间根目录，按 `{family_id}` 子目录隔离。 |
| `UPLOAD_DIR` | `./data/uploads` | 资产图片上传目录（静态文件服务根）。 |
| `CHAT_DIR` | `./data/chat` | 对话历史 JSONL 存储目录。不能位于 `UPLOAD_DIR` 下。 |
| `ENVIRONMENT` | `development` | 设为 `production` 启用生产校验。 |
| `CORS_ORIGINS` | `["http://localhost:5173", "http://localhost:8080"]` | 允许的 CORS 来源。生产环境必须配置具体域名。 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `15` | JWT access token 有效期（分钟）。 |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | JWT refresh token 有效期（天）。 |
| `ALTCHA_HMAC_KEY` | 自动生成 | **生产必填。** 验证码 HMAC 密钥。 |
| `AI_ENCRYPTION_KEY` | `""` | **生产必填。** Fernet 密钥，用于加密 AI API Key。生成：`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `STORAGE_ENCRYPTION_KEY` | `""` | **生产推荐。** 存储后端凭证加密密钥（独立于 `SECRET_KEY`）。 |
| `AGENT_INTERNAL_TOKEN` | `""` | backend ↔ agent 服务间调用令牌。生产必填。 |
| `AGENT_BASE_URL` | `http://agent:8001` | Agent 服务内部地址。 |
| `SNOWFLAKE_MACHINE_ID` | 自动推导 | Snowflake ID 机器编号（0–1023）。多实例部署时显式设置。 |
| `LOGIN_RATE_LIMIT_MAX_ATTEMPTS` | `5` | 登录失败锁定阈值。 |
| `LOGIN_RATE_LIMIT_LOCKOUT_SECONDS` | `900` | 锁定时长（秒，默认 15 分钟）。 |

### 最小生产 `.env` 示例

```env
ENVIRONMENT=production
SECRET_KEY=<openssl rand -base64 32>
ALTCHA_HMAC_KEY=<openssl rand -base64 32>
AI_ENCRYPTION_KEY=<Fernet.generate_key()>
STORAGE_ENCRYPTION_KEY=<Fernet.generate_key()>
AGENT_INTERNAL_TOKEN=<openssl rand -base64 32>
DATABASE_URL=sqlite:////app/data/numina.db
WORKSPACE_ROOT=/app/data/workspace
CORS_ORIGINS=["https://numina.yourdomain.com"]
```
