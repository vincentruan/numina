# Spec: 统一账户体系 + 双重验证重构

## Objective

重构 Numina 认证系统，实现儿童和大人统一的两阶段认证架构：

**第一阶段（身份验证）：** 账户 + 密码（所有用户统一）
**第二阶段（设备验证）：** 差异化 PIN 验证（父母数字PIN，儿童emoji PIN，未来可扩展）

**核心用户故事：**

- 作为父母，我可以用账户+密码登录，然后用数字PIN完成二级验证
- 作为儿童，我可以用账户+密码登录，然后用emoji PIN完成二级验证
- 作为父母，我可以为儿童设置初始密码和PIN，儿童也可以自行修改
- 作为家庭管理员，我可以在成员管理页面添加成人或儿童成员
- 作为任何用户，我可以通过邀请码自行加入家庭（包括儿童）
- 作为任何用户，在已信任设备上，我可以跳过账户密码直接进入二级验证
- 作为任何用户，首次在新设备登录后，系统提示我登记该设备

**成功标准：**

- [ ] 儿童账户有 `password_hash` 字段，可用账户+密码完成第一阶段登录
- [ ] 父母有数字PIN字段，可完成二级验证（未设置时每次必须验密码）
- [ ] `DeviceSession` 增加浏览器指纹字段，信任设备时记录指纹
- [ ] 已信任设备访问登录页，前端检测到设备信任状态，跳过第一阶段
- [ ] 新设备登录成功后，显示"登记此设备"提示
- [ ] 二级验证通过策略接口实现，支持 `numeric_pin`、`emoji_pin`，预留 `totp` 扩展点
- [ ] 儿童密码只能由父母或儿童本人修改（不能由其他家庭成员修改）
- [ ] 所有现有测试继续通过

---

## 认证流程详解

### 流程 A：首次登录（未知设备）

```
用户输入账户+密码
    ↓
后端验证第一阶段（POST /auth/login 或 /auth/child/login-password）
    ↓ 成功
返回"临时令牌"（short-lived，仅用于进入二级验证，不授予资源访问权）
    ↓
前端检查：该用户是否已设置二级验证（PIN）？
    ├── 已设置 → 进入二级验证页面
    └── 未设置 → 直接完成登录（仅密码），提示设置PIN
    ↓（已设置路径）
用户完成二级验证（POST /auth/verify-second-factor）
    ↓ 成功
颁发正式 access_token + refresh_token
    ↓
检查设备是否已信任（DeviceSession 匹配指纹）
    ├── 已信任 → 直接进入应用
    └── 未信任 → 显示"登记此设备"提示（用户可选择信任或跳过）
```

### 流程 B：已信任设备再次登录

```
用户访问登录页
    ↓
前端检测：本地是否有有效的 refresh_token + 设备指纹匹配？
    ├── 是 → 跳过账户密码，直接进入二级验证页面
    └── 否 → 走流程 A
    ↓
用户完成二级验证
    ↓ 成功
颁发新的 access_token（refresh_token 续期）
```

### 流程 C：儿童加入家庭

```
方式一（管理员添加）：
  家庭管理员在成员管理页面填写儿童信息 + 设置初始密码和PIN
      ↓
  系统创建儿童账户，归属该家庭

方式二（邀请码自行加入）：
  管理员生成家庭邀请码
      ↓
  儿童（或代为操作的父母）访问注册页，输入邀请码 + 账户信息
      ↓
  系统创建账户并绑定到该家庭
```

---

## 数据模型变更

### User 模型新增字段

```python
# 儿童账户新增
password_hash: str | None  # 儿童也有密码（父母代设）

# 父母新增（儿童已有 pin_hash）
numeric_pin_hash: str | None  # 数字PIN（4-6位），可选
numeric_pin_fail_count: int = 0
numeric_pin_locked_until: datetime | None = None

# 二级验证配置
second_factor_type: str | None  # "numeric_pin" | "emoji_pin" | "totp" | None
second_factor_enabled: bool = False  # 是否已启用二级验证
```

### DeviceSession 模型新增字段

```python
browser_fingerprint: str | None  # 浏览器指纹哈希（SHA-256）
fingerprint_components: str | None  # 指纹组成（JSON，用于调试）
```

### 新增：二级验证策略接口

