# Numina API 规范

## 认证方式

### JWT Bearer Token

所有需要认证的 API 端点都使用 JWT Bearer Token 认证：

```
Authorization: Bearer <access_token>
```

### 获取 Token

```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "username": "demouser",
  "password": "DemoPass123"
}
```

**响应** (200)：

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer"
}
```

### Token 有效期

| Token 类型 | 有效期 |
|-----------|--------|
| access_token | 30 分钟 |
| refresh_token | 7 天 |

> **注意：** 注册、登录、加入家庭等认证端点返回 200（非 201）。

---

## API 端点列表

### 认证模块 (/api/v1/auth)

| 方法 | 端点 | 说明 | 认证 |
|------|------|------|------|
| POST | /api/v1/auth/register | 用户注册 | ❌ |
| POST | /api/v1/auth/login | 用户登录 | ❌ |
| POST | /api/v1/auth/refresh | 刷新 Token | ✅ |
| GET | /api/v1/auth/me | 获取当前用户 | ✅ |
| PUT | /api/v1/auth/me | 更新个人信息 | ✅ |
| POST | /api/v1/auth/join-family | 加入家庭 | ✅ |
| POST | /api/v1/auth/change-password | 修改密码 | ✅ |

### 资产模块 (/api/v1/assets)

| 方法 | 端点 | 说明 | 认证 |
|------|------|------|------|
| GET | /api/v1/assets | 获取资产列表 | ✅ |
| GET | /api/v1/assets/{id} | 获取资产详情 | ✅ |
| POST | /api/v1/assets | 创建资产 | ✅ (201) |
| PUT | /api/v1/assets/{id} | 更新资产 | ✅ |
| DELETE | /api/v1/assets/{id} | 删除资产 | ✅ |
| POST | /api/v1/assets/{id}/sell | 出售/处置 | ✅ |
| GET | /api/v1/assets/stats | 获取资产统计 | ✅ |
| GET | /api/v1/assets/analytics | 获取资产分析 | ✅ |

### 分类模块 (/api/v1/categories)

| 方法 | 端点 | 说明 | 认证 |
|------|------|------|------|
| GET | /api/v1/categories | 获取分类列表 | ✅ |
| POST | /api/v1/categories | 创建分类 | ✅ (201) |
| PUT | /api/v1/categories/{id} | 更新分类 | ✅ |
| DELETE | /api/v1/categories/{id} | 删除分类 | ✅ |

### 标签模块 (/api/v1/tags)

| 方法 | 端点 | 说明 | 认证 |
|------|------|------|------|
| GET | /api/v1/tags | 获取标签列表 | ✅ |
| POST | /api/v1/tags | 创建标签 | ✅ (201) |
| PUT | /api/v1/tags/{id} | 更新标签 | ✅ |
| DELETE | /api/v1/tags/{id} | 删除标签 | ✅ |

### 负债模块 (/api/v1/liabilities)

| 方法 | 端点 | 说明 | 认证 |
|------|------|------|------|
| GET | /api/v1/liabilities | 获取负债列表 | ✅ |
| GET | /api/v1/liabilities/{id} | 获取负债详情 | ✅ |
| POST | /api/v1/liabilities | 创建负债 | ✅ (201) |
| PUT | /api/v1/liabilities/{id} | 更新负债 | ✅ |
| DELETE | /api/v1/liabilities/{id} | 删除负债 | ✅ |
| GET | /api/v1/liabilities/{id}/amortization | 摊销计划 | ✅ |

### 租约模块 (/api/v1/rental)

| 方法 | 端点 | 说明 | 认证 |
|------|------|------|------|
| GET | /api/v1/rental/contracts | 获取租约列表 | ✅ |
| GET | /api/v1/rental/contracts/{id} | 获取租约详情 | ✅ |
| POST | /api/v1/rental/contracts | 创建租约 | ✅ (201) |
| PUT | /api/v1/rental/contracts/{id} | 更新租约 | ✅ |
| DELETE | /api/v1/rental/contracts/{id} | 删除租约 | ✅ |
| GET | /api/v1/rental/dashboard | 租约仪表盘 | ✅ |

### 心愿模块 (/api/v1/wishes)

| 方法 | 端点 | 说明 | 认证 |
|------|------|------|------|
| GET | /api/v1/wishes | 获取心愿列表 | ✅ |
| GET | /api/v1/wishes/{id} | 获取心愿详情 | ✅ |
| POST | /api/v1/wishes | 创建心愿 | ✅ (201) |
| PUT | /api/v1/wishes/{id} | 更新心愿 | ✅ |
| DELETE | /api/v1/wishes/{id} | 删除心愿 | ✅ |

### 家庭模块 (/api/v1/family)

| 方法 | 端点 | 说明 | 认证 |
|------|------|------|------|
| GET | /api/v1/family | 获取家庭信息 | ✅ |
| PUT | /api/v1/family | 更新家庭信息 | ✅ |
| GET | /api/v1/family/members | 获取成员列表 | ✅ |
| PATCH | /api/v1/family/settings | 更新家庭设置 | ✅ |
| POST | /api/v1/family/manifesto | 签署家庭宣言 | ✅ |
| GET | /api/v1/family/manifesto | 获取家庭宣言 | ✅ |

### 儿童/宝贝模块 (/api/v1/baby)

| 方法 | 端点 | 说明 | 认证 |
|------|------|------|------|
| GET | /api/v1/baby/chores | 家务列表 | ✅ |
| POST | /api/v1/baby/chores | 创建家务 | ✅ (201) |
| GET | /api/v1/baby/chore-templates | 家务模板 | ✅ |
| POST | /api/v1/baby/chore-templates | 创建模板 | ✅ (201) |
| PATCH | /api/v1/baby/chores/{id}/approve | 审批家务 | ✅ |
| GET | /api/v1/baby/blind-box/gifts | 盲盒礼物列表 | ✅ |
| POST | /api/v1/baby/blind-box/draw | 盲盒抽奖 | ✅ |
| GET | /api/v1/baby/literacy/scenarios | 学习场景列表 | ✅ |
| GET | /api/v1/baby/literacy/badges | 徽章列表 | ✅ |

### 仪表盘模块 (/api/v1/dashboard)

| 方法 | 端点 | 说明 | 认证 |
|------|------|------|------|
| GET | /api/v1/dashboard/overview | 总览数据 | ✅ |
| GET | /api/v1/dashboard/allocation | 资产分布 | ✅ |
| GET | /api/v1/dashboard/trend | 趋势数据 | ✅ |
| GET | /api/v1/dashboard/top-assets | 高价值资产 | ✅ |
| GET | /api/v1/dashboard/daily-cost-ranking | 日均成本排名 | ✅ |
| GET | /api/v1/dashboard/low-usage-assets | 低使用率资产 | ✅ |
| GET | /api/v1/dashboard/expiring-soon | 即将到期资产 | ✅ |
| GET | /api/v1/dashboard/investment-returns | 投资收益率 | ✅ |
| GET | /api/v1/dashboard/states-summary | 状态汇总 | ✅ |
| GET | /api/v1/dashboard/narrative | AI 仪表盘叙事 | ✅ |
| GET | /api/v1/dashboard/finance-coach | 财务教练建议 | ✅ |
| GET | /api/v1/dashboard/education-reward-summary | 教育奖励统计 | ✅ |

### AI 模块 (/api/v1/ai)

| 方法 | 端点 | 说明 | 认证 |
|------|------|------|------|
| POST | /api/v1/ai/chat/stream | 流式对话 (SSE) | ✅ |
| GET | /api/v1/ai/threads | 对话线程列表 | ✅ |
| GET | /api/v1/ai/threads/{id} | 对话线程详情 | ✅ |
| DELETE | /api/v1/ai/threads/{id} | 删除对话线程 | ✅ |
| POST | /api/v1/ai/tasks | 创建异步 AI 任务 | ✅ |
| GET | /api/v1/ai/tasks/{id} | 查询任务状态 | ✅ |
| POST | /api/v1/ai/tasks/{id}/cancel | 取消任务 | ✅ |
| GET | /api/v1/ai/config/defaults | AI 默认配置 | ✅ |
| GET | /api/v1/ai/skills | 技能列表 | ✅ |
| POST | /api/v1/ai/skills | 创建技能 | ✅ |
| GET | /api/v1/ai/context | 家庭上下文 | ✅ |

### 通知模块 (/api/v1/notifications)

| 方法 | 端点 | 说明 | 认证 |
|------|------|------|------|
| GET | /api/v1/notifications/reminders | 提醒列表 | ✅ |
| POST | /api/v1/notifications/reminders | 创建提醒 | ✅ (201) |
| PUT | /api/v1/notifications/reminders/{id} | 更新提醒 | ✅ |
| DELETE | /api/v1/notifications/reminders/{id} | 删除提醒 | ✅ |
| GET | /api/v1/notifications/config | 通知配置 | ✅ |
| PUT | /api/v1/notifications/config | 更新通知配置 | ✅ |
| GET | /api/v1/notifications/thresholds | 阈值告警配置 | ✅ |
| PUT | /api/v1/notifications/thresholds | 更新阈值配置 | ✅ |

### 系统模块 (/api)

| 方法 | 端点 | 说明 | 认证 |
|------|------|------|------|
| GET | /api/health | 健康检查 | ❌ |
| GET | /api/v1/system/config | 系统配置 | ❌ |
| GET | /api/v1/currencies | 货币列表 | ❌ |
| GET | /api/v1/exchange-rates | 汇率查询 | ❌ |

---

## 请求格式

### 分页参数

```
GET /api/v1/assets?offset=0&limit=20
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| offset | int | 0 | 偏移量 |
| limit | int | 20 | 每页数量（最大 100） |

