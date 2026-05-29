# 设备身份重构设计

**Date:** 2026-05-29
**Branch:** `deerflow-agent`
**Status:** Draft — pending user review

## 背景

家庭资产可视化系统的登录流程支持"信任此设备"。已信任的设备下次登录时，前端在 `onMounted` 调用 `/auth/device/check`，命中后端返回 `temp_token + display_name + avatar_color`，前端直接跳过 step1（用户名/密码），进入 step2（PIN）。

当前用 `browser_fingerprint`（FingerprintJS visitorId）作为"是哪台设备"的唯一识别 key。

## 问题现象

同一台 Mac 上同一个 Chrome，多次登录后被识别成多个不同设备。已登录设备列表里会持续累积重复条目。

## 实测证据（2026-05-29，demouser/DemoPass123，http://localhost）

| 信号 | 值 |
|---|---|
| `localStorage._numina_fp_fallback` | `ef22c285e68bc4ef066df77e35fe5705` |
| 同一会话内现场调 FingerprintJS | `70f0a2a5e69282e07fa7e62cf91d5753` |
| 同秒内连跑两次 FingerprintJS | 完全相同 |
| `POST /auth/device/check {fingerprint: ef22c285...}` | `trusted: true` |
| `POST /auth/device/check {fingerprint: 70f0a2a5...}` | `trusted: false` |
| `GET /auth/devices` 当前用户活跃 session 数 | 30 |
| 其中 `Mac · Chrome` | 15 条（同一台机器同一个 Chrome） |

## 根因

1. **FingerprintJS 开源版 visitorId 不是跨时间稳定的**。同秒内稳定，但跨天/跨浏览器升级/跨扩展启用状态会漂移。文档宣称的 60–80% 准确率是 Pro 版指标。
2. **localStorage 是单点冗余**。localStorage 一旦被清（用户手动清缓存、Chrome 存储配额回收、隐私模式、跨 origin），FingerprintJS 重新算出来的值大概率和原值不同。
3. **后端没有"同一设备多次登录复用同一行"的概念**。每次 `/auth/device/trust` 都写新行，30 天才自然过期。

辅因：`frontend/apps/main/src/api/device.ts:31-33` 存在一个不传 fingerprint 的孤儿 `trustDevice()`，与 `frontend/packages/auth/src/stores/auth.ts:76-86` 里传 fingerprint 的版本并存。当前未被引用，但属于死代码。

### 命名先澄清

代码里已经在用 `device_id` 这个词，但实际含义是 **session 主键**（`DeviceSession.id`，Snowflake，每次 trust 都新生成）。它从来不是"稳定的设备身份"。本设计把"会话主键"重命名为 `session_id`，把"稳定的设备身份"占用 `device_id` 这个名字。

## 目标与非目标

**目标：**
- 同一个浏览器在同一 origin 下，多次登录被识别为**同一设备**
- 设备身份不依赖 FingerprintJS 的稳定性
- "信任设备 → 跳过 step1 直接 step2"流程语义不变
- 已登录设备列表中不再因同一浏览器多次登录累积重复条目

**非目标（明确不解决，文档化 trade-off）：**
- **跨 origin 不识别为同一设备**（`http://localhost` vs `http://127.0.0.1` vs 生产域名 → 浏览器存储模型决定不同 origin 不共享 cookie/localStorage，承认这是新设备）
- **隐私模式/无痕窗口不识别为已信任**（每次新 profile，按浏览器安全模型本就是新身份）
- **用户清空 cookie + localStorage 后仍能识别**（重新进入信任流程是正确的安全行为）
- **作为风控信号的"指纹差异度"**（本次先不做，保留 `browser_fingerprint` 列供未来风控使用，但新流程不写入也不读取）

## 设计

### 数据模型

`server/packages/db/models/device_session.py` 新增 `device_id` 字段：

