---
title: PWA Progressive Enhancement - Plan
type: feat
date: 2026-09-08
topic: pwa-progressive-enhancement
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: ce-brainstorm
execution: code
---

## Goal Capsule

- **Objective:** Add full PWA capabilities to both Numina frontend apps (main + child) — installable home screen access, offline asset viewing with queued CRUD sync, and targeted push notifications — delivering a native-app-like experience on mobile without migrating off the existing Vue 3 + Vant 4 stack.
- **Product authority:** Mobile experience enhancement for family members accessing Numina on phones.
- **Execution profile:** Code — spans both frontend apps and backend push infrastructure.
- **Success criteria:** (1) 3 个月内移动端 session 中 ≥20% 来自已安装 PWA；(2) 离线仪表盘首次加载 < 1s（从 SW 缓存）；(3) 推送通知到达延迟 < 5s。

---

## Product Contract

### Summary

为 Numina 的 main app（80+ 路由，家长端）和 child app（~15 路由，儿童端）同时添加完整 PWA 能力：可安装到手机主屏幕的全屏体验、离线查看仪表盘和资产负债详情、离线 CRUD 操作队列（联网后自动同步）、以及三类推送通知（到期提醒、资产异常告警、家庭互动）。保持现有 Vue 3 + Vant 4 + Vite 技术栈不变，后端仅新增推送相关端点。

### Key Decisions

- **PWA 优先，不做原生 APK** (session-settled: user-directed — chosen over Capacitor/uni-app/TWA: 短期不需要应用商店分发，PWA 覆盖核心移动体验，成本最低) — Governs all requirements.
- **两个前端应用同步推进** (session-settled: user-directed — chosen over main-only or child-pilot: 两个应用的用户群都需要移动端增强) — Governs R1, R2, R9.
- **离线读 B + 写 A** (session-settled: user-directed — 仪表盘+资产负债详情离线可读；仅资产/负债 CRUD 离线可写排队) — Governs R4, R5, R6, R7.
- **推送场景 ACD** (session-settled: user-directed — 到期提醒、资产异常告警、家庭互动通知；不含 AI 任务完成通知) — Governs R10, R11, R12.
- **iOS 与 Android 对齐，接受 iOS PWA 限制** (session-settled: user-approved — 不强依赖 Background Sync，推送覆盖 iOS 16.4+，存储可能被清理) — Governs R7, R8, R13.

### Actors

- A1. **家庭成员（移动端用户）** — 通过手机浏览器或已安装的 PWA 访问 Numina，查看资产、管理财务、参与家庭互动。
- A2. **Service Worker** — 拦截网络请求，提供缓存响应，管理离线数据队列。
- A3. **推送服务** — 后端 VAPID 签名 + Web Push Protocol 向已订阅的浏览器发送通知。

### Requirements

**Installable**

- R1. 两个前端应用各自提供 `manifest.json`，声明应用名称、短名称、主题色、图标（多尺寸）、启动 URL、`display: standalone`。
- R2. Service Worker 缓存 App Shell（HTML 入口、核心 JS/CSS bundle、关键字体），使 PWA 首次加载后即可秒开。
- R3. 在合适的时机触发浏览器 `beforeinstallprompt`，引导用户"添加到主屏幕"。触发策略和频率由 planning 决定。

**Offline Read**

- R4. 仪表盘概览数据（资产总额、分配比例、近期变动）和资产/负债详情列表在离线时可查看。通过缓存关键 API 响应实现。用户登出时必须清除 SW 缓存，防止家庭共享设备上数据泄露。
- R5. 离线状态下显示缓存数据的时效标记（如"离线数据 · 缓存于 2 小时前"），让用户知道数据可能不是最新的。

**Offline Write**

- R6. 离线时允许对资产和负债执行新增、编辑、删除操作。操作存入本地队列（IndexedDB），网络恢复后按序批量提交。
- R7. 联网后自动触发同步（主机制：`online` 事件监听 + `visibilitychange` 事件触发；Background Sync API 作为 best-effort 补充，不作为主依赖）。iOS PWA 在用户打开 app 时触发同步。
- R8. 同步冲突处理：离线队列中的操作提交时，如果服务端数据已被其他设备修改，采用"服务端优先"策略，以非侵入式 toast 通知用户（如"该记录已被更新，本地修改已跳过"）。不展示 diff 面板。

**Push Notifications**

