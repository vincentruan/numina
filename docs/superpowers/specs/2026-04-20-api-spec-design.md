# API Specification Design

**Date:** 2026-04-20
**Status:** Approved
**Scope:** API 端点定义、认证方式、请求响应格式

---

## Problem

API 缺乏统一规范文档，前后端协作困难。开发者不清楚端点列表、认证方式、错误处理机制，导致实现不一致和集成问题。

---

## Goals

1. 定义所有 API 端点及响应格式
2. 规范认证和错误处理机制
3. 提供前后端协作参考
4. 确保安全防护措施一致性

---

## Architecture

### API 认证机制

使用 JWT Bearer Token 认证：
- Access Token 有效期：15分钟（`ACCESS_TOKEN_EXPIRE_MINUTES`）
- Refresh Token 有效期：7天（`REFRESH_TOKEN_EXPIRE_DAYS`）
- Token 刷新：`POST /api/v1/auth/refresh`

请求携带：`Authorization: Bearer <access_token>`

### 响应格式标准

**成功响应**：
```json
{
  "data": { ... },
  "message": "操作成功"
}
```

**错误响应**：
```json
{
  "detail": "错误信息（中文）"
}
```

**分页响应**：
```json
{
  "items": [...],
  "total": 100,
  "page": 1,
  "per_page": 20
}
```

### API 模块分组

| 模块 | 路径前缀 | 说明 |
|------|----------|------|
| 认证 | `/api/v1/auth` | 登录、注册、token刷新 |
| 资产 | `/api/v1/assets` | CRUD、价值更新、出售、退役 |
| 负债 | `/api/v1/liabilities` | CRUD、还款记录 |
| 心愿 | `/api/v1/wishes` | CRUD、实现心愿 |
| 家庭 | `/api/v1/family` | 成员管理、邀请码、快照 |
| 仪表盘 | `/api/v1/dashboard` | 统计数据、趋势图表 |
| 分类 | `/api/v1/categories` | CRUD（系统分类只读） |
| 标签 | `/api/v1/tags` | CRUD |
| 币种 | `/api/v1/currencies` | 币种列表、汇率查询 |
| 导出 | `/api/v1/export` | CSV/JSON 导出 |
| 导入 | `/api/v1/import` | CSV 导入 |
| 上传 | `/api/v1/upload` | 图片上传 |
| 活动 | `/api/v1/activities` | 操作日志 |

---

## Implementation Details

### 认证端点

| 方法 | 端点 | 说明 | 响应 |
|------|------|------|------|
| POST | `/auth/register` | 注册用户 | `TokenResponse` |
| POST | `/auth/login` | 登录 | `TokenResponse` |
| POST | `/auth/refresh` | 刷新 Token | `TokenResponse` |
| POST | `/auth/join-family` | 加入家庭 | `TokenResponse` |
| GET | `/auth/me` | 当前用户信息 | `UserResponse` |
| PUT | `/auth/me` | 更新用户信息 | `UserResponse` |

**TokenResponse**：
```json
{
  "access_token": "string",
  "refresh_token": "string",
  "token_type": "bearer"
}
```

### 心愿端点

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/wishes` | 心愿列表（支持 status 过滤） |
| POST | `/wishes` | 创建心愿 |
| GET | `/wishes/{id}` | 心愿详情 |
| PUT | `/wishes/{id}` | 更新心愿 |
| DELETE | `/wishes/{id}` | 删除心愿 |
| POST | `/wishes/{id}/realize` | 实现心愿为资产 |

**POST /wishes/{id}/realize**：
- 心愿状态变为 `realized`
- 创建 Asset 记录（关联 `realized_asset_id`）
- 返回新创建的资产信息

### 仪表盘扩展端点

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/dashboard/overview` | 总览（总资产、总负债、净资产） |
| GET | `/dashboard/allocation` | 资产分布（按分类） |
| GET | `/dashboard/trend` | 净资产趋势 |
| GET | `/dashboard/top-assets` | 高价值资产 |
| GET | `/dashboard/daily-cost` | 日均成本排名 |
| GET | `/dashboard/low-usage` | 低使用率资产 |
| GET | `/dashboard/investment-returns` | 投资收益率 |
| GET | `/dashboard/states-summary` | 状态汇总 |
| GET | `/dashboard/home-assets` | 首页展示资产 |
| GET | `/dashboard/expiring-soon` | 即将到期资产 |

**GET /dashboard/expiring-soon**：
Query 参数：`days_threshold=90`（默认）
返回：90 天内到期的资产列表

### 导出端点

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/export/assets/csv` | 导出资产 CSV |
| GET | `/export/liabilities/csv` | 导出负债 CSV |
| GET | `/export/all/json` | 全量 JSON 备份 |

CSV 编码：UTF-8 with BOM（Excel 兼容）

### 导入端点

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/import/assets/csv` | 导入资产 CSV |

导入响应：
```json
{
  "success": 10,
  "failed": 2,
  "errors": [
    {"row": 5, "message": "分类不存在"},
    {"row": 8, "message": "金额格式错误"}
  ]
}
```

### 上传端点

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/upload/image` | 上传图片 |

支持的格式：JPEG、PNG、WebP（通过 magic bytes 验证）
最大大小：5MB
返回：`{"url": "/uploads/xxx.jpg"}`

### 安全防护：登录恒定响应时间

防止用户名枚举攻击：
- 用户不存在时，执行 dummy bcrypt 验证消耗相同时间
- 平均响应时间差异小于 20%

实现：
```python
# 用户不存在时执行 dummy bcrypt
if not user:
    bcrypt.checkpw("dummy_password", bcrypt.hashpw("dummy", bcrypt.gensalt()))
    raise HTTPException(401, "用户名或密码错误")
```

### 安全防护：统一错误信息

登录失败不区分原因，统一返回：`"用户名或密码错误"`

不提示：用户不存在、密码错误、账户锁定等具体原因。

---

## Code Pointers

| 模块 | 文件路径 |
|------|----------|
| 认证路由 | `backend/app/routers/auth.py` |
| 资产路由 | `backend/app/routers/assets.py` |
| 负债路由 | `backend/app/routers/liabilities.py` |
| 心愿路由 | `backend/app/routers/wishes.py` |
| 家庭路由 | `backend/app/routers/family.py` |
| 仪表盘路由 | `backend/app/routers/dashboard.py` |
| 分类路由 | `backend/app/routers/categories.py` |
| 标签路由 | `backend/app/routers/tags.py` |
| 币种路由 | `backend/app/routers/currencies.py` |
| 导出路由 | `backend/app/routers/export.py` |
| 导入路由 | `backend/app/routers/import_.py` |
| 上传路由 | `backend/app/routers/upload.py` |
| 活动路由 | `backend/app/routers/activities.py` |

---

## Related Specs

- **数据模型**：`2026-04-20-data-models-design.md` — 实体定义
- **文件上传安全**：`2026-04-20-file-upload-security-design.md` — magic bytes 验证
- **速率限制**：`2026-04-20-rate-limiting-design.md` — 登录限流