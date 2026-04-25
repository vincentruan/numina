# 儿童端设备授权与 PIN 登录设计规范

## 概述

采用**父母凭据授权模式**：首次登录时由父母输入自己的账户密码完成授权，成功后为儿童设置 emoji PIN（需二次确认），并记录3个月有效期的设备标识。后续在有效期内儿童可直接用 PIN 登录。支持 PIN 找回/重置流程（重新走父母授权）。

---

## Part 1：数据库模型

### 新增表：child_device_tokens

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BigInteger PK | snowflake ID |
| child_id | BigInteger FK → users | 关联儿童账号 |
| family_id | BigInteger FK → families | 冗余存储，便于按家庭查询 |
| token_hash | String(64) | SHA-256(raw_token)，不存明文 |
| device_hint | String(200) | User-Agent 前200字符，仅用于展示 |
| authorized_by | BigInteger FK → users | 授权的父母 user_id |
| authorized_at | DateTime | 授权时间 |
| expires_at | DateTime | 授权时间 + 90天 |
| last_used_at | DateTime nullable | 最近一次 PIN 登录时间 |
| revoked_at | DateTime nullable | 父母主动吊销时间 |

**索引**：
- token_hash（唯一索引）
- child_id + revoked_at + expires_at（查询有效授权）

### User 模型

无需改动。`pin_hash` 已存在。PIN 重置只是更新 `pin_hash`，不需要新字段。

---

## Part 2：API 端点设计

### 新增端点（全部挂在 `/auth/child/` 前缀下）

#### ① POST /auth/child/device-authorize — 父母授权设备

**请求体**：
```json
{ "child_id": "123", "parent_password": "..." }
```

**逻辑**：
1. 验证 `parent_password` 匹配同家庭任意 owner/member（复用现有 `verify_parent_password`）
2. 生成 `secrets.token_urlsafe(32)` 作为 raw token
3. 存 child_device_tokens（`token_hash=sha256(raw_token)`, `expires_at=now+90d`）
4. 返回 `{ "device_token": "<raw_token>", "expires_at": "..." }`
5. 前端收到后存入 httpOnly cookie `child_device_token`，max_age=90天

---

#### ② GET /auth/child/device-status — 检查设备授权状态

**查询参数**：`?child_id=123`

从请求 cookie 读取 `child_device_token`，验证是否有效（未过期、未吊销、匹配 child_id）。

**返回**：
```json
{ "status": "authorized" | "expired" | "none", "has_pin": true | false }
```

前端用这个接口决定跳转哪个页面：
- `authorized + has_pin` → PIN 登录页
- `authorized + !has_pin` → PIN 设置页
- `expired / none` → 父母授权页

---

#### ③ POST /auth/child/setup-pin — 设置/重置 PIN（需设备授权）

**请求体**：
```json
{ "child_id": "123", "pin_sequence": ["🐱","🐶","🐸","🦊"], "mode": "set" | "reset", "reset_nonce": "..." }
```

**Cookie**：必须携带有效 `child_device_token`

**逻辑**：验证设备 token → 更新 `user.pin_hash` → 返回成功。

mode=reset 时需要额外携带从 `device-authorize` 响应中获取的 `reset_nonce`（5分钟有效，单次消费）。

---

#### ④ POST /auth/child/{child_id}/reset-pin — 父母主动重置 PIN

**权限**：需父母 JWT + `require_owner` 依赖

直接清空 `pin_hash`（设为 NULL），前端下次检测到 `has_pin=false` 自动引导重新设置。

---

#### ⑤ DELETE /auth/child/device-tokens/{token_id} — 父母吊销设备授权

**权限**：需父母 JWT + 验证 family_id 匹配

设置 `revoked_at=now`。

---

#### ⑥ GET /auth/child/{child_id}/device-tokens — 列出家庭所有设备授权

**权限**：需父母 JWT

返回该儿童所有未吊销的设备授权列表（含 device_hint、authorized_at、expires_at、last_used_at）。

---

### 修改现有端点

#### POST /auth/child/login（现有）

在 PIN 验证成功后，额外验证 cookie 中的 `child_device_token` 有效：
- 无有效设备 token → 返回 403 DEVICE_NOT_AUTHORIZED
- 有效 → 更新 `last_used_at` → 正常颁发 JWT

---

### 新增错误码

| 错误码 | HTTP | 含义 |
|--------|------|------|
| DEVICE_NOT_AUTHORIZED | 403 | 设备未授权或已过期 |
| DEVICE_TOKEN_INVALID | 401 | token 不存在或已吊销 |
| PIN_NOT_SET | 400 | 儿童尚未设置 PIN |

---

## Part 3：前端页面流程

### 新增页面

#### ChildParentAuthPage.vue — 父母密码授权

**UI**：
- 标题："父母授权"
- 副标题："为 [displayName] 授权此设备"
- 输入框：父母账户密码（type=password）
- 按钮：[确认授权]

**流程**：
1. 输入父母密码 → POST /auth/child/device-authorize
2. 成功：后端颁发 device_token → 前端存 httpOnly cookie → 根据后端返回的 `has_pin` 决定跳转
3. 失败：显示错误（密码错误 / 无权限）

---

#### ChildPinSetupPage.vue — 设置 emoji PIN（两步确认）

**步骤1**：
- 标题："为 [displayName] 设置图形密码"
- 4个圆点进度指示
- emoji 键盘（12个常用emoji）
- [删除] / [清除] 按钮

**步骤2**（输满4个后自动切换）：
- 标题："请再次输入确认"
- 4个圆点进度指示
- emoji 键盘

**结果**：
- 两次一致 → POST /auth/child/setup-pin → 成功提示 → 跳转 ChildAuthPage
- 两次不一致 → 抖动动画 → 清空第二次 → 提示"两次不一致，请重新输入"