- R9. 后端实现 Web Push 基础设施：VAPID 密钥对生成、推送订阅端点（`POST /api/push/subscribe`）、订阅管理。推送订阅须绑定认证用户身份（复用现有 `sandbox_family_id` 隔离模式）。前端在用户授权后注册 Service Worker push subscription 并上报订阅信息。推送通道应作为新通道集成到现有通知系统（`notification/sender.py` 的 Telegram/Email/Feishu 通道旁），复用已有的 `NotificationChannel` 模型。
- R10. 到期/还款提醒：根据用户的租赁合同、贷款还款计划，在到期前 configurable 天数发送推送通知。
- R11. 资产异常告警：当资产总值大幅变动（阈值由 planning 定义）、预算超标、或负债比率超过设定阈值时，发送告警推送。
- R12. 家庭互动通知：孩子完成任务、获得素养徽章、达成心愿目标时，向家长端发送推送通知。child app 推送范围：接收 R10（到期提醒）和 R12（家庭互动），不接收 R11（资产异常告警）。

**Platform Parity**

- R13. 两个 app 在 Android Chrome 和 iOS Safari（16.4+）上均提供一致的 PWA 体验。iOS 不支持的能力（Background Sync、部分推送场景）降级为手动触发或静默跳过，不阻塞其他功能。
- R14. 在线/离线状态在 UI 上有明确指示：采用非侵入式方案——页面顶部轻量 banner（离线时显示，在线时隐藏）+ 导航栏图标状态变化。复用现有 `useNetwork.ts` composable 的 `isOnline` 状态。

### Key Flows

- F1. **PWA 安装流程**
  - **Trigger:** 用户第二次打开 Numina 移动端页面。
  - **Actors:** A1
  - **Steps:** 前端检测 `beforeinstallprompt` 可用 → 显示"添加到主屏幕"引导 → 用户确认 → 浏览器安装 PWA → 主屏幕出现应用图标。
  - **Outcome:** 用户可从主屏幕打开全屏应用，无浏览器 UI。

- F2. **离线操作排队与同步**
  - **Trigger:** 用户在离线状态下新增/编辑/删除资产或负债。
  - **Actors:** A1, A2
  - **Steps:** 前端将操作序列化存入 IndexedDB 队列（离线创建的记录使用客户端生成的 UUID 作为临时 ID）→ UI 标记该操作为"待同步"并乐观渲染到列表 → 网络恢复后（`online` 事件 / `visibilitychange` 触发；Background Sync 为 best-effort 补充）→ 按队列顺序逐条提交 API → 成功则从队列移除并去除"待同步"标记；冲突则 toast 通知"已被更新"；失败则标记为"同步失败"并提供重试/丢弃操作。
  - **Covers R6, R7, R8.**
  - **Outcome:** 离线操作在网络恢复后完整同步到服务端，失败操作有明确用户反馈。

- F3. **推送订阅与通知接收**
  - **Trigger:** 用户首次安装 PWA 或开启通知权限时。
  - **Actors:** A1, A3
  - **Steps:** 前端请求 Notification 权限 → 用户授权 → Service Worker 注册 push subscription → 前端将 subscription endpoint + keys 发送到后端 `POST /api/push/subscribe` → 后端存储订阅（绑定用户身份）→ 触发事件时后端通过 Web Push 协议发送通知 → 用户收到系统通知。**权限拒绝分支：** 显示一次性提示"如需提醒可在设置中开启"，app 设置页提供推送开关入口，未授权时以 app 内红点/badge 作为降级通知。
  - **Covers R9, R10, R11, R12.**
  - **Outcome:** 用户收到到期提醒、资产告警、家庭互动推送；权限拒绝时有降级路径。

### Acceptance Examples

- AE1. **主屏幕安装**
  - **Covers R1, R2, R3.**
  - **Given:** 用户在 Android Chrome 上访问 Numina。
  - **When:** 用户点击"添加到主屏幕"并完成安装。
  - **Then:** 主屏幕出现 Numina 图标；打开后全屏显示，无浏览器地址栏和工具栏；App Shell 从缓存加载，首次打开 < 1s。

- AE2. **离线查看仪表盘**
  - **Covers R4, R5.**
  - **Given:** 用户在线时已打开过仪表盘，数据已缓存。
  - **When:** 用户断网后打开 PWA。
  - **Then:** 仪表盘从缓存加载，显示资产总额和分配比例；页面顶部显示"离线数据 · 缓存于 X 分钟前"。

- AE3. **离线新增资产**
  - **Covers R6, R7, R8.**
  - **Given:** 用户在离线状态下打开 Numina。
  - **When:** 用户新增一笔资产并保存。
  - **Then:** 操作成功保存在本地队列，UI 显示"待同步"标记；恢复网络后，操作自动提交到服务端，队列清空，"待同步"标记消失。

