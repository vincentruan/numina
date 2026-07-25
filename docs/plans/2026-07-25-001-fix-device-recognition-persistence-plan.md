---
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: ce-brainstorm
execution: code
date: 2026-07-25
module: auth (frontend)
problem_type: bug-fix
tags: [device-trust, cookie, localStorage, persistence, dev-environment]
applies_when: trust 后关闭浏览器再打开，设备无法识别
---

# 修复设备信任持久化 — Plan

## Goal Capsule

**Objective**: 修复 "trust 后关闭浏览器再打开，设备从未成功识别" 的问题，使设备信任在 dev 和 prod 环境中均可靠持久化。

**Product authority**: 便利性优先 — 设备信任的核心价值是快速登录，不需要密码学级别安全性。

**Open blockers**: 无。

## Context

### 问题现象

- 用户在 LoginPage 完成登录 → 信任设备（trust 流程成功）
- 关闭浏览器 → 重新打开 → LoginPage 回到正常登录流程，Step 0 账户轮播从未出现
- 本地 dev 环境（Vite 5173 → proxy → backend 8000）中 100% 复现

### 根因

`numina_device_id` 的持久化**完全依赖 cookie**，存在两个脆弱点：

1. **后端 `Set-Cookie` 穿透 Vite proxy**：`device.py:151-158` 通过 `response.set_cookie()` 设置 `numina_device_id`。Vite 的 `http-proxy` 在处理 `Set-Cookie` 时有已知边界行为，cookie 可能被浏览器静默丢弃。

2. **前端 `writeDeviceId()` 只写 cookie**：`auth.ts:80` 从 trust 响应体读取 `data.device_id` 后调用 `writeDeviceId()`，但该函数只操作 `document.cookie`，没有 fallback 存储。

**核心洞察**：问题不在 ID 生成（Fingerprint.js、后台 UUID 都尝试过），而在 **ID 的持久化存储**。cookie 在 dev proxy 环境下不可靠。

### 现有架构

| 组件 | 文件 | 职责 |
|------|------|------|
| 设备 ID 存储 | `frontend/packages/auth/src/utils/deviceIdentity.ts` | cookie 读写（`numina_device_id`，90天，samesite=lax） |
| 信任流程 | `frontend/packages/auth/src/stores/auth.ts` → `trustDevice()` | 调用 `/auth/device/trust`，写回 cookie |
| 识别流程 | `frontend/apps/main/src/pages/LoginPage.vue` → `onMounted` | `readDeviceId()` → `POST /auth/device/check` → Step 0 |
| 后端信任 | `server/apps/backend/app/routers/device.py` → `trust_device()` | 创建/复用 DeviceSession，`Set-Cookie: numina_device_id` |
| 后端模型 | `server/packages/db/models/device_session.py` | `device_id` VARCHAR(36)，`browser_fingerprint` nullable |

## Requirements

### R1: 双存储写入

`deviceIdentity.ts` 的写入操作同时更新 cookie 和 localStorage。

- 写入 cookie：保留现有行为（`document.cookie`，90天 max-age，samesite=lax）
- 写入 localStorage：key 为 `numina_device_id`，值为 device_id 字符串
- 两个存储互不依赖，任一写入失败不阻塞另一个

### R2: 优先 cookie，fallback localStorage

`deviceIdentity.ts` 的读取操作优先从 cookie 读取，cookie 不存在时从 localStorage 读取。

- 读取 cookie → 有值则返回
- 读取 cookie 为 null → 读取 localStorage → 有值则返回
- 两者都为 null → 返回 null

### R3: 清除操作同步两个存储

`clearDeviceId()` 同时清除 cookie 和 localStorage。

### R4: trustDevice() 双写

`auth.ts` 的 `trustDevice()` 在调用 `writeDeviceId()` 后，同时确保 localStorage 已写入（R2 的 fallback 机制已覆盖，无需额外代码）。

### R5: 测试覆盖

`deviceIdentity.test.ts` 补充 localStorage fallback 场景：

- cookie 存在 → 返回 cookie 值
- cookie 不存在 + localStorage 有值 → 返回 localStorage 值
- 两者都不存在 → 返回 null
- `clearDeviceId()` 清除两者

## Out of Scope

- 后端 `Set-Cookie` 行为修改 — 保留现有后端逻辑，前端双存储已足够
- Fingerprint.js 或浏览器指纹方案 — 便利性优先场景下不需要
- WebAuthn 增强 — 已有独立实现（`/device/webauthn/verify`），不受本次修复影响
- child app 的 device API — `frontend/apps/child/src/api/device.ts` 使用相同 cookie 机制，本次修复自动覆盖

## Acceptance Examples

### AE1: dev 环境完整流程

1. 本地 dev 启动（Vite 5173 + backend 8000）
2. 登录 → 信任设备 → 确认 `numina_device_id` cookie 和 localStorage 均有值
3. 关闭浏览器 → 重新打开 → LoginPage Step 0 显示已信任账户
4. 点击账户 → 免密登录成功

### AE2: cookie 被清除但 localStorage 保留

1. 信任设备后，手动清除 cookie（DevTools → Application → Cookies → 删除 `numina_device_id`）
2. 刷新页面 → `readDeviceId()` 从 localStorage 读取 → Step 0 仍显示
3. 设备信任未中断

### AE3: 两个存储都被清除

1. 信任设备后，清除 cookie + localStorage
2. 刷新页面 → `readDeviceId()` 返回 null → 跳过 Step 0 → 正常登录流程
3. 这是预期行为

