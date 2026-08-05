# 家庭维度远程备份配置 - 实施完成

## 概述

已将远程备份从全局环境变量配置改为按家庭维度的 UI 配置。

## 主要变更

### 1. 数据模型 (Migration: f5g6h7i8j9k0)
- ✅ `StorageBackend` 表添加 `family_id` (BigInteger, FK → families.id, UNIQUE)
- ✅ 删除 `is_default` 列（语义已变：每个家庭最多一个后端，无需默认标识）
- ✅ 清理旧的全局后端记录

### 2. 环境变量清理
- ❌ 删除以下环境变量：
  - `STORAGE_BACKEND_TYPE`
  - `STORAGE_BACKEND_NAME`
  - `STORAGE_BACKEND_IS_DEFAULT`
  - `STORAGE_BACKEND_IS_ACTIVE`
  - `STORAGE_GITHUB_*` (所有 GitHub 配置)
  - `STORAGE_WEBDAV_*` (所有 WebDAV 配置)
- ⚠️ 启动时如检测到旧环境变量，将拒绝启动并提示用户迁移

### 3. 后端 API (新增路由)
**路由前缀**: `/api/v1/family/storage`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/status` | 获取当前家庭的后端状态（轻量级） |
| GET | `/` | 获取后端完整信息 |
| POST | `/` | 创建后端（owner only） |
| PATCH | `/{id}` | 更新后端配置（owner only） |
| DELETE | `/{id}` | 删除后端（owner only） |

### 4. 文件同步逻辑更新
- ✅ `StorageService.upload_file`: 按 `family_id` 查询后端
- ✅ `files.py:get_file_url`: 按 `family_id` 查询后端
- ✅ `scheduler_worker/file_sync_job`: 遍历所有 active 后端（而非单个全局默认）

### 5. 前端实现
- ✅ 新增 `FamilyStorageBackendPage.vue` - 配置表单页面
- ✅ 路由 `/settings/family/storage` (仅 owner 可见)
- ✅ API 客户端 `storageBackend.ts`
- ✅ i18n 支持 (zh-CN + en-US)

### 6. 测试更新
- ✅ 模型测试 (`test_file_storage_models.py`)
- ✅ 文件同步测试 (`test_file_sync.py`)
- ✅ 上传测试 (`test_upload.py`)
- ✅ 调度器测试 (`test_jobs_behavior.py`)
- ✅ 删除过时的种子数据测试 (`test_seed_storage_backends.py`)

**测试结果**:
- Backend: 1472 passed, 2 skipped
- Scheduler: 37 passed
- Frontend: typecheck passes, lint passes

## 迁移指南

### 对于已有用户
如果之前配置了全局远程备份（通过环境变量），需要：

1. 删除环境变量（所有 `STORAGE_BACKEND_*`）
2. 启动应用（会拒绝启动直到环境变量被删除）
3. 进入 设置 → 家庭管理 → 家庭远程备份
4. 重新配置 GitHub 或 WebDAV 后端

### 对于新部署
- 无需配置任何环境变量
- 用户可在设置中自行配置远程备份

## 技术亮点

1. **权限控制**: 仅家庭 owner 可配置远程备份
2. **加密存储**: 继续使用 Fernet 加密凭证
3. **向后兼容**: 旧数据自动清理，不影响现有文件引用
4. **多后端支持**: 调度器支持同时同步多个家庭的多个后端

## 文件清单

```
新增:
  frontend/apps/main/src/api/storageBackend.ts
  frontend/apps/main/src/pages/FamilyStorageBackendPage.vue
  server/apps/backend/alembic/versions/f5g6h7i8j9k0_add_family_id_to_storage_backends.py
  server/apps/backend/app/routers/storage_backend.py
  server/apps/backend/app/schemas/storage_backend.py

删除:
  server/apps/backend/app/bootstrap/storage_backends.py
  server/apps/backend/app/seed/storage_backends.py
  server/tests/backend/test_seed_storage_backends.py

修改: 22 files
  - 模型: storage_backend.py, family.py
  - 配置: settings.py, .env.example
  - 路由: files.py, main.py
  - 服务: service.py
  - 调度器: jobs/__init__.py
  - 测试: 6 个测试文件
  - 前端: SettingsPage.vue, router/index.ts, i18n 文件
```

## 下一步

用户现在可以：
1. 运行 `alembic upgrade head` 应用迁移
2. 删除旧的 `STORAGE_BACKEND_*` 环境变量
3. 启动应用
4. 在设置中配置家庭远程备份
