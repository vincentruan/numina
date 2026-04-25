# 设备信任认证设计规范

## 概述

统一父母和儿童账户的"记住登录"体验。用户登录后通过 post-login 提示选择是否信任当前设备，信任后颁发 30 天有效期的 refresh token 并创建 `DeviceSession` 记录。用户可在设置页查看和撤销已登录设备。

**核心决策：**
- 固定 30 天有效期，不可配置
- Post-login 提示（不是登录页 checkbox）
- 父母和儿童使用同一套设备信任机制
- 儿童不信任设备时 refresh token 改为 30 天（废弃原 10 年设计）
- PIN 码仅在后端以 Argon2 哈希存储，前端不缓存任何形式的 PIN

---

## Part 1：数据模型

### 新增表：device_sessions

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BigInteger PK | Snowflake ID |
| user_id | BigInteger FK → users | 关联用户（父母或儿童） |
| family_id | BigInteger FK → families | 冗余存储，便于按家庭查询 |
| device_name | String(200) | 由 `user-agents` 库解析 User-Agent 生成，如 "iPhone · Safari" |
| refresh_jti | String(36) | 当前有效 refresh token 的 JTI（唯一索引） |
| created_at | DateTime | 设备首次信任时间 |
| last_seen_at | DateTime | 最近一次 token refresh 时间 |
| expires_at | DateTime | created_at + 30 天，固定不滚动 |
| is_revoked | Boolean | 默认 False，主动撤销时设为 True |

**索引：**
- `refresh_jti`（唯一索引，用于 refresh 时快速查找）
- `user_id + is_revoked + expires_at`（设备列表查询）
- `family_id`（家庭维度查询）

### 现有模型变更

- `User` 模型无需改动
- `settings.CHILD_REFRESH_TOKEN_EXPIRE_DAYS` 从 3650 天改为 30 天
- `settings.REFRESH_TOKEN_EXPIRE_DAYS` 保持 7 天（非信任设备的 adult session）

---

## Part 2：认证流程

### Adult 登录流程

1. `POST /auth/login` 验证用户名 + 密码
2. 登录成功：颁发 access token（15 min）+ refresh token（7 天），设置 httpOnly cookie
3. 前端收到 `200` 后弹出 bottom sheet："要在此设备上保持登录状态吗？（30 天）"
4. **用户确认** → 前端调用 `POST /auth/device/trust`
   - 后端创建 `DeviceSession`，重新签发 30 天 refresh token，更新 cookie `max_age`
5. **用户拒绝** → 保持 7 天 refresh token，不创建 `DeviceSession`

### Child 登录流程

与 adult 流程相同，区别：
- 步骤 1 为 `POST /auth/child/pin-login` 或 WebAuthn 端点
- 使用 `child_access_token` / `child_refresh_token` cookie
- 步骤 4 调用同一个 `POST /auth/device/trust`（后端根据 token 类型判断）
- 不信任设备时 child refresh token 为 30 天（与 adult 对齐）

### Token Refresh 流程

1. 前端携带 refresh token cookie 调用 `POST /auth/refresh`
2. 后端验证 refresh token JTI：
   - **JTI 存在于 `DeviceSession.refresh_jti`**（信任设备）：
     - 签发新 access token
     - Rotate refresh token：新 JTI 写回 `DeviceSession.refresh_jti`，旧 JTI 加入 `RevokedToken`
     - 更新 `DeviceSession.last_seen_at`
   - **JTI 不存在**（普通 session）：走现有逻辑，不涉及 `DeviceSession`
3. 返回新 access token，更新 cookie

### Session 过期 / 撤销

- Refresh token 过期或 JTI 被撤销 → 后端返回 `401`
- 前端 HTTP 拦截器捕获 `401` on `/auth/refresh` → 显示 bottom sheet："登录已过期，请重新登录" + 确认按钮 → 跳转 `/login`
- 不静默跳转，给用户一次确认机会

---

## Part 3：API 端点

### 新增端点

#### POST /auth/device/trust — 信任当前设备

**权限**：有效 access token（adult 或 child）

**逻辑**：
1. 从 cookie 读取当前 refresh token，提取 JTI
2. 创建 `DeviceSession`（`expires_at = now + 30d`，`device_name` 由 `user-agents` 解析）
3. 重新签发 30 天 refresh token，写入新 JTI 到 `DeviceSession.refresh_jti`
4. 更新 cookie `max_age = 30 * 24 * 3600`

**响应**：
```json
{ "device_id": "...", "device_name": "iPhone · Safari", "expires_at": "2026-05-25T..." }
```

---

#### GET /auth/devices — 列出受信任设备

**权限**：有效 access token（adult 或 child）

**逻辑**：查询 `user_id` 匹配、`is_revoked=False`、`expires_at > now` 的记录

**响应**：
```json
[
  {
    "id": "...",
    "device_name": "iPhone · Safari",
    "created_at": "2026-04-01T10:00:00Z",
    "last_seen_at": "2026-04-25T08:30:00Z",
    "expires_at": "2026-05-01T10:00:00Z",
    "is_current": true
  }
]
```

`is_current`：通过比对请求的 refresh token JTI 与 `DeviceSession.refresh_jti` 判断。

---

#### DELETE /auth/devices/{device_id} — 撤销指定设备

**权限**：有效 access token（不接受 refresh token，防止 token 泄露后自我撤销）