```python
class DeviceSession(Base):
    __tablename__ = "device_sessions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    # 会话主键。对外 API 用 session_id 这个名字。

    user_id: Mapped[int]
    family_id: Mapped[int]
    device_name: Mapped[str]
    refresh_jti: Mapped[str] = mapped_column(String(36), unique=True)

    device_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    # 稳定的设备身份（UUID v4 字符串）。
    # 应用层保证 "同 user + 活跃" 唯一，DB 层只加索引不加 unique。
    # 同一 device_id 在历史上可以有多行（revoke 后重新 trust），保留审计轨迹。

    browser_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # 保留列。本次重构不写入也不读取。未来做风控时再启用。

    created_at / last_seen_at / expires_at / is_revoked  # 不变

    __table_args__ = (
        Index("ix_device_sessions_user_active", "user_id", "is_revoked", "expires_at"),
        Index("ix_device_sessions_family", "family_id"),
        Index("ix_device_sessions_user_device", "user_id", "device_id"),  # 新增
    )
```

**约束策略**：device_id 不加 DB 唯一索引。理由：
- device_id 是身份标识不是会话主键，不应该锁死数据形态
- 同一设备 revoke 后重新 trust 应该新建一行（审计需要），但活跃唯一性由应用层保证
- 留出未来"用户主动改 device_id"等场景空间

### 应用层唯一性

`server/apps/backend/app/services/device.py` 新增：

```python
def trust_or_reuse_device(
    db: Session,
    *,
    user_id: int,
    family_id: int,
    refresh_jti: str,
    device_name: str,
    device_id: str | None,
) -> tuple[DeviceSession, bool]:
    """信任设备：若已存在同 user + device_id 的活跃 session，复用；否则新建。

    Returns (session, is_new). is_new=False 表示复用了已有 session。
    """
    now = datetime.utcnow()
    expires_at = now + timedelta(days=30)

    if device_id:
        existing = (
            db.query(DeviceSession)
            .filter(
                DeviceSession.user_id == user_id,
                DeviceSession.device_id == device_id,
                DeviceSession.is_revoked.is_(False),
                DeviceSession.expires_at > now,
            )
            .first()
        )
        if existing:
            existing.refresh_jti = refresh_jti
            existing.device_name = device_name  # UA 升级可能改名
            existing.last_seen_at = now
            existing.expires_at = expires_at
            db.commit()
            db.refresh(existing)
            return existing, False

    new_device_id = device_id or str(uuid.uuid4())
    session = DeviceSession(
        user_id=user_id,
        family_id=family_id,
        refresh_jti=refresh_jti,
        device_name=device_name,
        device_id=new_device_id,
        created_at=now,
        last_seen_at=now,
        expires_at=expires_at,
        is_revoked=False,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session, True
```

老的 `create_device_session` 保留供测试用例使用；新接口走 `trust_or_reuse_device`。

### API 契约（破坏性变更）

#### POST /auth/device/check

```diff
  Request:
- { "fingerprint": string }
+ { "device_id": string }   # 从前端 cookie/localStorage 读出来

  Response (trusted):
  {
    "trusted": true,
    "device_name": string,
    "user_id": int,
    "temp_token": string,
    "display_name": string,
    "avatar_color": string,
    "second_factor_type": string | null
  }

  Response (not trusted):
  { "trusted": false, ... }   # 所有字段 null
```

#### POST /auth/device/trust

```diff
  Request body:
- { "fingerprint": string | null }   # 旧
+ { "device_id": string | null }     # 新；首次为 null，后端生成；后续传客户端持有的值

  Response:
  {
-   "device_id": int,        # 实际是 session.id
+   "session_id": int,       # 会话主键，明确命名
+   "device_id": string,     # 设备身份；后端在响应里下发，客户端 cookie + localStorage 同时存
    "device_name": string,
    "expires_at": datetime
  }

  Set-Cookie:
+   numina_device_id=<uuid>; Path=/; Max-Age=2592000; Secure(prod only); SameSite=Lax
    # 非 httpOnly —— /device/check 在登录前调用，需要 JS 能读
```

#### GET /auth/devices

```diff
  Response list item:
  {
-   "id": int,              # 实际是 session.id
+   "session_id": int,      # 会话主键
+   "device_id": string,    # 设备身份；列表里显示同设备的多次会话历史
    "device_name": string,
    "created_at": datetime,
    "last_seen_at": datetime,
    "expires_at": datetime,
    "is_current": bool
  }
```

#### DELETE /auth/devices/{session_id}