## Implementation Units

### U1. deviceIdentity 双存储读写 ✅ DONE

**Status**: 已完成 (commit e89ab753)

**Goal**: 修改 `deviceIdentity.ts`，写入时同时更新 cookie 和 localStorage，读取时优先 cookie、fallback localStorage，清除时同步两个存储。

**Requirements**: R1, R2, R3, R4

**Files**:
- `frontend/packages/auth/src/utils/deviceIdentity.ts` (modified)
- `frontend/packages/auth/src/utils/deviceIdentity.test.ts` (modified)

**Verification**: ✅ vitest 14 passed

---

### U2. IndexedDB 层实现

**Goal**: 增加 IndexedDB 作为第三层 fallback，在所有 JS 存储被清除时仍能恢复 device_id。

**Requirements**: R6 (IndexedDB 持久化)

**Dependencies**: U1 (cookie + localStorage 已完成)

**Files**:
- `frontend/packages/auth/src/utils/deviceIdentity.ts` (modify)
- `frontend/packages/auth/src/utils/deviceIdentity.test.ts` (modify)

**Approach**:
1. 新增 IndexedDB 工具函数：`openIdb()`, `readFromIdb()`, `writeToIdb()`, `clearIdb()`
2. DB 名称: `numina_device_store`, object store: `kv`, key: `device_id`
3. `writeDeviceId()` 增加 IndexedDB 写入（try/catch 包裹）
4. `readDeviceId()` 变为 **async**，读取链：cookie → localStorage → IndexedDB
5. 读取成功后 **backfill** 低优先级层（cookie 读到 → 写 localStorage + IndexedDB；localStorage 读到 → 写 IndexedDB）
6. `clearDeviceId()` 增加 IndexedDB 清除

**Test scenarios**:
- writeDeviceId 写入 IndexedDB（验证 DB 中有值）
- readDeviceId cookie+localStorage 都为空时从 IndexedDB 读取
- readDeviceId 从 IndexedDB 读取后 backfill localStorage
- clearDeviceId 清除 IndexedDB
- IndexedDB 不可用时（模拟 open 失败）不抛异常

---

### U3. ETag 层实现（后端端点）

**Goal**: 新增 `GET /auth/device-ping` 端点，利用 HTTP cache 的 ETag 机制实现第四层 fallback。

**Requirements**: R7 (ETag 恢复)

**Dependencies**: U2 (前端 IndexedDB 层已完成)

**Files**:
- `server/apps/backend/app/routers/device.py` (modify)
- `server/apps/backend/app/schemas/device.py` (modify)

**Approach**:
1. 新增 `GET /auth/device-ping` 端点（`include_in_schema=False`）
2. 读取 `If-None-Match` header，提取 device_id
3. 如果有 ETag：返回 200 + `{"device_id": "<id>"}` + `ETag` header + `Cache-Control: private, max-age=2592000` (30天)
4. 如果无 ETag：返回 200 + `{"device_id": null}` + `Cache-Control: no-store`
5. 端点无需认证（用于恢复流程）

**Test scenarios**:
- 请求带 `If-None-Match: "uuid"` → 返回 `{"device_id": "uuid"}`
- 请求无 `If-None-Match` → 返回 `{"device_id": null}`
- 响应包含正确的 `Cache-Control` header

---

### U4. ETag 层实现（前端 recovery）

**Goal**: 前端实现 `recoverFromEtag()` 函数，在所有 JS 存储丢失时通过 HTTP cache 恢复 device_id。

**Requirements**: R7 (ETag 恢复)

**Dependencies**: U3 (后端端点已完成)

**Files**:
- `frontend/packages/auth/src/utils/deviceIdentity.ts` (modify)
- `frontend/packages/auth/src/utils/deviceIdentity.test.ts` (modify)
- `frontend/packages/auth/src/stores/auth.ts` (modify)
- `frontend/apps/main/src/pages/LoginPage.vue` (modify)

**Approach**:
1. 新增 `recoverFromEtag()` 函数：`GET /api/v1/auth/device-ping` → 如果有 device_id → `writeDeviceId()` 写回所有层 → 返回 device_id
2. `readDeviceId()` 读取链末尾增加 ETag recovery：cookie → localStorage → IndexedDB → `recoverFromEtag()`
3. `trustDevice()` 在 trust 成功后主动调用一次 `/device-ping`（带 `If-None-Match` header）建立 ETag cache
4. `LoginPage.vue` 的 `onMounted` 和 `auth.ts` 的 `trustDevice()` 改为 await `readDeviceId()`

**Test scenarios**:
- recoverFromEtag 成功恢复 device_id 并写回所有层
- recoverFromEtag 返回 null 时不抛异常
- trustDevice 成功后建立 ETag cache

---

## Verification Contract

```bash
cd frontend/packages/auth
pnpm test:run     # deviceIdentity.test.ts 全部通过

cd server
uv run pytest apps/backend/tests/unit/services/test_device.py -v
```

**Definition of Done**:
- U1 ✅ + U2 + U3 + U4 完成
- vitest 全部通过
- backend pytest 通过
- 手动验证：dev 环境 trust → 关闭浏览器 → 重新打开 → Step 0 显示已信任账户
- 手动验证：清除 cookie + localStorage → 刷新 → IndexedDB 恢复
- 手动验证：清除所有 JS 存储 → 刷新 → ETag 恢复（需浏览器未清除 HTTP cache）