### 筛选参数

```
GET /api/v1/assets?status=in_use&asset_type=physical&category_id=123
```

### 排序参数

```
GET /api/v1/assets?sort_by=created_at&sort_order=desc
```

---

## 响应格式

### Snowflake ID 序列化

所有 ID 字段在 JSON 响应中序列化为 **string**，避免 JS 精度丢失：

```json
{
  "id": "1234567890123456789",
  "family_id": "9876543210987654321"
}
```

### 成功响应

**单个资源**：

```json
{
  "id": "1234567890123456789",
  "name": "资产名称",
  "created_at": "2024-01-01T00:00:00Z"
}
```

**资源列表**：

```json
{
  "items": [...],
  "total": 100,
  "offset": 0,
  "limit": 20
}
```

**信封格式**（部分端点）：

```json
{
  "data": { ... },
  "meta": { ... }
}
```

**创建成功**（HTTP 201）：

```json
{
  "id": "1234567890123456789",
  "name": "新资产",
  "created_at": "2024-01-01T00:00:00Z"
}
```

### 错误响应

```json
{
  "detail": "错误描述信息"
}
```

**字段验证错误**（HTTP 422）：

```json
{
  "detail": [
    {
      "loc": ["body", "name"],
      "msg": "字段不能为空",
      "type": "value_error.missing"
    }
  ]
}
```

---

## HTTP 状态码

| 状态码 | 说明 |
|--------|------|
| 200 OK | 请求成功（认证端点也返回 200） |
| 201 Created | 资源创建成功（资产/负债/心愿等 POST） |
| 204 No Content | 删除成功（无响应体） |
| 400 Bad Request | 请求参数错误 |
| 401 Unauthorized | 未认证 |
| 403 Forbidden | 无权限 |
| 404 Not Found | 资源不存在 |
| 422 Unprocessable Entity | 数据验证失败 |
| 429 Too Many Requests | 请求频率超限 |
| 500 Internal Server Error | 服务器错误 |

---

## 速率限制

| 端点类型 | 限制 |
|----------|------|
| 认证端点 | 10 次/分钟 |
| API 端点 | 100 次/分钟 |

超出限制返回 HTTP 429。

---

## URL 约定

所有端点**不带尾部斜杠**，无 307 重定向：

```
✅ GET /api/v1/assets
❌ GET /api/v1/assets/  → 不会 307 重定向
```

---

## 版本控制

API 使用 URL 路径前缀 `/api/v1/`。向后兼容的变更不增加版本号，破坏性变更发布新版本。
