# 多账户设备绑定登录设计

**Date:** 2026-06-06
**Status:** Draft — pending user review

## 背景

登录流程为两阶段设计：
- **一阶段**：身份确认（用户名/密码 或 设备绑定快速选择）+ ALTCHA 验证码
- **二阶段**：根据角色验证 PIN（管理员/大人：数字PIN 或跳过；儿童：必须验证 emoji PIN）

设备信任机制已于 2026-05-29 从 FingerprintJS 迁移到 server-issued UUID（cookie + localStorage）。但当前仅依赖 cookie + localStorage 两层存储，在用户清除浏览器数据后设备身份会丢失。本设计同时解决设备识别的健壮性和多账户绑定两个问题。

### 当前问题

**设备识别健壮性不足：**
- 当前方案仅 cookie + localStorage 两层。用户"清除浏览器数据"（不需要清全部，很多用户习惯性清 cookie）就会丢失 device_id
- 丢失后设备变成"新设备"，之前的绑定全部失效
- 家庭场景中共用设备（iPad、家庭电脑）被家长/孩子清理浏览器后频繁出现此问题

**多账户绑定缺失：**

现有 `/auth/device/check` 只返回单个用户（`.first()`）。家庭场景下，同一台设备（如家里的 iPad）可能有多个家庭成员使用。需要支持：
1. 同一设备绑定多个账户（最多6个）
2. 登录时展示已绑定账户列表，用户点击头像进入二阶段
3. 未绑定设备或选择"其他账户登录"时走传统用户名/密码路径
4. **所有一阶段路径均需 ALTCHA 验证码**

## 目标与非目标

**目标：**
- 同一 device_id 关联多个用户的 device_sessions，登录时展示所有已绑定用户
- 用户选择已知账户 + 通过验证码后直接进入二阶段 PIN
- 上限6个绑定账户，超过时最早绑定的不再展示（仍可通过"其他账户"路径登录）
- 保持安全性：验证码防爬，rate limit 防扫描

**非目标：**
- 不改变二阶段逻辑（已完善）
- 不改变设备信任/撤销管理
- 不使用 FingerprintJS 作为设备识别主键或恢复信号（误判率30-40%，不适合家庭财务场景）
- 不做跨浏览器/跨 origin 设备识别（浏览器安全模型限制）

## 设计

### Part A: 设备识别健壮性增强

#### 方案分析

| 方案 | 稳定性 | 抗清除能力 | 适用场景 |
|------|--------|-----------|----------|
| FingerprintJS (已废弃) | 差（跨时间漂移） | 好（重算即可） | 仅适合风控辅助信号 |
| cookie + localStorage (当前) | 好（值不变） | 差（清cookie即丢） | 用户不清数据时100%可靠 |
| + IndexedDB | 好 | 中（很少单独清IDB） | 覆盖大部分清cookie场景 |
| + ETag | 好 | 好（存HTTP缓存） | 覆盖"清cookie但未清缓存"场景 |

**结论：** 采用 cookie + localStorage + IndexedDB + ETag 四层持久化。

#### 设备身份持久化层级

```
读取优先级（从高到低）:
1. cookie (numina_device_id) — 最快，服务端可直接读
2. localStorage (_numina_device_id) — cookie 丢失时的第一兜底
3. IndexedDB (numina_device_store.device_id) — 清cookie+localStorage后的兜底
4. ETag (/api/v1/auth/device-ping 响应的 If-None-Match) — 清所有JS存储后的最后兜底

写入时机（信任设备时全部写入）:
- 后端 Set-Cookie → cookie
- 前端 writeDeviceId() → localStorage + IndexedDB
- 后端 /auth/device-ping ETag → HTTP 缓存
```

#### 前端 deviceIdentity.ts 改造