- AE4. **收到还款提醒推送**
  - **Covers R9, R10.**
  - **Given:** 用户有一笔租赁合同 3 天后到期，已开启推送通知。
  - **When:** 到期前 3 天的预设时间。
  - **Then:** 用户手机收到系统通知："租赁合同'XX公寓'将在 3 天后到期"；点击通知打开 PWA 跳转到合同详情。

### Scope Boundaries

**Deferred for later:**
- Android APK 打包（Capacitor / TWA）— 短期不做，视 PWA 采用率再决定。
- AI 功能离线化（AI 对话、报告生成、财务教练）— 依赖网络，不在本阶段范围内。
- 微信小程序 / 支付宝小程序 — uni-app 迁移路线已否决。

**Outside this product's identity:**
- uni-app 全量迁移 — 3,600+ Vant 引用迁移成本过高，投入产出比不合理。
- iOS / Android 原生组件（相机、NFC、蓝牙）— PWA 无法覆盖，Numina 当前场景不需要。

### Dependencies / Assumptions

- **Cookie 鉴权 PWA standalone 验证（前置 spike）：** 在实现前须验证 httpOnly Cookie 鉴权在 iOS Safari 16.4+ 和 Android Chrome PWA standalone 模式下正常工作。若验证失败，需切换为 token-based 鉴权方案后再推进 R4-R12。
- **现有通知系统集成：** 项目已有 Telegram/Email/Feishu 通知通道（`notification/sender.py`、`NotificationChannel` 模型）。Web Push 应作为新通道集成到现有系统，复用 `NotificationSubscription` 模型和分发逻辑，而非从零构建。
- **推送触发机制：** R10（到期提醒）和 R11（资产异常告警）的触发评估由 `scheduler_worker` 定时任务驱动（扫描到期合同、计算资产变动），具体扫描间隔和阈值由 planning 定义。
- **IndexedDB 可用性：** 离线操作队列依赖 IndexedDB，所有目标浏览器（Chrome 75+, Safari 13+）均支持。
- **Web Push API 覆盖：** Android Chrome 完整支持；iOS Safari 16.4+ 支持但需用户从 Safari 安装 PWA 后才能授权推送。
- **Service Worker HTTPS 要求：** PWA 需要 HTTPS 环境（开发环境 localhost 例外）。现有 Nginx 生产环境已配置 HTTPS（Cloudflare Origin CA）。

### Outstanding Questions

**Deferred to Planning:**
- "添加到主屏幕"的具体触发时机和频率策略。
- 离线缓存的数据范围精确列表（哪些 API 端点的响应需要缓存）和缓存过期策略。
- 推送通知的具体触发阈值（资产变动百分比、预算超标比例、到期提前天数等）。
- Service Worker 更新策略（等待用户下次访问 vs 强制刷新）。
- IndexedDB 离线队列的加密策略（Web Crypto API per-session key vs 依赖设备级加密）。
- VAPID 密钥存储位置和轮换流程。
- 推送订阅生命周期管理（过期重订阅、多设备去重、stale subscription 清理）。
- 推送通知内容策略（锁屏通知是否包含敏感金融数据，还是仅显示通用提醒）。
- 离线队列 TTL（最大离线时长、自动过期策略）。
- 两个 app 的 PWA 基础设施是否提取为共享包（`@numina/pwa`）。

---

## Planning Contract

### Key Technical Decisions

KTD1. **vite-plugin-pwa 作为 PWA 构建工具** — 两个 app 的 Vite 构建均集成 `vite-plugin-pwa`，自动生成 `manifest.json` 和管理 SW 预缓存列表。避免手写 SW 注册和 manifest 维护。

KTD2. **Web Push 集成到现有通知系统** — 新增 `channel_type = "web_push"` 到 `NotificationChannel` 模型，在 `sender.py` 添加 `send_webpush()` 方法，在 `dispatcher.py` 的 `_dispatch_notifications` 中添加分支。VAPID 密钥存储在 `NotificationChannelConfig`（已有加密 K/V 存储）。复用 `reminder_job` 定时触发，不新增调度任务。

KTD3. **离线队列复用 IndexedDB 模式** — 参照 `frontend/packages/auth/src/utils/deviceIdentity.ts` 的 IDB helper 模式（`openIdb`/`readFromIdb`/`writeToIdb`/`clearIdb`），在两个 app 中各建一个 `pending-mutations` object store。离线创建记录使用客户端 UUID 作为临时 ID。

