# API Layer Design

**Date:** 2026-04-21
**Status:** Approved
**Scope:** API 端点定义、认证机制、响应格式、速率限制

---

## Problem

1. API 缺乏统一规范文档，前后端协作困难
2. API 缺乏速率限制保护，容易遭受暴力破解和滥用攻击

---

## Goals

1. 定义所有 API 端点及响应格式
2. 规范认证和错误处理机制
3. 防止登录暴力破解攻击
4. 保护 API 端点免受滥用

---

## Architecture

### API 认证机制

使用 JWT Bearer Token 认证：
- Access Token 有效期：15分钟
- Refresh Token 有效期：7天
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

### 双层限流策略

**登录专用限流**：
- 策略：按用户名限流
- 触发条件：同一用户名连续失败 5 次
- 惩罚：锁定 15 分钟
- 存储位置：缓存层

**全局 API 限流**：
- 策略：按客户端标识限流
- 限制：每个客户端 100 次/分钟
- 跳过端点：健康检查、登录、注册
- 客户端标识：已认证用 token 前缀，未认证用 IP

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

### 心愿端点

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/wishes` | 心愿列表（支持 status 过滤） |
| POST | `/wishes` | 创建心愿 |
| GET | `/wishes/{id}` | 心愿详情 |
| PUT | `/wishes/{id}` | 更新心愿 |
| DELETE | `/wishes/{id}` | 删除心愿 |
| POST | `/wishes/{id}/realize` | 实现心愿为资产 |

### 仪表盘端点

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/dashboard/overview` | 总览 |
| GET | `/dashboard/allocation` | 资产分布 |
| GET | `/dashboard/trend` | 净资产趋势 |
| GET | `/dashboard/top-assets` | 高价值资产 |
| GET | `/dashboard/daily-cost` | 日均成本排名 |
| GET | `/dashboard/low-usage` | 低使用率资产 |
| GET | `/dashboard/investment-returns` | 投资收益率 |
| GET | `/dashboard/states-summary` | 状态汇总 |

### 导出导入端点

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/export/assets/csv` | 导出资产 CSV |
| GET | `/export/liabilities/csv` | 导出负债 CSV |
| GET | `/export/all/json` | 全量 JSON 备份 |
| POST | `/import/assets/csv` | 导入资产 CSV |

### 登录限流实现

```python
class LoginRateLimiter:
    MAX_ATTEMPTS = 5
    LOCKOUT_SECONDS = 900
    
    def check_lockout(self, username: str, cache: CacheBackend) -> int | None:
        key = f"login_lockout:{username}"
        ttl = cache.get_ttl(key)
        if ttl and ttl > 0:
            return int(ttl / 60)
        return None
    
    def record_failure(self, username: str, cache: CacheBackend) -> None:
        key = f"login_attempts:{username}"
        count = cache.increment(key)
        if count >= self.MAX_ATTEMPTS:
            cache.set(f"login_lockout:{username}", True, ttl_seconds=self.LOCKOUT_SECONDS)
            cache.delete(key)
```

### 全局 API 限流实现

```python
class GlobalRateLimiter:
    LIMIT_PER_MINUTE = 100
    SKIP_PATHS = ["/api/health", "/api/v1/auth/login", "/api/v1/auth/register"]
    
    def get_client_id(self, request: Request) -> str:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return f"token:{auth_header[7:15]}"
        return f"ip:{request.client.host}"
```

### 登录恒定响应时间（防止用户枚举）

```python
if not user:
    bcrypt.checkpw("dummy_password", bcrypt.hashpw("dummy", bcrypt.gensalt()))
    raise HTTPException(401, "用户名或密码错误")
```

---

## Code Pointers

| 模块 | 文件路径 |
|------|----------|
| 认证路由 | `backend/app/routers/auth.py` |
| 资产路由 | `backend/app/routers/assets.py` |
| 心愿路由 | `backend/app/routers/wishes.py` |
| 仪表盘路由 | `backend/app/routers/dashboard.py` |
| 登录限流器 | `backend/app/middleware/rate_limit.py` |
| 全局限流器 | `backend/app/middleware/rate_limit.py` |

---

## Related Specs

- **数据层设计**：`2026-04-21-data-layer-design.md` — 实体定义
- **安全层设计**：`2026-04-21-security-layer-design.md` — 恒定响应时间、统一错误信息、限流日志