```typescript
// frontend/packages/auth/src/utils/deviceIdentity.ts

const COOKIE_NAME = 'numina_device_id'
const LS_KEY = '_numina_device_id'
const IDB_STORE = 'numina_device_store'
const IDB_KEY = 'device_id'

export async function readDeviceId(): Promise<string | null> {
  // Layer 1: cookie
  const match = document.cookie.match(/(?:^|; )numina_device_id=([^;]+)/)
  if (match) {
    const value = decodeURIComponent(match[1])
    // 回填下层
    localStorage.setItem(LS_KEY, value)
    writeToIdb(value)
    return value
  }

  // Layer 2: localStorage
  const lsValue = localStorage.getItem(LS_KEY)
  if (lsValue) {
    writeToIdb(lsValue)
    return lsValue
  }

  // Layer 3: IndexedDB
  const idbValue = await readFromIdb()
  if (idbValue) {
    localStorage.setItem(LS_KEY, idbValue)
    return idbValue
  }

  // Layer 4: ETag — 通过发请求触发，后端检查 If-None-Match
  // 由调用方在 API 层处理（见 device-ping 端点设计）
  return null
}

export async function writeDeviceId(deviceId: string): Promise<void> {
  localStorage.setItem(LS_KEY, deviceId)
  await writeToIdb(deviceId)
}

export function clearDeviceId(): void {
  localStorage.removeItem(LS_KEY)
  document.cookie = `${COOKIE_NAME}=; Path=/; Max-Age=0`
  clearIdb()
}

// IndexedDB helpers
function openIdb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(IDB_STORE, 1)
    req.onupgradeneeded = () => {
      req.result.createObjectStore('kv')
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

async function readFromIdb(): Promise<string | null> {
  try {
    const db = await openIdb()
    return new Promise((resolve) => {
      const tx = db.transaction('kv', 'readonly')
      const req = tx.objectStore('kv').get(IDB_KEY)
      req.onsuccess = () => resolve(req.result ?? null)
      req.onerror = () => resolve(null)
    })
  } catch {
    return null
  }
}

async function writeToIdb(value: string): Promise<void> {
  try {
    const db = await openIdb()
    const tx = db.transaction('kv', 'readwrite')
    tx.objectStore('kv').put(value, IDB_KEY)
  } catch {
    // IndexedDB 不可用时静默忽略
  }
}

async function clearIdb(): Promise<void> {
  try {
    const db = await openIdb()
    const tx = db.transaction('kv', 'readwrite')
    tx.objectStore('kv').delete(IDB_KEY)
  } catch {}
}
```

**注意：** `readDeviceId()` 变为 async（返回 Promise），调用方需要 await。

#### ETag 持久化端点（后端新增）

```python
# 新增端点 GET /api/v1/auth/device-ping
# 无需认证，用于 ETag 持久化

@router.get("/device-ping", include_in_schema=False)
def device_ping(request: Request, response: Response):
    """ETag-based device identity persistence.

    On first call after trust: returns ETag with device_id.
    On subsequent calls: browser sends If-None-Match with stored device_id.
    If JS storage is lost, this endpoint recovers the device_id from HTTP cache.
    """
    if_none_match = request.headers.get("if-none-match")
    if if_none_match:
        # 浏览器缓存中还有 device_id — 返回 304 + device_id in body for recovery
        device_id = if_none_match.strip('"')
        response.headers["ETag"] = f'"{device_id}"'
        response.headers["Cache-Control"] = "private, max-age=2592000"  # 30天
        return {"device_id": device_id}

    # 无 ETag — 纯新设备，返回空
    response.headers["Cache-Control"] = "no-store"
    return {"device_id": None}
```

**前端 ETag 恢复逻辑（在 readDeviceId 返回 null 后调用）：**

```typescript
export async function recoverFromEtag(): Promise<string | null> {
  try {
    const resp = await fetch('/api/v1/auth/device-ping', { credentials: 'same-origin' })
    const data = await resp.json()
    if (data.device_id) {
      await writeDeviceId(data.device_id)
      return data.device_id
    }
    return null
  } catch {
    return null
  }
}
```