KTD4. **同步触发链：online 事件为主** — 不依赖 Background Sync API。同步触发链：`online` 事件监听（主）→ `visibilitychange` 事件（辅）→ Background Sync（best-effort）。axios response interceptor 在 network error 时将非 GET 请求序列化入队。

KTD5. **SW 缓存认证数据登出清除** — SW runtime cache 中存储的 API 响应（含金融数据）在用户登出时必须清除。通过 `auth/logout` 流程中调用 `caches.delete()` 实现。

### Product Contract Preservation

Product Contract unchanged — all R/A/F/AE IDs preserved verbatim.

---

## Implementation Units

### U1. PWA Infrastructure Foundation (Both Apps)

- **Goal:** 为两个前端应用添加 PWA 基础能力：`manifest.json`、Service Worker 注册、App Shell 预缓存、安装引导。
- **Requirements:** R1, R2, R3, R13
- **Dependencies:** none
- **Files:**
  - `frontend/apps/main/vite.config.ts` — 添加 `VitePWA` 插件
  - `frontend/apps/child/vite.config.ts` — 添加 `VitePWA` 插件
  - `frontend/apps/main/src/composables/useInstallPrompt.ts` — 新建，封装 `beforeinstallprompt` 逻辑
  - `frontend/apps/child/src/composables/useInstallPrompt.ts` — 新建，同上
  - `frontend/apps/main/src/layouts/MainLayout.vue` — 集成安装引导 UI
  - `frontend/apps/child/src/layouts/MainLayout.vue` — 集成安装引导 UI
  - `frontend/apps/main/nginx.conf` — 添加 SW 文件缓存头 + CSP `script-src 'self'`
  - `frontend/apps/child/nginx.conf` — 同上
  - `frontend/apps/main/nginx.production.conf` — 同上
  - `frontend/apps/child/nginx.production.conf` — 同上
  - `frontend/packages/assets/src/icons/` — 生成 PWA 图标（192/512/maskable）
- **Approach:**
  1. 安装 `vite-plugin-pwa` 到 `frontend/package.json`（workspace root）
  2. 在两个 `vite.config.ts` 中配置 `VitePWA` 插件：`registerType: 'prompt'`、`injectRegister: 'auto'`、`manifest` 配置（名称、主题色 `#4361ee`、`display: standalone`）、`workbox.precache` 注入
  3. 从现有图标资源（`3d-things/` 或 `cartoon-consumer/`）生成 192x192、512x512 和 maskable SVG 图标
  4. 创建 `useInstallPrompt` composable：监听 `beforeinstallprompt` 事件，提供 `canInstall` ref 和 `promptInstall()` 方法。安装引导策略：首次访问后第二次进入时显示底部 slide-up sheet，关闭后 7 天不再提示（通过 localStorage 记录关闭时间）
  5. nginx 配置：为 `/sw.js` 添加 `Cache-Control: no-cache` location block；CSP `script-src` 添加 `'self'` 以允许 SW 脚本加载
- **Patterns to follow:** `deviceIdentity.ts` 的 IDB 模式；现有 `MainLayout.vue` 的 offline banner 模式
- **Test scenarios:**
  - Covers AE1: 在 Chrome DevTools Lighthouse 中 PWA 审计通过（manifest 有效、SW 注册、App Shell 可缓存）
  - 两个 app 各自的 `manifest.json` 包含 name、short_name、icons、start_url、display
  - `beforeinstallprompt` 事件被正确捕获，`promptInstall()` 触发浏览器安装对话框
  - 安装引导关闭后 7 天内不再显示
  - nginx 返回 `/sw.js` 时包含 `Cache-Control: no-cache` 头
- **Verification:** Lighthouse PWA score ≥ 90；两个 app 均可在 Chrome "Add to Home Screen" 安装；从主屏幕打开后全屏无浏览器 UI

---

### U2. Offline Read — Service Worker Runtime Caching

- **Goal:** 仪表盘和资产/负债列表数据在离线时从 SW 缓存加载，并显示时效标记。登出时清除缓存。
- **Requirements:** R4, R5
- **Dependencies:** U1
- **Files:**
  - `frontend/apps/main/vite.config.ts` — workbox runtime caching 配置
  - `frontend/apps/child/vite.config.ts` — 同上
  - `frontend/apps/main/src/composables/useOfflineCache.ts` — 新建，缓存时效查询
  - `frontend/apps/child/src/composables/useOfflineCache.ts` — 同上
  - `frontend/apps/main/src/pages/Dashboard.vue` — 集成时效标记
  - `frontend/apps/main/src/pages/Finance.vue` — 集成时效标记
  - `frontend/apps/main/src/composables/useAuth.ts` — 登出时清除 SW 缓存