路径参数值不变（一直是 `DeviceSession.id` 即 Snowflake 会话主键），仅参数命名从 `device_id` 改为 `session_id` 以避免与新引入的"设备身份 device_id"歧义。前端 `revokeDevice(sessionId: string)` 的传入值也来自列表项的 `session_id` 字段（原 `id`）。

### 前端

#### `frontend/packages/auth/src/utils/deviceIdentity.ts`（新文件）

```typescript
const COOKIE_NAME = 'numina_device_id'
const LS_KEY = '_numina_device_id'

export function readDeviceId(): string | null {
  // cookie 优先
  const match = document.cookie.match(/(?:^|; )numina_device_id=([^;]+)/)
  if (match) {
    const value = decodeURIComponent(match[1])
    localStorage.setItem(LS_KEY, value)  // 回填兜底
    return value
  }
  // localStorage 兜底
  return localStorage.getItem(LS_KEY)
}

export function writeDeviceId(deviceId: string): void {
  // cookie 由后端 Set-Cookie 下发；这里只更新 localStorage 兜底
  localStorage.setItem(LS_KEY, deviceId)
}

export function clearDeviceId(): void {
  localStorage.removeItem(LS_KEY)
  document.cookie = `${COOKIE_NAME}=; Path=/; Max-Age=0`
}
```

#### `frontend/packages/auth/src/utils/fingerprint.ts`

新登录/信任流程**不再调用此函数**。文件保留供未来风控用，添加 deprecation 注释。`localStorage._numina_fp_fallback` 不再读写。

#### `frontend/packages/auth/src/stores/auth.ts`

```diff
- async function trustDevice(options?: ...) {
-   const fingerprint = await getDeviceFingerprint()
-   await getHttp().post('/auth/device/trust', { fingerprint })
- }
+ async function trustDevice(options?: ...) {
+   const deviceId = readDeviceId()  // 可能为 null（首次）
+   const { data } = await getHttp().post('/auth/device/trust', { device_id: deviceId })
+   writeDeviceId(data.device_id)    // 后端返回的；cookie 也由后端 Set-Cookie
+ }
```

#### `frontend/apps/main/src/pages/LoginPage.vue`

```diff
  onMounted(async () => {
    try {
-     const fingerprint = await getDeviceFingerprint()
-     const { data } = await checkDevice(fingerprint)
+     const deviceId = readDeviceId()
+     if (!deviceId) return  // 没设备身份，直接走 step1
+     const { data } = await checkDevice(deviceId)
      if (data.trusted && data.temp_token && data.display_name && data.avatar_color) {
        ...
        step.value = 2
      }
    } catch { /* non-fatal */ }
  })
```

#### `frontend/apps/main/src/api/device.ts`

```diff
- export function checkDevice(fingerprint: string) {
-   return http.post<DeviceCheckResponse>('/auth/device/check', { fingerprint })
+ export function checkDevice(deviceId: string) {
+   return http.post<DeviceCheckResponse>('/auth/device/check', { device_id: deviceId })
  }

  // 删除孤儿
- export function trustDevice() {
-   return http.post<DeviceTrustResponse>('/auth/device/trust')
- }

  // 重命名字段
  export interface DeviceTrustResponse {
-   device_id: string    # 实际是 session.id
+   session_id: string
+   device_id: string
    device_name: string
    expires_at: string
  }
  export interface DeviceSession {
-   id: string
+   session_id: string
+   device_id: string | null
    ...
  }
  export function revokeDevice(sessionId: string) {
    return http.delete(`/auth/devices/${sessionId}`)
  }
```

`frontend/apps/child/src/api/device.ts` 做相同的对齐。

### 数据迁移

```python
# server/apps/backend/alembic/versions/XXXX_add_device_id_to_device_sessions.py

def upgrade():
    # 清空现有会话表 —— 所有用户下次 refresh 失败、自动退出、重新登录。
    # 当前测试数据场景可接受；生产环境部署前需要在变更窗口内执行。
    op.execute("DELETE FROM device_sessions")

    op.add_column(
        "device_sessions",
        sa.Column("device_id", sa.String(36), nullable=True),
    )
    op.create_index(
        "ix_device_sessions_user_device",
        "device_sessions",
        ["user_id", "device_id"],
    )

def downgrade():
    op.drop_index("ix_device_sessions_user_device", table_name="device_sessions")
    op.drop_column("device_sessions", "device_id")
```