#### 设备身份写入时机

在用户点击"信任此设备"时，`POST /auth/device/trust` 响应处理中：

```typescript
// auth store trustDevice 改造
async function trustDevice() {
  const deviceId = await readDeviceId()
  const { data } = await getHttp().post('/auth/device/trust', { device_id: deviceId })
  // 写入所有层
  await writeDeviceId(data.device_id)  // localStorage + IndexedDB
  // cookie 由后端 Set-Cookie 处理
  // ETag 通过下一次 device-ping 请求自动建立
  await fetch('/api/v1/auth/device-ping', {
    credentials: 'same-origin',
    headers: { 'If-None-Match': `"${data.device_id}"` }
  })
}
```

#### FingerprintJS 定位

- **不再用于设备识别**
- **保留为风控辅助信号**：未来可在 trust 时存储指纹到 `browser_fingerprint` 列，在可疑操作时比对
- `fingerprint.ts` 保持 DEPRECATED 状态
- `@fingerprintjs/fingerprintjs` 依赖可后续清理

---

### Part B: 多账户设备绑定

### 登录流程状态机

```
页面加载
  │
  ├── await readDeviceId() == null
  │     └── await recoverFromEtag() == null ──→ [Step 1: 用户名/密码/验证码]
  │
  └── readDeviceId() 有值
        │
        POST /auth/device/check { device_id }
        │
        ├── users: [] (空) ──→ [Step 1: 用户名/密码/验证码]
        │
        └── users: [{...}, ...] ──→ [Step 0: 账户选择视图]
                                       │
                                       ├── 用户点击某账户头像
                                       │     └── 展示 ALTCHA 验证码
                                       │           └── 验证通过
                                       │                 └── POST /auth/device/select
                                       │                       { device_id, user_id, altcha }
                                       │                       │
                                       │                       ├── 有 second_factor → [Step 2: PIN]
                                       │                       └── 无 second_factor → 登录完成
                                       │
                                       └── 用户点击"其他账户登录"
                                             └── [Step 1: 用户名/密码/验证码]
```

### API 变更

#### POST /auth/device/check（改造）

**Request 不变：**
```json
{ "device_id": "uuid-string" }
```

**Response 变更：**
```json
{
  "trusted": true,
  "users": [
    {
      "user_id": 123456789,
      "display_name": "爸爸",
      "avatar_color": "#4ecdc4",
      "role": "owner",
      "second_factor_type": "numeric_pin",
      "last_seen_at": "2026-06-05T10:30:00Z"
    },
    {
      "user_id": 234567890,
      "display_name": "妈妈",
      "avatar_color": "#ff6b6b",
      "role": "admin",
      "second_factor_type": null,
      "last_seen_at": "2026-06-04T08:15:00Z"
    },
    {
      "user_id": 345678901,
      "display_name": "小明",
      "avatar_color": "#6bcb77",
      "role": "child",
      "second_factor_type": "emoji_pin",
      "last_seen_at": "2026-06-03T16:45:00Z"
    }
  ]
}
```

当 `trusted: false` 时 `users` 为空数组。

**逻辑变更：**
- 查询 `device_sessions` 中所有匹配 `device_id` 且活跃（非 revoked、未过期）的 session
- JOIN `users` 表获取 display_name、avatar_color、role、second_factor 信息
- 按 `last_seen_at` 降序排列，最多返回6条
- **不再返回 temp_token**（安全考虑：不能在无验证码的情况下发 token）

#### POST /auth/device/select（新增）

无需认证（登录前调用），需 rate limit（同 `/device/check`，20/min per IP）。

**Request：**
```json
{
  "device_id": "uuid-string",
  "user_id": "123456789",
  "altcha": "captcha-payload-string"
}
```

**Response（成功，需二阶段）：**
```json
{
  "second_factor_required": true,
  "temp_token": "jwt-temp-token",
  "second_factor_type": "numeric_pin",
  "display_name": "爸爸",
  "avatar_color": "#4ecdc4"
}
```