```python
# backend/app/auth/second_factor.py
class SecondFactorStrategy(Protocol):
    factor_type: str
    
    def verify(self, user: User, payload: dict) -> bool: ...
    def is_configured(self, user: User) -> bool: ...

class NumericPinStrategy:
    factor_type = "numeric_pin"
    # 验证数字PIN（父母）

class EmojiPinStrategy:
    factor_type = "emoji_pin"
    # 验证emoji PIN（儿童，现有逻辑迁移）

class TotpStrategy:
    factor_type = "totp"
    # 预留，未来实现
```

---

## API 变更

### 新增端点

```
POST /auth/login/step1
  Request: { username, password, altcha? }
  Response: { temp_token, second_factor_required, second_factor_type }
  说明：第一阶段验证，返回临时令牌（5分钟有效）

POST /auth/login/step2
  Request: { temp_token, factor_type, payload }
  Response: TokenResponse（正式令牌）
  说明：第二阶段验证，payload 根据 factor_type 不同

POST /auth/child/login/step1
  Request: { username, password }
  Response: { temp_token, second_factor_required, second_factor_type }
  说明：儿童第一阶段（无 altcha）

POST /auth/device/check
  Request: { fingerprint }
  Response: { trusted, device_name, user_id? }
  说明：前端检测设备是否已信任，决定是否跳过第一阶段

POST /auth/device/trust（现有，扩展）
  Request: { device_name, fingerprint }
  说明：信任设备时同时记录指纹

POST /auth/pin/setup（父母设置数字PIN）
  Request: { pin: string }  # 4-6位数字
  Response: { success }

POST /auth/pin/change（修改PIN）
  Request: { old_pin, new_pin }
  Response: { success }

POST /auth/child/{child_id}/password（父母代设儿童密码）
  Request: { new_password }
  Response: { success }
  权限：仅家庭 owner/member（父母角色）
```

### 移除端点（首次开发阶段，无需向后兼容）

```
DELETE POST /auth/child/login          → 替换为 step1/step2 流程
DELETE GET  /auth/child/bind           → 移除（bind token 流程废弃）
DELETE GET  /auth/child/family/{id}/children → 移除
DELETE POST /auth/child/webauthn/*     → 暂移除（WebAuthn 后续单独规划）
```

### 保留端点

```
POST /auth/register       → 不变（创建家庭 + 管理员账户）
POST /auth/login          → 重构为 step1/step2 内部调用
POST /auth/family/join    → 扩展支持儿童加入
POST /auth/refresh        → 不变
POST /auth/logout         → 不变
```

---

## 前端变更

### 成人前端（frontend/apps/main）

**LoginPage.vue 改造：**
1. 页面加载时调用 `POST /auth/device/check`（传浏览器指纹）
2. 若设备已信任 → 隐藏账户密码表单，直接显示数字PIN输入
3. 若设备未信任 → 显示账户密码表单（现有逻辑）
4. 登录成功后若设备未信任 → 显示"登记此设备"底部弹窗

**新增 PinSetupPage.vue：** 引导用户设置数字PIN

**新增 NumericPinPage.vue：** 数字PIN输入（4-6位，类似手机解锁界面）

### 儿童前端（frontend/apps/child）

**ChildAuthPage.vue 改造：**
- 现有 emoji PIN 逻辑保留
- 新增：若设备未信任，登录成功后提示"设为信任设备"

**新增 ChildPasswordLoginPage.vue：** 儿童账户+密码登录页（首次或设备不信任时）

### 浏览器指纹实现

使用轻量级指纹方案（无需第三方库）：
```typescript
// frontend/packages/auth/src/utils/fingerprint.ts
async function getDeviceFingerprint(): Promise<string> {
  const components = [
    navigator.userAgent,
    navigator.language,
    screen.width + 'x' + screen.height,
    Intl.DateTimeFormat().resolvedOptions().timeZone,
    navigator.hardwareConcurrency,
  ]
  const raw = components.join('|')
  const hash = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(raw))
  return Array.from(new Uint8Array(hash)).map(b => b.toString(16).padStart(2, '0')).join('')
}
```

---

## Tech Stack

| 层 | 技术 |
|----|------|
| Backend | Python 3.11 + FastAPI + SQLAlchemy + Alembic |
| Frontend | Vue 3 + TypeScript + Vite + Vant 4 |
| Auth | JWT (httpOnly cookie) + bcrypt |
| 指纹 | Web Crypto API（原生，无第三方依赖） |

---

## Commands