**状态**：
```ts
const step = ref<1 | 2>(1)
const firstPin = ref<string[]>([])
const secondPin = ref<string[]>([])
```

---

### 修改现有页面

#### ChildAuthPage.vue

**改动**：
1. PIN 锁定时，在 lockMessage 下方增加"忘记图形密码？"按钮，点击跳转 ChildParentAuthPage（携带 mode=reset query 参数，授权成功后直接进 PIN 设置而非 PIN 登录）
2. 登录请求收到 403 DEVICE_NOT_AUTHORIZED 时，跳转 ChildParentAuthPage（设备 cookie 过期场景）

---

### 路由新增

```ts
{ path: '/child/parent-auth', name: 'ChildParentAuth', component: ChildParentAuthPage },
{ path: '/child/pin-setup',   name: 'ChildPinSetup',   component: ChildPinSetupPage },
```

两个新页面不需要 auth guard（授权前访问）。

---

#### ChildSelectPage.vue 改动

选中儿童后，先调 device-status，再根据结果路由：

```ts
async function selectChild(child: ChildUser) {
  const { status, has_pin } = await getChildDeviceStatus(child.id)
  if (status === 'authorized' && has_pin) {
    router.push({ name: 'ChildAuth', query: { ... } })
  } else if (status === 'authorized' && !has_pin) {
    router.push({ name: 'ChildPinSetup', query: { ... } })
  } else {
    router.push({ name: 'ChildParentAuth', query: { ... } })
  }
}
```

---

## Part 4：安全考虑

### 1. 设备 Token 安全

**存储**：raw token 只在颁发时返回一次，后端只存 SHA-256(raw_token)。即使数据库泄露，攻击者拿不到有效 token。

**Cookie 属性**：
```python
response.set_cookie(
    key="child_device_token",
    value=raw_token,
    max_age=90 * 24 * 60 * 60,  # 90天
    httponly=True,               # JS 不可读
    secure=production,           # HTTPS only
    samesite="strict",           # 防 CSRF
    path="/",
)
```

**绑定 child_id**：验证时必须同时匹配 cookie token + query 中的 child_id，防止一个儿童的 token 被用于另一个儿童。

---

### 2. 父母密码验证防护

复用现有 `verify_parent_password`，已有：
- bcrypt 恒定时间比较（防时序攻击）
- 无父母账号时也执行 dummy bcrypt

**新增**：`device-authorize` 端点需要独立限速，防止暴力枚举父母密码：

```python
# 复用现有 cache 机制
key = f"device_authorize_attempts:{child_id}"
# 5次失败 → 锁定15分钟
```

---

### 3. PIN 设置端点防滥用

POST /auth/child/setup-pin 必须验证 child_device_token cookie 有效，不能仅凭 child_id 参数就允许设置 PIN。否则任何人知道 child_id 就能覆盖 PIN。

**验证链**：
```
cookie child_device_token
  → SHA-256 → 查 child_device_tokens 表
  → 验证 child_id 匹配 + expires_at > now + revoked_at IS NULL
  → 通过才允许写 pin_hash
```

---

### 4. PIN 登录新增设备验证

**现有** POST /auth/child/login 只验证 PIN 正确性。**改造后**：

| 场景 | 结果 |
|------|------|
| PIN 正确 + 设备 token 有效 | 颁发 JWT ✅ |
| PIN 正确 + 设备 token 无效 | 403 DEVICE_NOT_AUTHORIZED ❌ |
| PIN 错误 | 401（现有逻辑不变） |

**顺序很重要**：先验证 PIN，再验证设备 token。反过来会泄露"该设备是否已授权"信息给未知 PIN 的攻击者。

---

### 5. 并发授权限制

同一儿童允许多设备授权（家里多个手机/平板），但建议：
- 单儿童最多 **5个** 有效设备 token（超出时拒绝新授权，提示父母先吊销旧设备）
- 父母端设备列表页展示 device_hint（User-Agent 前200字符），便于识别和吊销陌生设备

---

### 6. PIN 找回防绕过

"忘记 PIN" 流程必须重新走父母密码验证，不能仅凭旧的 child_device_token 就允许重置 PIN。

即：setup-pin 端点在 mode=reset 时，要求同时携带：
- 有效 child_device_token（设备已授权）
- 刚刚颁发的 device_authorize 响应中的一次性 reset_nonce（5分钟有效）

这样即使攻击者偷到设备 cookie，也无法在没有父母密码的情况下重置 PIN。

**实现**：device-authorize 响应额外返回 `{ "reset_nonce": "..." }`，前端存 sessionStorage（不存 localStorage，页面关闭即失效），setup-pin 请求体携带此 nonce，后端验证后单次消费。

---

### 7. 审计日志

以下操作写入现有 audit_log：
- 父母授权设备（记录 authorized_by、device_hint）
- PIN 设置/重置
- 设备 token 吊销
- 设备 token 过期触发的重新授权

---

## 待办清单

- [ ] 数据库迁移：创建 child_device_tokens 表
- [ ] 后端：实现 6 个新 API 端点
- [ ] 后端：修改 /auth/child/login 增加设备验证
- [ ] 后端：新增错误码到 ErrorCode 枚举
- [ ] 前端：创建 ChildParentAuthPage.vue
- [ ] 前端：创建 ChildPinSetupPage.vue（两步 PIN 设置）
- [ ] 前端：修改 ChildSelectPage.vue 路由逻辑
- [ ] 前端：修改 ChildAuthPage.vue（忘记 PIN、403 跳转）
- [ ] 前端：新增路由配置
- [ ] 前端：API client 更新（新增 6 个接口）
- [ ] 测试：E2E 覆盖完整流程