**Response（成功，无需二阶段 — 管理员/大人未绑定 PIN）：**
直接设置 auth cookies（access + refresh），返回：
```json
{
  "second_factor_required": false
}
```

**验证逻辑：**
1. 验证 ALTCHA captcha
2. 验证 device_id + user_id 对应一个活跃的 device_session
3. 验证 user 状态为 active
4. 刷新 session 的 last_seen_at
5. 根据用户二阶段配置返回 temp_token 或直接签发 tokens

**错误码：**
- `CAPTCHA_INVALID` — 验证码无效
- `AUTH_DEVICE_NOT_FOUND` — device_id + user_id 组合不存在活跃 session
- `AUTH_USER_DISABLED` — 用户被禁用
- `RATE_LIMITED` — 超出频率限制

### Schema 变更

```python
# server/apps/backend/app/schemas/device.py

class DeviceCheckUserItem(SnowflakeBase):
    user_id: int
    display_name: str
    avatar_color: str
    role: str
    second_factor_type: str | None
    last_seen_at: datetime

class DeviceCheckResponse(BaseModel):
    trusted: bool
    users: list[DeviceCheckUserItem] = []

class DeviceSelectRequest(BaseModel):
    device_id: str
    user_id: str  # 前端传字符串，后端 int() 转换
    altcha: str

class DeviceSelectResponse(BaseModel):
    second_factor_required: bool
    temp_token: str | None = None
    second_factor_type: str | None = None
    display_name: str | None = None
    avatar_color: str | None = None
```

### 前端变更

#### LoginPage.vue 状态扩展

```typescript
// 新增 step 值: 0 = 账户选择, 1 = 用户名密码, 2 = PIN
const step = ref<0 | 1 | 2>(1)

interface BoundUser {
  userId: string
  displayName: string
  avatarColor: string
  role: string
  secondFactorType: string | null
}
const boundUsers = ref<BoundUser[]>([])
const selectedUser = ref<BoundUser | null>(null)
```

#### onMounted 逻辑

```typescript
onMounted(async () => {
  let deviceId = await readDeviceId()

  // Layer 4: ETag recovery
  if (!deviceId) {
    deviceId = await recoverFromEtag()
  }

  if (!deviceId) return  // 无 device_id，保持 step=1

  try {
    const { data } = await checkDevice(deviceId)
    if (data.trusted && data.users.length > 0) {
      boundUsers.value = data.users.map(u => ({
        userId: String(u.user_id),
        displayName: u.display_name,
        avatarColor: u.avatar_color,
        role: u.role,
        secondFactorType: u.second_factor_type,
      }))
      step.value = 0  // 进入账户选择视图
    }
  } catch {
    // 非致命错误，保持 step=1
  }
})
```

#### Step 0 视图（账户选择）

- 显示 Numina logo + 副标题（同 step 1）
- **横向滑动卡片** — 账户卡片横向排列，左右滑动切换（Swiper 风格）
  - 每张卡片：圆形头像（首字母 + avatar_color）+ display_name + role 标签
  - 最后一张固定卡片："其他账户登录"（带 + 图标），点击切换到 step 1
  - 最多 6 张账户卡片 + 1 张"其他账户"卡片 = 最多7张
  - 当前焦点卡片居中放大，两侧卡片缩小露出边缘（暗示可滑动）
  - 底部圆点指示器显示当前位置
  - 支持手势滑动 + 点击切换
- 用户点击某账户卡片后：
  - `selectedUser.value = user`
  - 卡片下方展开 ALTCHA 验证码区域（带过渡动画）
  - 验证码通过后自动调用 `/auth/device/select`
  - 根据响应进入 step 2 或直接登录完成

**实现方案：** 使用 Vant 4 的 `<van-swipe>` 组件（项目已引入 Vant），无需额外依赖。