- **Approach:**
  1. 在 `vite-plugin-pwa` 的 `workbox.runtimeCaching` 中配置 stale-while-revalidate 策略，缓存以下 API 路径：
     - `/api/v1/dashboard/summary` — 仪表盘汇总
     - `/api/v1/dashboard/allocation` — 分配比例
     - `/api/v1/assets` — 资产列表
     - `/api/v1/liabilities` — 负债列表
  2. 缓存条目添加 `Date` header 标记缓存时间，`useOfflineCache` composable 从 SW `Cache` API 读取响应头中的时间戳，计算时效
  3. 离线状态下，Dashboard 和 Finance 页面顶部显示 sticky banner："离线数据 · 缓存于 X 分钟前"
  4. 首次离线（缓存未命中）显示空状态插图 + "首次使用需联网加载数据" 提示
  5. 在 `useAuth.ts` 的 logout 流程中添加 `caches.delete('workbox-runtime-caching-...')` 和 `caches.delete('workbox-precache-v2-...')`
- **Patterns to follow:** `vite-plugin-pwa` workbox 配置模式；现有 `useNetwork.ts` 的 reactive 模式
- **Test scenarios:**
  - Covers AE2: 在线加载仪表盘后断网，刷新页面，仪表盘数据从缓存加载
  - 缓存时效标记正确显示"缓存于 X 分钟前"
  - 首次离线（无缓存）显示空状态而非报错
  - 登出后 SW 缓存被清除，重新登录需重新加载数据
- **Verification:** Chrome DevTools → Application → Cache Storage 可见缓存条目；断网后仪表盘正常显示；登出后缓存清空

---

### U3. Offline Write Queue & Sync

- **Goal:** 离线时资产/负债 CRUD 操作存入 IndexedDB 队列，联网后自动同步，失败有用户反馈。
- **Requirements:** R6, R7, R8
- **Dependencies:** U1
- **Files:**
  - `frontend/packages/shared/src/utils/offlineQueue.ts` — 新建，IndexedDB 队列核心（参照 `deviceIdentity.ts` 的 IDB 模式）
  - `frontend/apps/main/src/api/index.ts` — axios interceptor 扩展：network error 时非 GET 请求入队
  - `frontend/apps/child/src/api/index.ts` — 同上
  - `frontend/apps/main/src/composables/useSyncQueue.ts` — 新建，同步触发 + 状态管理
  - `frontend/apps/child/src/composables/useSyncQueue.ts` — 同上
  - `frontend/apps/main/src/components/SyncStatus.vue` — 新建，待同步/同步中/失败状态 UI
  - `frontend/apps/child/src/components/SyncStatus.vue` — 同上
- **Approach:**
  1. `offlineQueue.ts` 实现：`openQueueDb()` 创建 `pending_mutations` store（key: timestamp+uuid, value: `{method, url, body, idempotencyKey, createdAt, status}`）；`enqueue(operation)` 序列化操作；`dequeue()` 按序取出；`remove(key)` 成功后移除；`listPending()` 返回队列内容
  2. 离线创建的记录使用 `crypto.randomUUID()` 作为客户端 ID，同步成功后替换为服务端返回的 snowflake ID
  3. axios response interceptor 扩展：在现有 network error 处理逻辑（`api/index.ts:236`）中，对非 GET 请求（POST/PATCH/DELETE）在 offline 或 network error 时调用 `enqueue()` 而非抛出错误
  4. `useSyncQueue` composable：监听 `online` 事件和 `visibilitychange`（document.visible），触发 `drain()` 方法逐条提交队列；每次提交后更新状态（pending → syncing → done/failed/conflict）
  5. 冲突处理：服务端返回 409 或数据 `updated_at` 比离线操作时间新时，移除队列条目 + toast 通知"该记录已被更新，本地修改已跳过"
  6. 失败处理：3 次重试后标记为 `failed`，`SyncStatus` 组件显示失败列表，提供"重试"和"丢弃"按钮
  7. 乐观渲染：操作入队后立即在本地 store 中更新数据（带 `pending_sync` 标记），同步成功后去除标记