**逻辑**：
1. 验证 `device_id` 属于当前用户
2. `DeviceSession.is_revoked = True`
3. 将 `refresh_jti` 加入 `RevokedToken` 表
4. 若撤销的是当前设备：清除 cookie，返回 `200`，前端跳转登录页

---

#### DELETE /auth/devices — 撤销所有设备

**权限**：有效 access token

**逻辑**：批量撤销当前用户所有 `DeviceSession`，所有 JTI 加入 `RevokedToken`，清除 cookie，前端跳转登录页。

---

### Device Name 解析

使用 `user-agents` Python 库（底层 `ua-parser`）：

```python
from user_agents import parse

ua = parse(request.headers.get("user-agent", ""))
device = ua.device.family  # "iPhone", "Other"
browser = ua.browser.family  # "Safari", "Chrome"
os = ua.os.family  # "iOS", "Android", "Windows"

if device != "Other":
    device_name = f"{device} · {browser}"
else:
    device_name = f"{os} · {browser}"

device_name = device_name or "未知设备"
```

---

## Part 4：前端

### Post-Login 提示

登录成功后（`POST /auth/login` 或 `POST /auth/child/pin-login` 返回 `200`）弹出 Vant `ActionSheet` 或 `Dialog`：

```
要在此设备上保持登录状态吗？
登录状态将保留 30 天

[保持登录]   [暂不]
```

- 点击"保持登录" → 调用 `POST /auth/device/trust` → 成功后进入主页
- 点击"暂不" → 直接进入主页

### 设备管理页

路由：`/settings/devices`，入口在"设置 → 账户安全"。

**列表项**：设备名称、最后活跃时间（相对时间，如"3 小时前"）、到期时间、"当前设备"标签。

**操作**：
- 每行"撤销"按钮（当前设备显示"退出此设备"，点击后跳转登录页）
- 底部"退出所有其他设备"按钮

### 401 拦截器

```ts
// 在 HTTP client 拦截器中
if (error.response?.status === 401 && isRefreshEndpoint) {
  showDialog({
    message: '登录已过期，请重新登录',
    confirmButtonText: '重新登录',
  }).then(() => router.push('/login'))
}
```

---

## Part 5：安全

### PIN 码存储

- PIN 码仅在后端以 Argon2 哈希存储（现有实现已满足）
- 前端只传输明文 PIN 序列（HTTPS 传输加密）
- **禁止**前端以任何形式缓存 PIN（localStorage、sessionStorage、cookie 均不可）

### 并发 Refresh 竞态

- `refresh_jti` 唯一索引保证并发安全
- 并发两个 refresh 请求：第一个成功写入新 JTI，第二个因旧 JTI 已被撤销返回 `401`
- 这是现有 JTI rotation 的既有行为，无需额外处理

### 设备撤销安全

- 撤销端点只接受 access token，不接受 refresh token
- 防止攻击者拿到 refresh token 后自我撤销以清除痕迹

### 会话清理

现有 hourly scheduler 扩展，额外清理：
- `expires_at < now` 且 `is_revoked = False` 的过期 `DeviceSession`（标记为撤销）
- `is_revoked = True` 且超过 7 天的记录（物理删除，审计窗口）

---

## Part 6：测试策略

### 后端单元测试

- `DeviceSession` 创建、过期、撤销逻辑
- `POST /auth/device/trust`：正常路径、重复信任同一设备、无效 token
- `GET /auth/devices`：`is_current` 标记正确
- `DELETE /auth/devices/{id}`：撤销后 JTI 进入 `RevokedToken`，refresh 返回 `401`
- Token refresh with device session：JTI rotation 正确写回 `DeviceSession.refresh_jti`
- Child login trust flow：与 adult 走同一端点，结果一致
- 过期 session 不出现在设备列表

### 集成测试

- 完整 adult trust flow：login → trust → refresh（验证 JTI rotation）→ revoke → refresh 返回 `401`
- 完整 child trust flow：pin-login → trust → refresh → revoke
- 并发 refresh：两个请求同时到达，只有一个成功

### 前端测试

- Post-login 提示：确认 / 拒绝两条路径
- 设备列表页：加载、撤销、"退出所有其他设备"
- `401` 拦截器：触发 bottom sheet，不静默跳转

---

## 与现有 child-device-auth-spec 的关系

`child-device-auth-spec.md` 描述的是父母授权设备 + child_device_tokens 表的方案（独立 opaque token）。本规范采用统一 DeviceSession 方案，覆盖父母和儿童，两者不兼容。实现时以本规范为准，child-device-auth-spec.md 可归档。

---

## 待办清单

- [ ] 数据库迁移：创建 `device_sessions` 表
- [ ] 后端：添加 `user-agents` 依赖
- [ ] 后端：实现 `POST /auth/device/trust`
- [ ] 后端：实现 `GET /auth/devices`
- [ ] 后端：实现 `DELETE /auth/devices/{device_id}`
- [ ] 后端：实现 `DELETE /auth/devices`
- [ ] 后端：修改 token refresh 逻辑，支持 DeviceSession JTI rotation
- [ ] 后端：修改 `CHILD_REFRESH_TOKEN_EXPIRE_DAYS` 为 30 天
- [ ] 后端：扩展 hourly scheduler 清理 DeviceSession
- [ ] 前端：post-login 提示组件
- [ ] 前端：设备管理页 `/settings/devices`
- [ ] 前端：`401` 拦截器 bottom sheet
- [ ] 测试：覆盖上述测试策略