```vue
<!-- Step 0: 账户选择轮播 -->
<van-swipe
  :loop="false"
  :width="280"
  :show-indicators="true"
  class="account-swipe"
>
  <van-swipe-item
    v-for="user in boundUsers"
    :key="user.userId"
    @click="onSelectUser(user)"
  >
    <div class="account-card" :class="{ selected: selectedUser?.userId === user.userId }">
      <div class="account-avatar" :style="{ background: user.avatarColor }">
        {{ user.displayName.charAt(0) }}
      </div>
      <p class="account-name">{{ user.displayName }}</p>
      <span class="account-role">{{ t(`role.${user.role}`) }}</span>
    </div>
  </van-swipe-item>

  <!-- 固定尾部卡片: 其他账户登录 -->
  <van-swipe-item @click="switchToStep1">
    <div class="account-card account-card--other">
      <div class="account-avatar account-avatar--add">+</div>
      <p class="account-name">{{ t('login.otherAccount') }}</p>
    </div>
  </van-swipe-item>
</van-swipe>
```

**视觉规格（遵循 DESIGN.md）：**
- 卡片背景：`rgba(255, 255, 255, 0.06)` + `backdrop-filter: blur(16px)`（玻璃态，同 step 1 输入框）
- 卡片边框：`2px solid rgba(189, 187, 255, 0.35)`
- 选中态：边框高亮 `#bdbbff` + 外发光 `box-shadow: 0 0 20px rgba(189, 187, 255, 0.4)`
- 头像圆形 64px，字号 24px 白色粗体
- 卡片宽度 240px，高度 auto（约160px），圆角 8px
- 指示器颜色：活跃 `#bdbbff`，非活跃 `rgba(189, 187, 255, 0.3)`

#### API 模块

```typescript
// frontend/apps/main/src/api/device.ts

export interface DeviceCheckUser {
  user_id: string
  display_name: string
  avatar_color: string
  role: string
  second_factor_type: string | null
  last_seen_at: string
}

export interface DeviceCheckResponse {
  trusted: boolean
  users: DeviceCheckUser[]
}

export interface DeviceSelectResponse {
  second_factor_required: boolean
  temp_token?: string
  second_factor_type?: string
  display_name?: string
  avatar_color?: string
}

export function checkDevice(deviceId: string) {
  return http.post<DeviceCheckResponse>('/auth/device/check', { device_id: deviceId })
}

export function selectDeviceUser(deviceId: string, userId: string, altcha: string) {
  return http.post<DeviceSelectResponse>('/auth/device/select', {
    device_id: deviceId,
    user_id: userId,
    altcha,
  })
}
```

### 数据库

**不需要 migration。** 现有 `device_sessions` 表已经支持同一 device_id 对应多个 user_id：
- unique index 是 `(user_id, device_id) WHERE is_revoked = FALSE`
- 不同 user_id + 相同 device_id 各自有独立行

只需确认：每个家庭成员分别在该设备上登录并"信任此设备"后，会各自创建自己的 device_session 行（device_id 相同），这已经是当前 `trust_or_reuse_device` 的正确行为。

### 安全考量

| 风险 | 缓解措施 |
|------|----------|
| `/device/check` 暴露用户列表 | 仅返回 display_name + avatar_color，不暴露 username/email；需要持有有效 device_id（UUID，不可猜测） |
| `/device/select` 可能被用于验证 user_id 存在 | Rate limit 20/min per IP + ALTCHA 验证码 |
| 验证码绕过 | ALTCHA 后端校验，无效直接拒绝 |
| device_id 被盗取 | device_id 本身不足以登录（仍需 PIN 或无 PIN 时仍需 captcha），且 30 天自动过期 |

### 6账户上限逻辑

- 后端查询时 `.limit(6)` 截断
- 不阻止第7个用户"信任此设备"（device_session 仍正常创建），只是 `/device/check` 展示时按 last_seen_at 取最近6个
- 被截断的用户仍可通过"其他账户登录"进入

