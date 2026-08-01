# CI/CD 部署指南

本项目使用 GitHub Actions 自动构建 Docker 镜像并部署到生产服务器。**服务器不执行任何构建**，仅拉取预构建镜像。

## 架构

```
GitHub Push → GitHub Actions → Build Docker Images → Push to GHCR
                                                      ↓
                                              SSH to Server
                                                      ↓
                                              docker compose pull
                                                      ↓
                                              docker compose up -d
                                                      ↓
                                              Restart nginx
```

## 工作原理

1. **代码推送到 main 分支** 时触发 workflow
2. **路径检测**：只构建有变更的服务（frontend/backend）
3. **GitHub Actions 构建镜像** 并推送到 GitHub Container Registry (GHCR)
4. **SSH 连接服务器**，拉取新镜像并重启容器
5. **健康检查**：验证 backend API 和 frontend 可访问

## 配置步骤

### 1. 添加 GitHub Secrets

在 GitHub 仓库的 **Settings → Secrets and variables → Actions** 中添加：

| Secret | 说明 | 示例 |
|--------|------|------|
| `DEPLOY_SSH_KEY` | SSH 私钥（完整内容，包括 `-----BEGIN` 行） | `-----BEGIN OPENSSH PRIVATE KEY-----...` |
| `DEPLOY_HOST` | 服务器 IP 或域名 | `74.120.169.252` |
| `DEPLOY_PORT` | SSH 端口 | `26610` |
| `DEPLOY_USER` | SSH 用户名 | `geek` |
| `DEPLOY_PATH` | 服务器上的仓库路径 | `/home/geek/data/numina` |

> **开源项目注意**：如果仓库是公开的，`DEPLOY_HOST` 等 secrets 只在配置后才会触发部署。Fork 项目的人如果没有配置这些 secrets，deploy job 会自动跳过，不影响他们本地开发。

### 1.5. 配置服务器 `.env`

在**生产服务器**的 `~/data/numina/.env` 中添加镜像地址：

```bash
# 在服务器上执行
echo 'FRONTEND_MAIN_IMAGE=ghcr.io/vincentruan/numina/frontend-main:latest' >> .env
echo 'FRONTEND_CHILD_IMAGE=ghcr.io/vincentruan/numina/frontend-child:latest' >> .env
echo 'BACKEND_IMAGE=ghcr.io/vincentruan/numina/backend:latest' >> .env
```

这样 `docker compose pull` 会从 GHCR 拉取预构建镜像，而不是本地构建。

> **开源用户**：不需要设置这些变量。`docker compose up` 会自动使用 `build:` 从源码构建。

### 2. 生成 SSH 密钥（如果没有）

```bash
# 在本地生成专用部署密钥
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/github_deploy_numina

# 将公钥添加到服务器的 ~/.ssh/authorized_keys
ssh-copy-id -i ~/.ssh/github_deploy_numina.pub -p 26610 geek@74.120.169.252

# 将私钥内容复制到 GitHub Secret (DEPLOY_SSH_KEY)
cat ~/.ssh/github_deploy_numina
```

### 3. 首次部署准备

在服务器上执行一次，拉取基础镜像：

```bash
cd ~/data/numina
docker compose pull  # 拉取所有镜像（包括 GHCR 的）
docker compose up -d
```

## Workflow 文件

- `.github/workflows/deploy.yml` — CI/CD 部署
- `.github/workflows/ci.yml` — 测试（PR 和 push 时运行）

## 触发条件

Deploy workflow 仅在以下条件触发：

- **分支**：`main`
- **路径**：
  - `frontend/**` → 构建 frontend-main + frontend-child
  - `server/**` → 构建 backend

## 手动触发部署

```bash
# 通过 GitHub CLI 手动触发
gh workflow run deploy.yml

# 或通过 GitHub UI
# Actions → Deploy → Run workflow
```

## 回滚

如果部署后发现问题，可以回滚到上一个版本：

