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

**响应**：

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

### 刷新 Token

```http
POST /api/v1/auth/refresh
Authorization: Bearer <refresh_token>
```

---

## API 端点列表

### 认证模块 (/auth)

| 方法 | 端点 | 说明 | 认证 |
|------|------|------|------|
| POST | /auth/register | 用户注册 | ❌ |
| POST | /auth/login | 用户登录 | ❌ |
| POST | /auth/refresh | 刷新 Token | ✅ |
| GET | /auth/me | 获取当前用户 | ✅ |

### 资产模块 (/assets)

| 方法 | 端点 | 说明 | 认证 |
|------|------|------|------|
| GET | /assets | 获取资产列表 | ✅ |
| GET | /assets/{id} | 获取资产详情 | ✅ |
| POST | /assets | 创建资产 | ✅ |
| PUT | /assets/{id} | 更新资产 | ✅ |
| DELETE | /assets/{id} | 删除资产 | ✅ |
| GET | /assets/stats | 获取资产统计 | ✅ |

### 分类模块 (/categories)

| 方法 | 端点 | 说明 | 认证 |
|------|------|------|------|
| GET | /categories | 获取分类列表 | ✅ |
| POST | /categories | 创建分类 | ✅ |
| PUT | /categories/{id} | 更新分类 | ✅ |
| DELETE | /categories/{id} | 删除分类 | ✅ |

### 标签模块 (/tags)

| 方法 | 端点 | 说明 | 认证 |
|------|------|------|------|
| GET | /tags | 获取标签列表 | ✅ |
| POST | /tags | 创建标签 | ✅ |
| PUT | /tags/{id} | 更新标签 | ✅ |
| DELETE | /tags/{id} | 删除标签 | ✅ |

### 负债模块 (/liabilities)

| 方法 | 端点 | 说明 | 认证 |
|------|------|------|------|
| GET | /liabilities | 获取负债列表 | ✅ |
| GET | /liabilities/{id} | 获取负债详情 | ✅ |
| POST | /liabilities | 创建负债 | ✅ |
| PUT | /liabilities/{id} | 更新负债 | ✅ |
| DELETE | /liabilities/{id} | 删除负债 | ✅ |

### 心愿模块 (/wishes)

| 方法 | 端点 | 说明 | 认证 |
|------|------|------|------|
| GET | /wishes | 获取心愿列表 | ✅ |
| GET | /wishes/{id} | 获取心愿详情 | ✅ |
| POST | /wishes | 创建心愿 | ✅ |
| PUT | /wishes/{id} | 更新心愿 | ✅ |
| DELETE | /wishes/{id} | 删除心愿 | ✅ |

### 家庭模块 (/family)

| 方法 | 端点 | 说明 | 认证 |
|------|------|------|------|
| GET | /family | 获取家庭信息 | ✅ |
| PUT | /family | 更新家庭信息 | ✅ |
| POST | /family/members | 添加成员 | ✅ |
| DELETE | /family/members/{id} | 移除成员 | ✅ |
| POST | /family/invite-code | 生成邀请码 | ✅ |
| POST | /family/join | 加入家庭 | ✅ |
| GET | /family/snapshots | 获取快照列表 | ✅ |
| POST | /family/snapshots/generate | 生成快照 | ✅ |

### 仪表盘模块 (/dashboard)

| 方法 | 端点 | 说明 | 认证 |
|------|------|------|------|
| GET | /dashboard/overview | 获取总览数据 | ✅ |
| GET | /dashboard/allocation | 获取资产分布 | ✅ |
| GET | /dashboard/trend | 获取趋势数据 | ✅ |
| GET | /dashboard/top-assets | 获取高价值资产 | ✅ |
| GET | /dashboard/daily-cost-ranking | 获取日均成本排名 | ✅ |
| GET | /dashboard/low-usage-assets | 获取低使用率资产 | ✅ |
| GET | /dashboard/expiring-soon | 获取即将到期资产 | ✅ |
| GET | /dashboard/investment-returns | 获取投资收益率 | ✅ |
| GET | /dashboard/states-summary | 获取状态汇总 | ✅ |
| GET | /dashboard/home-assets | 获取首页资产 | ✅ |

---

## 请求格式

### 分页参数

```
GET /assets?offset=0&limit=20
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| offset | int | 0 | 偏移量 |
| limit | int | 20 | 每页数量（最大 100） |

### 筛选参数

```
GET /assets?status=in_use&asset_type=physical&category_id=xxx
```

### 排序参数

```
GET /assets?sort_by=created_at&sort_order=desc
```

---

## 响应格式

### 成功响应

**单个资源**：

```json
{
  "id": "uuid",
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

**创建成功**（HTTP 201）：

```json
{
  "id": "uuid",
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
| 200 OK | 请求成功 |
| 201 Created | 资源创建成功 |
| 204 No Content | 删除成功（无响应体） |
| 400 Bad Request | 请求参数错误 |
| 401 Unauthorized | 未认证 |
| 403 Forbidden | 无权限 |
| 404 Not Found | 资源不存在 |
| 422 Unprocessable Entity | 数据验证失败 |
| 429 Too Many Requests | 请求频率超限 |
| 500 Internal Server Error | 服务器错误 |

---

## 业务错误码

| 错误码 | 说明 |
|--------|------|
| AUTH_001 | 用户名已存在 |
| AUTH_002 | 密码错误 |
| AUTH_003 | Token 已过期 |
| FAMILY_001 | 邀请码无效 |
| FAMILY_002 | 已是家庭成员 |
| ASSET_001 | 资产不存在 |
| ASSET_002 | 无权操作此资产 |

---

## 速率限制

| 端点类型 | 限制 |
|----------|------|
| 认证端点 | 10 次/分钟 |
| API 端点 | 100 次/分钟 |

超出限制返回 HTTP 429。

---

## 版本控制

API 使用 URL 路径版本控制：

- 当前版本：`/api/v1/`
- 未来版本：`/api/v2/`

向后兼容的变更不增加版本号，破坏性变更发布新版本。