### 设备绑定过期机制

**需求：** 设备绑定有有效期，如果某用户在该设备上超过 N 天未登录，绑定自动失效。N 通过 `.env` 配置。

**当前状态：** device_session 有 `expires_at` 字段（固定30天），但该值在每次 `trust_or_reuse_device` 时被滚动续期（`last_seen_at` 和 `expires_at` 同时刷新）。问题是 `expires_at` 是从"最后一次主动信任/刷新"算起的绝对值，不是从"最后一次使用该设备登录"算起。

**改造方案：**

1. **新增配置项 `DEVICE_TRUST_EXPIRE_DAYS`：**

```python
# server/packages/core/settings.py
class Settings(BaseSettings):
    ...
    DEVICE_TRUST_EXPIRE_DAYS: int = 30  # 设备信任有效期（天），从最后一次登录算起
```

`.env` 中可覆盖：`DEVICE_TRUST_EXPIRE_DAYS=30`

2. **消除硬编码 `timedelta(days=30)`：**

`server/apps/backend/app/services/device.py` 中所有 `timedelta(days=30)` 替换为 `timedelta(days=settings.DEVICE_TRUST_EXPIRE_DAYS)`。

3. **过期语义基于 `last_seen_at`：**

当前逻辑已经正确：
- `trust_or_reuse_device` 在复用时刷新 `last_seen_at` 和 `expires_at`
- `/auth/device/check` 查询 `expires_at > now` 过滤
- `cleanup_expired_device_sessions` 定期清理过期 session

但 `last_seen_at` 只在以下时机更新：
- 调用 `trust_or_reuse_device`（用户点"信任设备"）
- 调用 `rotate_device_session_jti`（token refresh）

**需要补充的更新时机：**
- `/auth/device/select` 成功时（用户通过绑定设备登录）— 刷新 `last_seen_at` + `expires_at`

这样，只要用户每30天内至少登录一次该设备，绑定就不会过期。超过30天未登录则自动失效。

4. **前端提示已过期的绑定：**

如果 `/auth/device/check` 返回 `users: []`（所有绑定都过期了），前端直接展示 step 1。不需要特殊提示——用户重新登录 + 重新信任设备即可恢复绑定。

**Cookie 和 ETag 的 max-age 同步：**
- `numina_device_id` cookie 的 `max_age` 也改为 `settings.DEVICE_TRUST_EXPIRE_DAYS * 24 * 3600`
- ETag 的 `Cache-Control: max-age` 同步调整

## 测试

### 设备识别健壮性

1. **readDeviceId 层级回退** — cookie 有值直接返回；cookie 无、localStorage 有 → 返回 + 回填；都没有 → 读 IndexedDB；都没有 → 调 ETag recovery
2. **writeDeviceId 全写** — 同时写入 localStorage + IndexedDB
3. **ETag recovery** — 模拟清除 cookie+localStorage+IndexedDB 后，device-ping 返回缓存的 device_id
4. **clearDeviceId** — 清除所有三层存储
5. **IndexedDB 不可用降级** — IndexedDB 被禁用时静默跳过，不影响其他层

### 多账户绑定后端

1. `/device/check` 对有多个绑定用户的 device_id → 返回 users 列表
2. `/device/check` 对无绑定的 device_id → `trusted: false, users: []`
3. `/device/check` 对超过6个绑定的 device_id → 只返回6个（按 last_seen_at 降序）
4. `/device/select` 正常流程 → temp_token（有 PIN）/ 直接登录（无 PIN）
5. `/device/select` 验证码无效 → CAPTCHA_INVALID
6. `/device/select` device_id + user_id 不匹配 → AUTH_DEVICE_NOT_FOUND
7. `/device/select` rate limit → RATE_LIMITED
8. `/device/select` 成功后 session 的 `last_seen_at` 和 `expires_at` 已刷新

### 设备绑定过期

