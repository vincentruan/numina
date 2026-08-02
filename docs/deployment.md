# CI/CD 部署指南

本项目使用 GitHub Actions 自动构建 Docker 镜像并推送到 GHCR。**服务器不执行任何构建**，仅拉取预构建镜像。

> **GitHub 不需要任何部署密钥 (SSH Key)** — 只需要 `GITHUB_TOKEN`（GitHub Actions 自带）。

## 架构

```
GitHub Push → GitHub Actions → Test (CI)
                                    ↓ (main branch only)
                              Build Docker Images
                                    ↓
                              Push to GHCR
                                    ↓
                        服务器: make deploy-images
                              (docker compose pull + up)
```

## 工作原理

1. **代码推送到 main 分支** 时触发 CI workflow
2. **CI 运行测试**：backend pytest、frontend typecheck + vitest、E2E smoke
3. **测试通过后构建镜像** 并推送到 GitHub Container Registry (GHCR)
4. **服务器手动拉取**：`git pull && make deploy-images`

## 两种部署模式

| 模式 | 命令 | 适用场景 |
|------|------|----------|
| **本地构建** | `make deploy` | 开源用户、Fork、低版本服务器 |
| **拉取镜像** | `make deploy-images` | 使用预构建镜像，无需在服务器编译 |

### 模式一：本地构建（开源默认）

```bash
git pull origin main
make deploy
```

`docker-compose.yml` 中 `image:` 为空时，自动使用 `build:` 从源码构建。

### 模式二：拉取预构建镜像

```bash
git pull origin main
make deploy-images
```

首次运行会自动将 GHCR 默认地址写入 `.env`：

```bash
BACKEND_IMAGE=ghcr.io/vincentruan/numina/backend:latest
AGENT_IMAGE=ghcr.io/vincentruan/numina/agent:latest
SCHEDULER_WORKER_IMAGE=ghcr.io/vincentruan/numina/scheduler-worker:latest
FRONTEND_MAIN_IMAGE=ghcr.io/vincentruan/numina/frontend-main:latest
FRONTEND_CHILD_IMAGE=ghcr.io/vincentruan/numina/frontend-child:latest
```

如需使用自定义镜像仓库（例如 Fork 后推送到自己的 GHCR），编辑 `.env` 中的 `*_IMAGE` 变量即可。

## 环境变量配置

无论哪种部署模式，都需要正确配置 `.env`。

### 初始化

```bash
make setup    # 自动生成 .env（含随机密钥）
```

`make setup` 会自动生成以下密钥：
- `SECRET_KEY` — JWT 签名
- `ALTCHA_HMAC_KEY` — 验证码
- `AI_ENCRYPTION_KEY` — AI API Key 加密
- `STORAGE_ENCRYPTION_KEY` — 存储后端加密

### 必须配置的变量

| 变量 | 说明 | 生成方式 |
|------|------|----------|
| `SECRET_KEY` | JWT 签名密钥 | `openssl rand -hex 32` |
| `ALTCHA_HMAC_KEY` | 验证码密钥 | `openssl rand -hex 32` |
| `AI_ENCRYPTION_KEY` | AI Key 加密（Fernet） | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `STORAGE_ENCRYPTION_KEY` | 存储加密（Fernet） | 同上 |

> 以上密钥由 `make setup` 自动生成，无需手动配置。

### 按需配置的变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DATABASE_URL` | `sqlite:////app/.numina/data/db/numina.db` | 数据库路径 |
| `DATA_ROOT` | `/app/.numina/data` | 数据存储根目录 |
| `CORS_ORIGINS` | `["http://localhost:80"]` | CORS 允许的域名 |
| `AI_MODEL` | `placeholder` | AI 模型 ID |
| `AI_API_KEY` | `placeholder` | AI API 密钥 |

完整变量列表参见 [configuration.md](./configuration.md)。

### 两种模式的变量注入方式

| 场景 | 镜像构建时 | 容器运行时 |
|------|-----------|-----------|
| `make deploy`（本地构建） | 无特殊变量 | 从 `.env` 注入所有配置 |
| `make deploy-images`（拉取镜像） | 无特殊变量 | 从 `.env` 注入所有配置 |

**关键**：所有密钥和配置都是**运行时注入**，不烘焙进镜像。预构建镜像与本地构建使用完全相同的 `.env`。

## 镜像标签

每个服务有两个标签：

- `:latest` — 始终指向最新版本
- `:<commit-sha>` — 特定版本的快照（用于回滚）

## 回滚

```bash
# 回退到特定 commit 的镜像
docker tag ghcr.io/vincentruan/numina/backend:<old-sha> \
           ghcr.io/vincentruan/numina/backend:latest
docker compose up -d --no-deps backend

# 或通过 git 回退代码 + 本地构建
git checkout <commit-hash>
make deploy
```

## CI 镜像构建条件

- **分支**：仅 `main`
- **前置**：所有测试通过（backend + frontend + E2E smoke）
- **矩阵构建**：backend、agent、scheduler-worker、frontend-main、frontend-child 并行构建
- **缓存**：使用 GitHub Actions 缓存 (`type=gha`) 加速

## Workflow 文件

- `.github/workflows/ci.yml` — 测试 + 镜像构建（push to main 时）

## 常见问题

### Q: 开源 Fork 用户需要配置什么？

什么都不用。直接 `make deploy` 即可本地构建。CI 中的 `build-images` job 仅在有写入 GHCR 权限时才会推送。

### Q: 如何手动触发镜像构建？

```bash
# 通过 GitHub CLI
gh workflow run ci.yml --ref main

# 或推送一个空 commit
git commit --allow-empty -m "ci: trigger image build" && git push
```

### Q: GHCR 镜像存储有限制吗？

GitHub 免费账户有 2GB 镜像存储限制。可以定期清理旧镜像：

**GitHub UI**：Settings → Packages → 选择包 → Manage versions → Delete

### Q: 如何自定义镜像仓库地址？

编辑 `.env` 中的 `*_IMAGE` 变量：

```bash
BACKEND_IMAGE=ghcr.io/my-org/my-numina/backend:latest
AGENT_IMAGE=ghcr.io/my-org/my-numina/agent:latest
SCHEDULER_WORKER_IMAGE=ghcr.io/my-org/my-numina/scheduler-worker:latest
FRONTEND_MAIN_IMAGE=ghcr.io/my-org/my-numina/frontend-main:latest
FRONTEND_CHILD_IMAGE=ghcr.io/my-org/my-numina/frontend-child:latest
```

然后运行 `make deploy-images`。

### Q: 服务器健康检查

```bash
# 容器状态
make ps

# Backend API
curl http://localhost/api/health

# Frontend
curl -I http://localhost/
```

---
**最后更新**: 2026-08-02