- **Patterns to follow:** `deviceIdentity.ts` 的 `openIdb`/`readFromIdb`/`writeToIdb` 模式；现有 axios interceptor 的 retry-on-network-error 模式
- **Test scenarios:**
  - Covers AE3: 离线新增资产 → IndexedDB 队列有一条记录 → 恢复网络 → 队列清空 → 资产出现在列表中
  - 离线编辑后断网 → 再恢复网络 → 编辑同步到服务端
  - 离线删除 → 恢复网络 → 服务端记录被删除
  - 同步冲突（服务端数据已变更）→ toast 通知 → 本地修改被跳过
  - 同步失败（服务端 500）→ 重试 3 次 → 标记为失败 → SyncStatus 显示重试/丢弃按钮
  - 离线创建 → 离线编辑同一条记录 → 恢复网络 → create 先提交获得 server ID → edit 替换 temp ID 后提交
- **Verification:** 断网后 CRUD 操作成功入队并乐观渲染；恢复网络后队列自动清空；冲突和失败场景有明确 UI 反馈

---

### U4. Backend Web Push Infrastructure

- **Goal:** 后端支持 Web Push 通知发送：VAPID 密钥管理、推送订阅 CRUD、`send_webpush` 集成到现有通知系统。
- **Requirements:** R9
- **Dependencies:** none
- **Files:**
  - `server/apps/backend/app/services/notification/sender.py` — 添加 `send_webpush()` 方法
  - `server/apps/backend/app/services/notification/dispatcher.py` — `_dispatch_notifications` 添加 `web_push` 分支
  - `server/apps/backend/app/routers/notification_push.py` — 新建，`POST /api/v1/notifications/push/subscribe` + `DELETE`
  - `server/packages/db/models/notification_channel.py` — 添加 `web_push` channel_type 常量
  - `server/packages/db/alembic/versions/` — 新建迁移：初始化 `web_push` NotificationChannel + VAPID keys in NotificationChannelConfig
  - `server/apps/backend/app/core/config.py` — 添加 `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` 配置项（从 env 或 NotificationChannelConfig 读取）
- **Approach:**
  1. 安装 `pywebpush` 依赖到 `server/pyproject.toml`
  2. VAPID 密钥对：首次部署时通过 Alembic 迁移生成，存储在 `NotificationChannelConfig` 中（`channel_type='web_push'`, `key='vapid_private_key'` / `key='vapid_public_key'`，已有加密存储）
  3. `send_webpush(subscription_info, data, vapid_private_key, vapid_claims)` — 调用 `pywebpush.webpush()` 发送；处理 410 Gone（订阅过期 → 从 DB 删除）；返回 `bool`
  4. `dispatcher.py` 的 `_dispatch_notifications` 中添加 `elif channel.channel_type == "web_push":` 分支，查询该 channel 关联的所有 push subscription，逐条调用 `send_webpush`
  5. Push subscription 端点：`POST /api/v1/notifications/push/subscribe` 接收 `{endpoint, keys: {p256dh, auth}}`，绑定 `user_id`（从 JWT 获取），存储到新的 `PushSubscription` 表（或作为 `NotificationChannelConfig` 的 K/V 条目）
  6. 家庭隔离：push subscription 绑定 `family_id`（从 JWT `fid` claim），通知分发只发给同 family 的订阅
  7. 推送内容策略：通知 body 仅包含通用描述（"您有一条新的还款提醒"），不包含资产金额等敏感数据；详细数据在用户点击通知打开 app 后加载
- **Patterns to follow:** `send_telegram()` 的 async 模式；`_dispatch_notifications` 的 channel 分支模式；`NotificationChannelConfig` 的加密 K/V 存储模式
- **Test scenarios:**
  - VAPID 密钥对生成并存储在 NotificationChannelConfig（加密）
  - POST subscribe 端点正确绑定 user_id + family_id
  - send_webpush 成功发送通知（mock pywebpush）
  - send_webpush 收到 410 Gone 时自动删除过期订阅
  - 推送通知 body 不包含敏感金融数据
  - 跨家庭隔离：family A 的推送不会发送给 family B 的订阅
- **Verification:** `pywebpush` 集成测试通过；subscribe 端点返回 200 + 绑定用户；dispatcher 正确路由 web_push 通道

---

### U5. Frontend Push Subscription & SW Handler

- **Goal:** 前端实现推送权限请求、subscription 注册、SW push 事件处理、权限拒绝降级。
- **Requirements:** R9, R13
- **Dependencies:** U1, U4
- **Files:**
  - `frontend/apps/main/src/composables/usePushSubscription.ts` — 新建，权限请求 + subscription 管理
  - `frontend/apps/child/src/composables/usePushSubscription.ts` — 同上
  - `frontend/apps/main/public/sw-push-handler.ts` — SW push 事件处理（vite-plugin-pwa 注入）
  - `frontend/apps/child/public/sw-push-handler.ts` — 同上
  - `frontend/apps/main/src/pages/Settings.vue` — 推送开关入口
  - `frontend/apps/child/src/pages/ChildSettings.vue` — 推送开关入口