1. **过期自动失效** — session 超过 `DEVICE_TRUST_EXPIRE_DAYS` 未登录 → `/device/check` 不返回该用户
2. **登录续期** — `/device/select` 成功后 `expires_at` 被刷新为 now + N 天
3. **配置生效** — 修改 `DEVICE_TRUST_EXPIRE_DAYS` 后新创建/刷新的 session 使用新值
4. **Cookie max-age 同步** — `numina_device_id` cookie 有效期与配置一致

### 前端

1. 无 device_id → 直接展示 step 1
2. 有 device_id 但无绑定 → 展示 step 1
3. 有 device_id 且有绑定 → 展示 step 0 账户列表
4. 点击账户 → 展示验证码 → 通过后进入 step 2
5. 点击"其他账户" → 展示 step 1
6. 多个账户正确排列（最近使用的在前）

## 向后兼容性

`/auth/device/check` 响应结构改变（从返回单用户字段变为 `users` 数组），这是**破坏性变更**。

影响范围：
- `frontend/apps/main/src/pages/LoginPage.vue` — 需要更新 onMounted 逻辑
- `frontend/apps/main/src/api/device.ts` — DeviceCheckResponse 类型变更
- `frontend/apps/child/` — child 应用暂不使用 device/check（child 使用独立的 WebAuthn/emoji 入口）

**无需数据迁移**，只是 API 响应格式变更 + 新增端点。

## 实施顺序

**Phase 1: 设备识别健壮性增强**
1. 前端 `deviceIdentity.ts` 改造 — 加入 IndexedDB 读写 + readDeviceId 变 async
2. 后端新增 `GET /auth/device-ping` ETag 端点
3. 前端新增 `recoverFromEtag()` + 信任设备时写入 ETag
4. 更新 LoginPage.vue 中 `onMounted` 为 async 调用
5. 单元测试覆盖4层读写和降级

**Phase 2: 多账户绑定**
1. 后端配置 — `settings.py` 新增 `DEVICE_TRUST_EXPIRE_DAYS`，替换 `device.py` 中所有硬编码 `timedelta(days=30)`
2. 后端 schemas — 新增 `DeviceCheckUserItem`、`DeviceSelectRequest/Response`，修改 `DeviceCheckResponse`
3. 后端 router — 改造 `check_device` 逻辑（查多用户），新增 `select_device` 端点（含 last_seen_at 续期）
4. 后端 cookie — `numina_device_id` 的 `max_age` 改为读取配置值
5. 后端 tests — 覆盖8个功能用例 + 4个过期用例
6. 前端 api — 更新 `device.ts` 类型和函数
7. 前端 LoginPage — 新增 step 0 横向滑动卡片视图（van-swipe）、ALTCHA 集成
8. 前端 i18n — 新增相关文案（`login.otherAccount`、`role.*` 等）
9. 端到端验证

## Trade-off

**设备识别方案选择：**
- **为什么不用 FingerprintJS** — 开源版 visitorId 跨时间不稳定（实测同一Mac累积15个重复session），误判率30-40%不适合家庭财务场景
- **为什么不做指纹恢复** — UUID丢失时指纹已漂移，恢复准确率低；且错误恢复（把设备A认成设备B）会暴露其他用户的账户列表
- **四层存储的取舍** — IndexedDB+ETag 增加约50行前端代码和1个后端端点，换来覆盖80%+的"用户清cookie"场景。用户清全部浏览器数据（包括缓存）时仍会丢失，这是可接受的安全行为
- **ETag 的局限** — 用户"清除所有浏览数据"（包括缓存）时 ETag 也会丢失。但实际中大部分用户只清 cookie 不清缓存

**多账户绑定：**
- **验证码在所有一阶段路径** — 用户体验略有摩擦，但防止了 device_id 泄露后的无门槛访问
- **不阻止第7+绑定** — 避免复杂的"解绑"逻辑，只是展示时截断
- **API 破坏性变更** — 因为前后端同仓库、同时部署，可以接受