```bash
# Backend 测试
cd backend && uv run pytest tests/ -v

# Backend 数据库迁移
cd backend && uv run alembic revision --autogenerate -m "add unified auth fields"
cd backend && uv run alembic upgrade head

# Frontend 类型检查
cd frontend && npm run typecheck

# 种子数据重置
bash tests/data/seed-data.sh
```

---

## Project Structure（受影响文件）

```
backend/
  app/
    models/
      user.py                    ← 新增字段（儿童password_hash，父母numeric_pin_hash）
      device_session.py          ← 新增指纹字段
      child_bind_token.py        ← 删除（bind token 废弃）
    auth/
      second_factor.py           ← 新增（策略接口）
      deps.py                    ← 新增临时令牌验证
    routers/
      auth.py                    ← 重构（step1/step2，移除child/bind端点）
      device.py                  ← 扩展 trust 端点（记录指纹）
    services/
      auth.py                    ← 重构登录逻辑
      family.py                  ← 扩展（管理员添加成员入口）
    constants/
      pin.py                     ← 新增数字PIN常量
  alembic/versions/
    xxxx_unified_auth.py         ← 新迁移文件

frontend/
  packages/auth/src/
    utils/
      fingerprint.ts             ← 新增
    stores/
      auth.ts                    ← 重构（step1/step2流程，移除bind逻辑）
      childAuth.ts               ← 重构
  apps/main/src/pages/
    LoginPage.vue                ← 改造（设备检测 + 数字PIN）
    NumericPinPage.vue           ← 新增
    PinSetupPage.vue             ← 新增
    FamilyMembersPage.vue        ← 扩展（添加成人/儿童入口）
  apps/child/src/pages/
    ChildBindPage.vue            ← 删除（bind token 废弃）
    ChildSelectPage.vue          ← 删除（合并到登录流程）
    LoginPage.vue                ← 新增（统一登录入口）
    ChildAuthPage.vue            ← 保留（emoji PIN 二级验证）

tests/data/
  seed-data.sh                   ← 更新（儿童账户密码，移除bind token数据）
```

---

## Testing Strategy

- **单元测试：** 每个 SecondFactorStrategy 实现独立测试
- **集成测试：** 完整两阶段登录流程（step1 → step2 → device check）
- **回归测试：** 现有 `/auth/login`、`/auth/child/login` 向后兼容
- **测试框架：** pytest（backend），vitest（frontend）
- **测试位置：** `backend/tests/`，`frontend/packages/auth/src/__tests__/`

---

## Boundaries

**Always:**
- 新端点遵循"无尾斜杠"规则（`@router.post("")`）
- 错误信息用中文
- 密码/PIN 用 bcrypt 存储，不明文
- 临时令牌有效期 ≤ 5 分钟
- 数字PIN锁定逻辑与emoji PIN一致（3次失败 → 15分钟锁定）

**Ask first:**
- 修改现有 `/auth/login` 端点的请求/响应结构
- 添加第三方指纹库（如 FingerprintJS）
- 修改 JWT 有效期

**Never:**
- 在响应中返回明文密码或PIN
- 跳过二级验证（即使设备已信任，二级验证仍必须完成）
- 允许非父母角色修改儿童密码

---

## Open Questions

无。所有关键决策已确认：
- 儿童有密码 ✓
- 设备信任基于 DeviceSession + 浏览器指纹 ✓
- 父母PIN可选后设 ✓
- 儿童密码由父母代设，儿童可自改 ✓

---

## 实现优先级（建议顺序）

1. **清理废弃代码**：删除 bind token 模型、路由、前端页面（ChildBindPage、ChildSelectPage）
2. **数据库迁移**：User 新增字段（儿童 password_hash，父母 numeric_pin_hash），DeviceSession 新增指纹字段
3. **后端：二级验证策略接口** + NumericPinStrategy + EmojiPinStrategy（迁移现有 emoji PIN 逻辑）
4. **后端：step1/step2 端点**（统一两阶段登录）
5. **后端：设备指纹端点**（check + trust 扩展记录指纹）
6. **后端：家庭成员管理扩展**（管理员添加成人/儿童，儿童密码代设）
7. **前端：浏览器指纹工具函数**
8. **前端：成人登录页改造**（设备检测 → 跳过第一阶段 or 数字PIN）
9. **前端：儿童前端重构**（统一登录入口，移除 bind 流程）
10. **前端：家庭成员管理页扩展**（添加成员入口）
11. **种子数据更新**（儿童账户加密码，移除 bind token 数据）
12. **回归测试**