- **Approach:**
  1. `usePushSubscription` composable：
     - `requestPermission()`: 调用 `Notification.requestPermission()`；授权后调用 `registration.pushManager.subscribe()` 获取 subscription；POST 到 `/api/v1/notifications/push/subscribe`
     - `unsubscribe()`: 调用 `subscription.unsubscribe()` + DELETE 到后端
     - `permissionState`: ref 追踪当前权限状态（granted/denied/default）
     - 权限拒绝后显示一次性提示"如需提醒可在设置中开启"（localStorage 标记已显示）
  2. SW push 事件处理：在 `vite-plugin-pwa` 的 `injectManifest` 模式下，添加 `push` 事件监听器，调用 `self.registration.showNotification()` 展示通知；`notificationclick` 事件打开 PWA 并导航到对应页面
  3. Settings 页面添加"推送通知"开关，调用 `usePushSubscription` 的 grant/revoke 方法
  4. 降级方案：未授权推送时，app 内使用红点/badge 提示未读通知（后续可扩展为 app 内通知中心）
  5. iOS 特殊处理：检测 `navigator.standalone` + iOS 版本，若 iOS < 16.4 则不显示推送相关 UI
- **Patterns to follow:** `useNetwork.ts` 的 composable 模式；现有 Settings 页面的开关组件模式
- **Test scenarios:**
  - Covers F3: 用户授权推送 → subscription 成功注册到后端 → SW 能接收 push 事件
  - 用户拒绝推送 → 显示一次性提示 → Settings 页可重新开启
  - SW 收到 push 事件 → showNotification 正确展示标题和 body
  - 点击通知 → PWA 打开并导航到对应页面（如合同详情）
  - iOS < 16.4 → 推送相关 UI 不显示
  - 多设备场景：同一用户在两个设备上注册 → 两个 subscription 都存储 → 推送到达两个设备
- **Verification:** Chrome DevTools → Application → Push Messaging 可见 subscription；SW 能正确展示通知；Settings 页开关正常工作

---

### U6. Push Notification Triggers

- **Goal:** 实现三类推送通知的触发逻辑：到期提醒（R10）、资产异常告警（R11）、家庭互动（R12）。
- **Requirements:** R10, R11, R12
- **Dependencies:** U4
- **Files:**
  - `server/apps/scheduler_worker/jobs/reminder_job.py` — 扩展，添加 web_push 触发（利用现有 `run_scheduled_checks`）
  - `server/apps/backend/app/services/notification/dispatcher.py` — 添加资产异常检测逻辑
  - `server/apps/backend/app/routers/assets.py` — 资产变动时触发 R11 检测
  - `server/apps/backend/app/routers/child_tasks.py` — 孩子完成任务时触发 R12 推送
  - `server/apps/backend/app/routers/badges.py` — 徽章获得时触发 R12 推送
- **Approach:**
  1. **R10 到期提醒：** 现有 `reminder_job`（每日 09:20）已调用 `run_scheduled_checks()` → `_dispatch_notifications()`。添加 `web_push` 分支后，到期的租赁合同和贷款还款自动通过 web_push 通道分发。提醒提前天数从 `NotificationConfig` 读取（默认 3 天）
  2. **R11 资产异常告警：** 在资产 CRUD 端点（`routers/assets.py`）的 POST/PATCH/DELETE 成功后，检查资产总值变动是否超过阈值（从 `NotificationConfig.large_purchase` 读取）。超过则调用 dispatcher 发送 web_push 通知。同时在 `reminder_job` 中添加定期检查负债比率的任务
  3. **R12 家庭互动：** 在 `child_tasks.py`（任务完成）、`badges.py`（徽章获得）、`wishes.py`（心愿达成）的端点中，成功后异步调用 dispatcher 向家长端推送通知。使用 `asyncio.create_task` 不阻塞主请求
  4. child app 推送范围：child app 的 push subscription 只接收 R10 和 R12 类型的通知，不接收 R11。在 dispatcher 的 web_push 分支中根据 `reminder_type` 和订阅者角色过滤
- **Patterns to follow:** 现有 `reminder_job` 的调度模式；`_dispatch_notifications` 的分发模式；`asyncio.create_task` 的异步通知模式
- **Test scenarios:**
  - Covers AE4: 租赁合同 3 天后到期 → reminder_job 触发 → web_push 通知发送到订阅用户
  - 资产总值变动超过阈值 → 告警推送发送
  - 孩子完成任务 → 家长收到推送通知
  - 孩子获得徽章 → 家长收到推送通知
  - child app 用户只收到 R10/R12 类型通知，不收到 R11
  - 推送通知到达延迟 < 5s（从触发到用户收到）