**用户提示**：本次重构发布后，所有用户需要重新登录一次并重新选择"信任此设备"。从第二次登录开始恢复正常 trusted 体验。

### Revoke 语义

| 操作 | session 表 | device_id cookie/localStorage | 用户体验 |
|---|---|---|---|
| `DELETE /devices/{session_id}` (撤销当前会话) | 该 session 标记 revoked | 不动 | 当前 session 失效；下次登录仍走 trusted 快路（device_id 还在） |
| `DELETE /devices/{session_id}` (撤销远程其他会话) | 该 session 标记 revoked | 不动 | 远程会话失效；本地不受影响 |
| `DELETE /devices` (撤销全部) | 该 user 所有 session revoked | 不动 | 所有设备失效；但 device_id 仍可复用，下次重新登录 + trust 时复用旧 id |

**理由**：revoke 是"会话级"操作不是"设备级"操作。device_id 是设备身份，不应该因为用户清理远程会话就丢失本机的设备身份。

未来如果有"我不再信任这台设备"的场景，可以独立加 `clearDeviceId()` 调用，不耦合到 revoke。

## 测试

### 后端单元

`server/tests/backend/unit/services/test_device.py`：
- `trust_or_reuse_device` 首次（device_id=None）→ 新建 + 生成新 UUID
- `trust_or_reuse_device` 复用（已有活跃 session）→ 复用同一行，刷新 jti/last_seen/expires
- `trust_or_reuse_device` 复用（device_id 命中但 session 已 revoke）→ 新建一行（保留审计）
- `trust_or_reuse_device` 复用（device_id 命中但 session 已 expired）→ 新建一行

### 后端集成

`server/tests/backend/integration/test_device_api.py`：
- 首次 trust → 响应含新 device_id + Set-Cookie + session_id（数值）
- 带已有 device_id trust → session 表行数不变，jti/last_seen 已更新
- check 接口对未知 device_id → trusted=false
- check 接口对已 trust 的 device_id → trusted=true + temp_token

### 前端单元

`frontend/packages/auth/src/utils/deviceIdentity.test.ts`：
- readDeviceId() cookie 命中 → 返回 + 回填 localStorage
- readDeviceId() 仅 localStorage 命中 → 返回
- readDeviceId() 都没有 → null
- clearDeviceId() 清除两处

### 端到端（手动验证）

1. 全新浏览器 → /login → 提示 step1
2. 登录 → 勾选"信任此设备" → 关浏览器 → 重开 → /login → 直接 step2
3. 设备列表只有 1 条
4. 连续 3 次"登出 + 重新登录 + 信任设备" → 设备列表仍只有 1 条（验证复用而非新增）
5. 列表里 revoke 当前 → 登出 → 重新登录 → 仍跳过 step1（device_id 还在）+ 设备列表新增 1 条（revoke 后是新会话）

## Trade-off 与已知限制

- **跨 origin 不共享**：浏览器存储模型限制。`localhost` vs `127.0.0.1` vs 生产域名互不识别。这是浏览器安全模型，不再尝试用指纹绕过。
- **隐私模式/无痕窗口**：每次新身份，按设计就是不同设备。
- **用户清 cookie + localStorage**：等价于"我不再信任这台设备"，需要重新走完整流程。
- **多设备登录同一账号**：每个浏览器各自有 device_id，互不干扰。设备列表展示每台设备一行（按 device_id 复用后）。

## 实施顺序

阶段 1 — 后端：
- DeviceSession 模型加字段 + Alembic 迁移
- schemas + services 改名/新增
- routers 改 request/response，加 Set-Cookie 逻辑
- 单元 + 集成测试

阶段 2 — 前端：
- 新建 `deviceIdentity.ts`
- 改 `LoginPage.vue` + `auth.ts` + `api/device.ts`（main 和 child 两个 app）
- 删除孤儿 `trustDevice()`
- 类型/单元测试

阶段 3 — 验证：
- docker-compose down + 重建（迁移会清空 device_sessions）
- 手动跑端到端验证 5 步

实现细节进下一步 `superpowers:writing-plans` 时拆任务。