```bash
# 在服务器上
cd ~/data/numina

# 查看镜像历史
docker images | grep ghcr.io/vincentruan/numina

# 回退到特定版本（使用 commit SHA）
docker tag ghcr.io/vincentruan/numina/frontend-main:<old-sha> \
           ghcr.io/vincentruan/numina/frontend-main:latest

# 重启服务
docker compose up -d frontend-main
docker restart numina-nginx
```

或通过 git：

```bash
# 回退代码到上一个 commit
git revert HEAD
git push origin main

# 这会触发新的部署，构建上一个版本的镜像
```

## 本地开发 vs 生产部署

### 本地开发

```bash
# 本地构建并运行（使用 build: 指令）
docker compose up -d --build
```

### 生产部署

```bash
# 服务器拉取预构建镜像（使用 image: 指令）
docker compose pull
docker compose up -d
```

`docker-compose.yml` 同时包含 `build:` 和 `image:` 指令：
- 本地：`docker compose build` 使用 `build:` 从源码构建
- 服务器：`docker compose pull` 使用 `image:` 从 GHCR 拉取

## 镜像标签

每个服务有两个标签：

- `:latest` — 始终指向最新版本
- `:<commit-sha>` — 特定版本的快照（用于回滚）

例如：
- `ghcr.io/vincentruan/numina/frontend-main:latest`
- `ghcr.io/vincentruan/numina/frontend-main:abc123def`

## 常见问题

### Q: 如何跳过部署？

在 commit message 中添加 `[skip ci]` 或 `[ci skip]`。

### Q: 部署失败怎么办？

1. 查看 GitHub Actions 日志：`Actions → Deploy → <run> → deploy`
2. 检查服务器日志：`docker compose logs -f`
3. 手动 SSH 到服务器排查

### Q: 如何只部署 frontend 不部署 backend？

路径检测会自动判断。只改 `frontend/**` 的文件，backend 不会构建。

### Q: GHCR 镜像存储有限制吗？

GitHub 免费账户有 2GB 镜像存储限制。可以定期清理旧镜像：

```bash
# 使用 GitHub CLI 删除旧镜像
gh api -X DELETE /user/packages/container/numina/frontend-main/versions/<version-id>
```

或使用 GitHub UI：**Packages → <package> → Manage versions → Delete**

## 性能优化

### BuildKit 缓存

Workflow 使用 GitHub Actions 缓存（`type=gha`）加速构建：
- 首次构建：~5 分钟
- 后续构建（有缓存）：~1-2 分钟

### 并发控制

`concurrency` 配置确保同时只有一个部署在运行，避免冲突。

### 路径过滤

`dorny/paths-filter` 只构建有变更的服务，节省时间。

## 监控

### 查看部署状态

```bash
# GitHub Actions UI
# Actions → Deploy → <run>

# 或 GitHub CLI
gh run list --workflow=deploy.yml
gh run view <run-id> --log
```

### 服务器健康检查

```bash
# 容器状态
docker compose ps

# Backend API
curl http://localhost/api/health

# Frontend
curl -I http://localhost/
```

## 安全建议

1. **使用专用 SSH 密钥**：不要复用个人 SSH 密钥
2. **限制密钥权限**：服务器上配置 `command=` 限制密钥只能执行 docker 命令
3. **定期轮换密钥**：每 6-12 个月更换部署密钥
4. **审计日志**：GitHub Actions 保留所有部署日志

## 扩展：添加更多服务

如果要为 `agent` 或 `scheduler_worker` 添加 CI/CD：

1. 在 `docker-compose.yml` 添加 `image:` 指令
2. 在 `deploy.yml` 添加对应的 build job
3. 在 deploy job 的 `docker compose pull` 中添加服务名

示例：

```yaml
# docker-compose.yml
agent:
  image: ghcr.io/vincentruan/numina/agent:latest
  build: ...

# deploy.yml
build-agent:
  # ... similar to build-backend
```

## 参考

- [GitHub Actions 文档](https://docs.github.com/en/actions)
- [GHCR 文档](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)
- [Docker Compose 文档](https://docs.docker.com/compose/)
- [appleboy/ssh-action](https://github.com/appleboy/ssh-action)