- **Verification:** 模拟到期合同 → 推送正确发送；模拟资产大幅变动 → 告警推送发送；模拟孩子完成任务 → 家长推送发送

---

### U7. Platform Parity & Polish

- **Goal:** 确保两个 app 在 iOS/Android 上体验一致；在线/离线状态指示器；SW 更新策略。
- **Requirements:** R13, R14
- **Dependencies:** U1, U2, U3
- **Files:**
  - `frontend/apps/child/src/composables/useNetwork.ts` — 新建（从 main app 复制 + 适配）
  - `frontend/apps/child/src/layouts/MainLayout.vue` — 添加 offline banner（参照 main app）
  - `frontend/apps/main/src/composables/useNetwork.ts` — 增强：添加 `visibilitychange` 触发同步
  - `frontend/apps/child/src/composables/useNetwork.ts` — 同上
  - `frontend/apps/main/src/components/OfflineStaleness.vue` — 新建，可复用的缓存时效标记组件
  - `frontend/apps/child/src/components/OfflineStaleness.vue` — 同上
- **Approach:**
  1. 将 `useNetwork.ts` 从 main app 复制到 child app，增强为同时监听 `online`/`offline`/`visibilitychange` 事件
  2. child app 的 `MainLayout.vue` 添加与 main app 一致的 offline banner（复用样式）
  3. 创建 `OfflineStaleness.vue` 共享组件：接收 `lastSyncedAt` prop，离线时显示"离线数据 · 缓存于 X 分钟前"，在线时隐藏
  4. SW 更新策略：`vite-plugin-pwa` 配置 `registerType: 'prompt'`，SW 更新时在底部显示"有新版本可用"toast，用户点击后调用 `skipWaiting()` 激活新 SW
  5. iOS 检测：`useNetwork.ts` 中检测 `navigator.standalone`（PWA standalone 模式）和 iOS 版本，在 iOS < 16.4 时禁用推送相关功能
  6. 安全区域：两个 app 的 CSS 中添加 `env(safe-area-inset-*)` 支持，确保 standalone 模式下 notch/home indicator 不遮挡内容
- **Patterns to follow:** main app 的 offline banner 样式；Vant 组件的 toast 模式
- **Test scenarios:**
  - child app 在离线状态下正确显示 offline banner
  - OfflineStaleness 组件正确显示缓存时间
  - SW 更新后用户看到"有新版本"提示
  - iOS standalone 模式下推送权限请求正常工作（iOS 16.4+）
  - iOS < 16.4 时推送 UI 不显示
  - 两个 app 在 standalone 模式下安全区域正确（notch 不遮挡）
- **Verification:** child app offline banner 显示正常；SW 更新流程可用；iOS PWA standalone 模式体验与 Android 一致

---

## Verification Contract

| Gate | Command / Check | Applies to |
|------|----------------|------------|
| Frontend typecheck | `cd frontend && pnpm typecheck` | All units |
| Frontend lint | `cd frontend && pnpm lint` | All units |
| Backend typecheck | `cd server && make typecheck` | U4, U6 |
| Backend tests | `cd server && make test` | U4, U6 |
| Lighthouse PWA | Chrome DevTools → Lighthouse → PWA audit ≥ 90 | U1, U2 |
| Cookie auth spike | 在 iOS Safari 16.4+ 和 Android Chrome PWA standalone 中验证 httpOnly Cookie 鉴权 | U1（前置） |
| Manual E2E | 断网 → 查看仪表盘 → 新增资产 → 恢复网络 → 验证同步 | U2, U3 |
| Push E2E | 创建到期合同 → 等待 reminder_job → 验证推送到达 | U4, U5, U6 |

---

## Definition of Done

- [ ] 所有 7 个 Implementation Units 完成并通过 Verification Contract 中的对应 gates
- [ ] Cookie 鉴权 PWA standalone 前置 spike 通过（iOS Safari 16.4+ + Android Chrome）
- [ ] 两个 app 的 Lighthouse PWA score ≥ 90
- [ ] 离线仪表盘从 SW 缓存加载 < 1s
- [ ] 离线 CRUD 操作正确入队、同步、冲突处理
- [ ] 三类推送通知（到期、异常、互动）端到端可用
- [ ] iOS/Android PWA standalone 体验一致
- [ ] 无 `TODO`、`FIXME`、stub 实现或空 test 文件
