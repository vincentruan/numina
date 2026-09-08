---
title: "feat: Manifesto Sign Flow Visualization with Vue Flow"
type: feat
date: 2026-09-08
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: ce-plan-bootstrap
execution: code
---

# 家庭约定会签流程页面改造

## Goal Capsule

- **Objective:** 改造 `/manifesto/sign` 页面，用 Vue Flow 构建纵向流程状态可视化，让用户进入页面后首先看到"当前进行到哪一步"，再查看约定内容和执行操作。
- **Authority:** 用户需求文档 31 条验收标准。以现有项目代码和数据结构为准适配。
- **Scope boundary:** 仅改造 main app 的 `ManifestoSignPage.vue`。Child app 签署页不在本次范围。不涉及流程设计器能力。

---

## Problem Frame

当前 `ManifestoSignPage.vue` 布局为：约定内容 → 签名区 → 确认按钮。用户进入后无法快速判断"当前约定处于什么状态"、"其他人签了没有"、"我需要做什么"。

改造目标：**流程状态优先** — 先展示流程进度，再展示约定内容，最后根据当前状态条件性地展示签署操作。

**核心约束：**
- 现有后端数据模型基本可用，但需要扩展 reject 机制
- `@vue-flow/core` 未安装，需要新增依赖
- 现有 `SignaturePad`、`ManifestoViewer`、`templateRegistry` 等组件直接复用
- `familyStore.members` 包含所有家庭成员（含 child role），通过 `member.role === 'child'` 区分成人/儿童
- 多轮会签通过 `ManifestoVersion.version_number` 映射

---

## Product Contract

### Requirements

**R1. 纵向流程状态可视化（Vue Flow）**

使用 Vue Flow 渲染固定的纵向流程图。节点自上而下排列，代表约定的流转阶段。Vue Flow 仅作为只读 Viewer — 禁用拖拽、连线、缩放、平移。

**R2. 当前节点视觉重点**

进入页面时，当前流程节点处于可视区域中心，视觉上最突出（边框/阴影/色块/轻微动画）。历史节点弱化处理，未来节点灰化。

**R3. 会签节点展示成员状态**

当流程处于会签阶段时，当前节点内展示所有家庭成员的会签状态：已签署/已确认/待签署/待确认/已拒绝/已过期。成人和儿童使用不同状态文案。

**R4. 当前用户"我"标识**

当前登录用户在成员列表中明确标注"我"，与其他成员明显区分。当前用户待处理时比其他成员更加突出。

**R5. 状态色块区分**

已签署/已确认：`--color-success` 正向完成状态。待签署/待确认：中性状态。已拒绝：`--color-error` 拒绝状态。已过期：警告状态。

**R6. 条件性签署操作区**

只有当前流程处于会签阶段（`signing`）且当前用户尚未签署/确认时，才展示签署操作。具体：
- 成人 + 待签署 → SignaturePad + 确认/拒绝按钮
- 成人 + 已签署 → "我 · 已签署"，不展示签名板
- 儿童 + 待确认 → 确认按钮（无签名板）
- 儿童 + 已确认 → "我 · 已确认"
- 已拒绝 → "我 · 已拒绝"，不展示操作
- 非会签节点 → 不展示任何签署操作

**R7. 流程流动动画**

使用 Vue Flow 的 `animated: true` 边属性表达当前流转方向。历史边降低动画强度。当前活跃边动画最明显。

**R8. 多轮会签展示**

通过 `version_number` 映射轮次。历史轮次简化显示（如"第一轮 · 未通过"），当前轮次完整展示。

**R9. 签署有效期**

从 `manifesto.signing_deadline` 计算剩余时间或显示"签署已结束"。过期后不允许提交签署。

**R10. 拒绝流程**

展示拒绝成员和拒绝原因。流程向"修改约定"方向展示。签名输入区消失。

**R11. 生效状态**

所有成员完成签署/确认且无拒绝 → "家庭约定已生效"。不展示任何签署操作。

**R12. 约定内容保留**

`ManifestoViewer` 继续展示约定标题和正文，位置调整到流程图下方。

**R13. 移动端体验**

320px-430px 宽度无横向滚动。Vue Flow 不干扰页面上下滚动。底部操作区不遮挡内容。iPhone Safe Area 正常。

### Scope Boundaries

**In scope:**
- `/manifesto/sign` 页面重构
- Vue Flow 安装和集成
- 后端 reject API 扩展
- 流程状态推导 composable
- 自定义 Vue Flow 节点/边组件
- 成员状态展示组件
- 条件性签署操作区
- 多轮会签历史展示

**Deferred for later:**
- Child app (`/child/manifesto/sign`) 签署页改造
- 流程设计器/BPMN
- WebSocket 实时推送签署状态
- PDF 导出

### Key Decisions

| 决策 | 选择 | 理由 |
|------|------|------|
| Vue Flow 模式 | 只读 Viewer，禁用所有编辑能力 | 需求明确不做设计器 |
| 流程状态推导 | 前端 composable 从现有 API 数据推导，不依赖新状态字段 | 最小化后端改动 |
| 多轮映射 | `version_number` = 轮次号 | 后端已有版本系统 |
| 拒绝机制 | 后端新增 reject endpoint + ManifestoRejection 模型 | 需求明确要求拒绝功能 |
| 滚动定位 | `useVueFlow().fitView()` + `panTo()` 定位当前节点 | Vue Flow 内置能力 |
| 动画策略 | `animated: true` 用于活跃边；历史边用 CSS 降低动画速度 | Vue Flow 原生支持 |
| 成员数据 | `familyStore.members` 包含所有角色，通过 `role === 'child'` 区分 | 复用现有数据 |

---

## Key Technical Decisions

**KTD1. Vue Flow 只读配置。** 全局禁用编辑能力：`nodesDraggable=false`, `nodesConnectable=false`, `elementsSelectable=false`, `zoomOnScroll=false`, `zoomOnPinch=false`, `panOnDrag=false`, `preventScrolling=true`。容器高度由节点布局决定（非固定高度），避免 Vue Flow 与页面滚动冲突。引入 `@vue-flow/core/dist/style.css` + `@vue-flow/core/dist/theme-default.css`（后者可选，主要用自定义样式）。Governs R1, R13.

**KTD2. 流程状态由前端 composable 推导。** `useManifestoFlow` 接收 `Manifesto` + `members[]` + `currentUser`，输出 `FlowState`。推导逻辑：
- `status === 'draft'` → `draft`
- `signatures.length === totalMembers` 且无拒绝 → `effective`
- `deadline` 已过 且未全部签署 → `expired`
- 有拒绝记录 → `rejected`
- 否则 → `signing`

Governs R1-R3, R6.

**KTD3. 后端新增 reject 机制。** 新增 `ManifestoRejection` 模型（`version_id`, `user_id`, `reason`, `created_at`）+ `POST /family/manifesto/reject` endpoint。`ManifestoResponse` 增加 `rejections: list[ManifestoRejectionItem]` 字段。Governs R10.

**KTD4. 自定义 Vue Flow 节点类型。** 5 种自定义节点：`flow-created`（约定创建）, `flow-signing`（会签中）, `flow-rejected`（会签未通过）, `flow-modifying`（修改中）, `flow-effective`（已生效）。每种节点有独立的视觉样式。会签节点内部嵌入成员状态列表。Governs R1-R4.

**KTD5. 纵向布局固定坐标。** 节点 position 硬编码为纵向排列：`{ x: centerX, y: index * nodeSpacing }`。不需要自动布局算法。节点数量固定（2-7 个），布局可预测。Governs R1, R2.

**KTD6. 滚动定位当前节点。** 页面加载后通过 `useVueFlow().onNodesInitialized` 或 `fitView({ nodes: [currentNodeId] })` 将当前节点居中到可视区域。设置 `padding` 使上下能看到相邻节点的一小部分。Governs R2.

**KTD7. 复用现有 SignaturePad。** 成人签署直接复用 `@/components/manifesto/SignaturePad.vue`，不重新实现。签署后调用现有 `manifestoApi.signManifesto()`。Governs R6.

**KTD8. 儿童确认操作简化。** 儿童用户（`member.role === 'child'`）不显示 SignaturePad。待确认时显示 `van-button` 确认按钮，调用 `signManifesto(null)`（signature_data 为 null = tap-to-consent）。Governs R6.

---

## High-Level Technical Design

### 页面布局层级

```
┌─────────────────────────────────┐
│ van-nav-bar (签署约定)           │
├─────────────────────────────────┤
│                                 │
│ Vue Flow 流程区域               │
│ ┌─────────────────────┐        │
│ │ ○ 家庭约定已创建     │ ← 弱化  │
│ │ │                   │        │
│ │ ↓ (animated edge)   │        │
│ │                     │        │
│ │ ● 第N轮家庭会签      │ ← 重点  │
│ │   3/4 已完成         │        │
│ │   成员状态列表       │        │
│ │   截止时间           │        │
│ │                     │        │
│ │ ↓                   │        │
│ │ ○ 家庭约定生效       │ ← 未来  │
│ └─────────────────────┘        │
│                                 │
├─────────────────────────────────┤
│ ManifestoViewer (约定内容)      │
│ 标题 + 正文                     │
├─────────────────────────────────┤
│ 操作区 (条件渲染)               │
│ - 成人待签署: SignaturePad + 按钮│
│ - 儿童待确认: 确认按钮          │
│ - 已签署/确认: "我·已签署"      │
│ - 非会签阶段: 不显示            │
└─────────────────────────────────┘
```

### 流程状态推导

```
                      ┌──────────────┐
                      │  Manifesto   │
                      │  API Data    │
                      └──────┬───────┘
                             │
                      ┌──────▼───────┐
                      │ useManifesto │
                      │ Flow()       │
                      └──────┬───────┘
                             │
            ┌────────────────┼────────────────┐
            │                │                │
     ┌──────▼──────┐  ┌─────▼──────┐  ┌──────▼──────┐
     │  flowState  │  │  members   │  │  current    │
     │  (enum)     │  │  status[]  │  │  userState  │
     └─────────────┘  └────────────┘  └─────────────┘
```

### Vue Flow 节点/边架构

```
VueFlow (viewer mode)
├── Custom Nodes (via #node-<type> slots)
│   ├── FlowCreatedNode     → 简单标签节点
│   ├── FlowSigningNode     → 复合节点（嵌入 MemberStatusList）
│   ├── FlowRejectedNode    → 带拒绝信息的节点
│   ├── FlowModifyingNode   → 修改中节点
│   └── FlowEffectiveNode   → 生效完成节点
├── Custom Edges (via #edge-<type> slots)
│   ├── AnimatedFlowEdge    → 活跃流动边（CSS dash animation）
│   └── CompletedFlowEdge   → 已完成静态边（灰色/弱化）
└── Data → computed nodes/edges from flowState + manifesto
```

---

## Implementation Units

### U1. 后端 — Reject API 扩展

**Goal:** 新增拒绝签署的后端支持，使前端能展示拒绝状态和拒绝原因。

**Requirements:** R10

**Dependencies:** None

**Files:**
- `server/apps/backend/app/models/manifesto.py` (modify — add `ManifestoRejection` model)
- `server/apps/backend/app/models/__init__.py` (modify — export new model)
- `server/apps/backend/app/schemas/manifesto.py` (modify — add reject request/response schemas)
- `server/apps/backend/app/services/manifesto_service.py` (modify — add `reject_manifesto` method)
- `server/apps/backend/app/routers/manifesto.py` (modify — add `POST /reject` endpoint)
- `server/apps/backend/app/errors/codes.py` (modify — add `MANIFESTO_ALREADY_REJECTED`)
- `server/apps/backend/app/errors/locales/zh-CN.json` (modify — add reject error messages)
- `server/apps/backend/app/errors/locales/en-US.json` (modify — add reject error messages)
- `server/apps/backend/alembic/versions/XXXX_add_manifesto_rejection.py` (new — migration)
- `tests/backend/api/test_manifesto_reject_api.py` (new)

**Approach:**
1. 新增 `ManifestoRejection` 模型：`id` (snowflake), `version_id` (BigInteger, indexed), `user_id` (BigInteger), `reason` (Text, nullable, max 2000 chars), `created_at` (UTCDateTime)。唯一约束 `(version_id, user_id)`
2. 新增 schema：`ManifestoRejectRequest(reason: str | None)`, `ManifestoRejectionItem(SnowflakeBase)`
3. `ManifestoResponse` 增加 `rejections: list[ManifestoRejectionItem] = []`
4. Service 层 `reject_manifesto(db, version_id, user_id, req)`：创建拒绝记录
5. Router: `POST "/reject"` → `require_adult` → 201
6. 生成 Alembic migration
7. 已有 `MANIFESTO_ALREADY_SIGNED` 检查需扩展：已拒绝的用户不能再签署，已签署的用户不能再拒绝

**Patterns to follow:** `ManifestoSignature` model for structure; `sign_manifesto` service method for pattern; existing error code pattern.

**Test scenarios:**
- 成人用户拒绝 → 201，rejection 记录创建
- 已签署的用户不能拒绝 → 409
- 已拒绝的用户不能再签署 → 409
- 同一用户不能拒绝两次 → 409
- `GET /family/manifesto` 返回的 `rejections` 包含拒绝列表
- 拒绝原因可选（nullable）

**Verification:** `pytest tests/backend/api/test_manifesto_reject_api.py` pass; `alembic upgrade head` succeeds; `ruff check` clean.

---

### U2. 前端依赖安装 + 类型扩展

**Goal:** 安装 `@vue-flow/core`，扩展前端 TypeScript 类型以支持 rejection 和 flow state。

**Requirements:** R1, R3, R10

**Dependencies:** U1 (for rejection type alignment)

**Files:**
- `frontend/apps/main/package.json` (modify — add `@vue-flow/core`)
- `frontend/apps/main/src/types/manifesto.ts` (modify — add rejection types, flow state types)
- `frontend/apps/main/src/api/manifesto.ts` (modify — add `rejectManifesto` API function)
- `frontend/apps/main/src/i18n/locales/zh-CN.ts` (modify — add flow-related i18n keys)
- `frontend/apps/main/src/i18n/locales/en-US.ts` (modify — add flow-related i18n keys)

**Approach:**
1. `cd frontend && pnpm add @vue-flow/core` (installed in main app only)
2. 扩展 `types/manifesto.ts`：
   - 新增 `ManifestoRejection` interface: `{ id, user_id, reason, created_at }`
   - `Manifesto` interface 增加 `rejections: ManifestoRejection[]`
   - 新增 `FlowState` type: `'draft' | 'signing' | 'rejected' | 'modifying' | 'effective' | 'expired'`
   - 新增 `MemberSigningStatus` type: `'signed' | 'confirmed' | 'pending_sign' | 'pending_confirm' | 'rejected' | 'expired'`
   - 新增 `FlowMemberState` interface: `{ userId, displayName, role, status, isCurrentUser, signatureData?, rejectionReason? }`
3. 新增 API 函数 `rejectManifesto(reason?: string)` → `POST /family/manifesto/reject`
4. 添加 i18n keys：`manifesto.flow.*`（流程节点名称）, `manifesto.status.*`（成员状态文案）, `manifesto.deadline.*`（截止时间相关）, `manifesto.reject.*`（拒绝相关）

**Patterns to follow:** 现有 `manifesto.ts` types 和 `api/manifesto.ts` 模式。i18n 必须通过 `t()` 引用。

**Test scenarios:**
- `@vue-flow/core` 安装成功，import 不报错
- 类型定义覆盖所有 flow state 和 member status 组合
- `rejectManifesto()` 正确调用 POST endpoint
- 所有新增 i18n keys 在 zh-CN 和 en-US 中都有定义

**Verification:** `pnpm typecheck` clean; `pnpm lint` clean.

---

### U3. `useManifestoFlow` composable — 流程状态推导

**Goal:** 创建核心 composable，从 API 数据推导流程状态、成员状态和当前用户状态。

**Requirements:** R2, R3, R4, R5, R6, R9, R10, R11

**Dependencies:** U2

**Files:**
- `frontend/apps/main/src/composables/useManifestoFlow.ts` (new)
- `frontend/apps/main/tests/unit/composables/useManifestoFlow.spec.ts` (new)

**Approach:**
1. `useManifestoFlow(manifesto, members, currentUserId)` 接收响应式参数
2. 输出 `flowState: ComputedRef<FlowState>` — 推导逻辑：
   - `manifesto.status === 'draft'` → `'draft'`
   - 有 rejection 记录 → `'rejected'`
   - 所有成员已签署/确认（无拒绝）→ `'effective'`
   - `signing_deadline` 已过 且 未全部签署 → `'expired'`
   - 否则 → `'signing'`
3. 输出 `memberStates: ComputedRef<FlowMemberState[]>` — 每个成员的状态：
   - 遍历 `familyStore.members`
   - 匹配 `manifesto.signatures` 判断是否已签署/确认
   - 匹配 `manifesto.rejections` 判断是否已拒绝
   - 根据 `member.role === 'child'` 区分状态文案
   - 标记 `isCurrentUser`
4. 输出 `currentRound: ComputedRef<number>` — `manifesto.current_version.version_number`
5. 输出 `signingProgress: ComputedRef<{ signed: number, total: number }>`
6. 输出 `deadlineInfo: ComputedRef<{ expired: boolean, remaining: string | null }>` — 计算截止时间剩余/已过
7. 输出 `currentUserState: ComputedRef<FlowMemberState | null>` — 当前用户的状态
8. 输出 `canSign: ComputedRef<boolean>` — 当前用户是否可以签署（会签中 + 待签署/确认 + 未过期）
9. 输出 `canReject: ComputedRef<boolean>` — 当前用户是否可以拒绝（会签中 + 待签署/确认 + 未过期 + 成人）

**Patterns to follow:** `useManifestoWizard.ts` for composable pattern. Pure computation, no API calls.

**Test scenarios:**
- Draft manifesto → `flowState === 'draft'`
- All members signed → `flowState === 'effective'`
- Has rejection → `flowState === 'rejected'`
- Deadline passed, not all signed → `flowState === 'expired'`
- Active, some pending → `flowState === 'signing'`
- Adult member signed → `status === 'signed'`
- Child member signed (null data) → `status === 'confirmed'`
- Adult member not signed → `status === 'pending_sign'`
- Child member not signed → `status === 'pending_confirm'`
- Current user correctly flagged with `isCurrentUser === true`
- `canSign` true only when signing + pending + not expired
- `canReject` true only when signing + pending + not expired + adult

**Verification:** All test scenarios pass; `pnpm typecheck` clean.

---

### U4. Vue Flow 自定义节点组件

**Goal:** 创建 5 种自定义流程节点组件，每种对应一种流程状态。

**Requirements:** R1, R2, R3, R4, R5, R11

**Dependencies:** U2, U3

**Files:**
- `frontend/apps/main/src/components/manifesto/flow/FlowCreatedNode.vue` (new)
- `frontend/apps/main/src/components/manifesto/flow/FlowSigningNode.vue` (new)
- `frontend/apps/main/src/components/manifesto/flow/FlowRejectedNode.vue` (new)
- `frontend/apps/main/src/components/manifesto/flow/FlowModifyingNode.vue` (new)
- `frontend/apps/main/src/components/manifesto/flow/FlowEffectiveNode.vue` (new)
- `frontend/apps/main/src/components/manifesto/flow/MemberStatusList.vue` (new)
- `frontend/apps/main/src/components/manifesto/flow/flowNodeStyles.ts` (new)

**Approach:**
1. **FlowCreatedNode** — 简单节点：图标 + "家庭约定已创建" 标签。历史状态用灰色。
2. **FlowSigningNode** — 复合节点：标题（"第N轮家庭会签"）+ 进度（"3/4 已完成"）+ `MemberStatusList` 嵌入 + 截止时间。当前节点时边框高亮 + 阴影 + 轻微脉冲动画。
3. **FlowRejectedNode** — 节点：标题（"会签未通过"）+ 拒绝成员列表 + 拒绝原因（截断展示）。`--color-error` 色调。
4. **FlowModifyingNode** — 节点：图标 + "约定修改中" 标签。
5. **FlowEffectiveNode** — 节点：图标 + "家庭约定已生效" + 生效日期。`--color-success` 色调。
6. **MemberStatusList** — 嵌入在 FlowSigningNode 内的成员列表组件。每个成员一行：
   - 头像/名字 + 状态标签 + "我"标识
   - 当前用户待处理时行背景更突出
   - 色块区分：signed/confirmed（绿色）、pending（中性）、rejected（红色）、expired（橙色）
   - 成人显示"待签署/已签署"，儿童显示"待确认/已确认"
7. **flowNodeStyles.ts** — 导出共用的节点 CSS 类名和样式常量。使用 CSS 变量而非硬编码颜色。

**节点尺寸约束：** 所有节点宽度固定为 `min(280px, 85vw)`，自适应高度。确保 320px 宽度下不横向溢出。

**Patterns to follow:** Vue Flow custom node via `#node-<type>` slot pattern; Vant `van-tag` for status badges; existing CSS variable system (`--color-success`, `--color-error`, `--card-bg`, `--text-primary`).

**Test scenarios:**
- FlowSigningNode 渲染成员列表，成员数量和状态正确
- MemberStatusList 当前用户显示"我"标识
- 成人成员显示"已签署/待签署"，儿童显示"已确认/待确认"
- 所有节点 320px 宽度不横向溢出
- 当前节点样式比其他节点更突出
- 暗色模式下颜色正确（使用 CSS 变量）

**Verification:** Components render in isolation; `pnpm typecheck` clean; no horizontal overflow at 320px.

---

### U5. Vue Flow 自定义边组件 + 动画

**Goal:** 创建自定义边组件实现流程流动动画效果。

**Requirements:** R7

**Dependencies:** U2

**Files:**
- `frontend/apps/main/src/components/manifesto/flow/AnimatedFlowEdge.vue` (new)
- `frontend/apps/main/src/components/manifesto/flow/CompletedFlowEdge.vue` (new)

**Approach:**
1. **AnimatedFlowEdge** — 活跃流转边：使用 SVG `stroke-dasharray` + CSS `@keyframes` 实现虚线流动效果。方向自上而下。线条颜色使用 `--color-primary`。动画速度 1.5s/循环。
2. **CompletedFlowEdge** — 已完成边：实线，灰色（`--text-secondary` + 低 opacity），无动画或极慢脉冲。
3. 边的 type 由节点状态组合决定：
   - 已完成节点之间 → `completed`
   - 最后一个已完成节点 → 当前节点 → `animated`（活跃流转）
   - 当前节点 → 未来节点 → 不渲染边（或极淡虚线）
   - 拒绝方向 → `animated` 但颜色为 `--color-error`
4. 所有边为直线（`type: 'straight'` 或自定义），纵向连接。

**Patterns to follow:** Vue Flow custom edge via `#edge-<type>` slot; SVG path rendering.

**Test scenarios:**
- AnimatedFlowEdge 显示流动动画
- CompletedFlowEdge 无流动动画，视觉弱化
- 拒绝方向边使用错误色
- `prefers-reduced-motion: reduce` 时动画降级

**Verification:** Edges render correctly between nodes; animations visible; reduced-motion respected.

---

### U6. `ManifestoFlowViewer` — Vue Flow 容器组件

**Goal:** 封装 Vue Flow 容器，负责节点/边数据生成、只读配置、滚动定位。

**Requirements:** R1, R2, R7, R8, R13

**Dependencies:** U3, U4, U5

**Files:**
- `frontend/apps/main/src/components/manifesto/flow/ManifestoFlowViewer.vue` (new)

**Approach:**
1. **Props:** `flowState`, `currentRound`, `memberStates`, `deadlineInfo`, `hasRejections`, `signingProgress`
2. **节点数据生成** — computed `nodes: Node[]`：
   - 根据 `flowState` 决定显示哪些节点（动态流程）
   - 正常流程：created → signing → effective
   - 有拒绝：created → signing → rejected → modifying → signing(R2) → effective
   - 多轮：历史轮次的 signing 节点简化显示
   - 每个节点 position: `{ x: 0, y: index * 180 }`（纵向排列）
3. **边数据生成** — computed `edges: Edge[]`：
   - 连接相邻节点
   - 根据状态设置 `type: 'animated' | 'completed'` 和 `animated: true/false`
4. **Vue Flow 配置** — 只读模式：
   ```
   :nodes-draggable="false"
   :nodes-connectable="false"
   :elements-selectable="false"
   :zoom-on-scroll="false"
   :zoom-on-pinch="false"
   :pan-on-drag="false"
   :prevent-scrolling="true"
   :fit-view="false"
   ```
5. **滚动定位** — `onNodesInitialized` 回调中调用 `fitView({ nodes: [currentNodeId], padding: 0.3 })` 将当前节点居中
6. **自定义节点 slot 注册**：
   ```html
   <template #node-flow-created="nodeProps">
     <FlowCreatedNode v-bind="nodeProps" />
   </template>
   <!-- 同理注册其他 4 种节点 -->
   <template #edge-animated="edgeProps">
     <AnimatedFlowEdge v-bind="edgeProps" />
   </template>
   <template #edge-completed="edgeProps">
     <CompletedFlowEdge v-bind="edgeProps" />
   </template>
   ```
7. **容器高度** — 根据节点数量动态计算 `height: nodeCount * 180 + 'px'`，不设固定高度，避免与页面滚动冲突
8. **CSS imports** — 在组件中引入 `@vue-flow/core/dist/style.css`（非 scoped）

**Patterns to follow:** Vue Flow `VueFlow` component with custom node/edge slots.

**Test scenarios:**
- 正常流程渲染 3 个节点 + 2 条边
- 拒绝流程渲染 5 个节点 + 4 条边
- 当前节点正确传递给 fitView
- 容器高度随节点数量自适应
- Vue Flow 不拦截页面滚动事件

**Verification:** Flow renders correctly for each state scenario; no scroll interference; current node centered.

---

### U7. `ManifestoSignPage.vue` 重构 — 页面布局与条件渲染

**Goal:** 重构签署页面，整合流程可视化、条件性签署操作、约定内容展示。

**Requirements:** R1-R13, R6 (核心)

**Dependencies:** U1, U2, U3, U6

**Files:**
- `frontend/apps/main/src/pages/ManifestoSignPage.vue` (modify — major refactor)

**Approach:**
1. **页面结构重构** — 新布局：
   ```
   van-nav-bar
   ↓
   ManifestoFlowViewer (流程状态区域)
   ↓
   ManifestoViewer (约定内容，可折叠或始终可见)
   ↓
   操作区 (条件渲染)
   ```
2. **数据获取** — 保持现有逻辑：`manifestoApi.getCurrentManifesto()` + `familyStore.fetchFamily()`
3. **使用 `useManifestoFlow`** — 传入 manifesto + members + currentUser，获取 flowState/memberStates/currentUserState
4. **条件性操作区** — 根据 flowState 和 currentUserState 渲染：
   - `flowState === 'signing'` + `currentUserState.status === 'pending_sign'` + 成人 →
     保留现有 scroll/timer gate + SignaturePad + 确认按钮 + 新增拒绝按钮
   - `flowState === 'signing'` + `currentUserState.status === 'pending_confirm'` + 儿童 →
     确认按钮（`van-button`）+ 拒绝按钮（如果成人可拒绝，儿童不可拒绝 — 实际儿童不显示拒绝）
   - `flowState === 'signing'` + `currentUserState.status === 'signed'` →
     "我 · 已签署" + 已签名的图片展示（可选）
   - `flowState === 'signing'` + `currentUserState.status === 'confirmed'` →
     "我 · 已确认"
   - `flowState === 'signing'` + `currentUserState.status === 'rejected'` →
     "我 · 已拒绝"
   - `flowState === 'effective'` → 不显示操作区
   - `flowState === 'rejected'` → 不显示操作区
   - `flowState === 'expired'` → "签署已结束"提示
   - `flowState === 'draft'` → 不显示操作区
5. **拒绝操作** — 成人待签署时，除"确认签署"按钮外，增加"拒绝"按钮（`van-button plain type="danger"`）。点击后弹出 `showConfirmDialog` 确认 + 可选拒绝原因输入。调用 `manifestoApi.rejectManifesto(reason)`。
6. **Deadline 显示** — 在 FlowSigningNode 内或操作区上方显示截止时间信息
7. **滚动 gate 保留** — 成人首次待签署时，保留现有的 scroll + timer gate 机制，确保用户阅读约定后才能签署
8. **签署/拒绝后刷新** — 签署或拒绝成功后，重新调用 `getCurrentManifesto()` 刷新数据

**Execution note:** 这是最核心的 unit，涉及整个页面的重新编排。建议先搭建布局骨架，再逐步填充各状态的条件渲染。保持现有的 `SignaturePad` 和 `ManifestoViewer` 的 import，不要重新实现。

**Patterns to follow:** 现有 `ManifestoSignPage.vue` 的 API 调用和数据获取模式; `van-button` 样式; `showConfirmDialog` 确认模式; CSS scoped + CSS 变量。

**Test scenarios:**
- 会签中 + 成人待签署 → SignaturePad + 确认/拒绝按钮可见
- 会签中 + 成人已签署 → "我·已签署"，无 SignaturePad
- 会签中 + 儿童待确认 → 确认按钮可见，无 SignaturePad
- 会签中 + 儿童已确认 → "我·已确认"
- 已生效 → 无任何签署操作
- 已拒绝 → 无签署操作，显示拒绝状态
- 已过期 → "签署已结束"
- 拒绝操作弹出确认对话框 + 可选原因输入
- scroll/timer gate 仅在成人待签署时激活
- 320px 宽度无横向滚动

**Verification:** All 8 scenarios from the requirement (场景 1-8) pass manually; `pnpm typecheck` clean; no horizontal scroll at any mobile width.

---

## Verification Contract

| Gate | Command | Scope |
|------|---------|-------|
| Type check | `cd frontend/apps/main && pnpm typecheck` | Main app |
| Lint | `cd frontend/apps/main && pnpm lint` | Main app |
| Unit tests | `cd frontend/apps/main && pnpm test:run` | Main app |
| Backend tests | `cd server && uv run pytest tests/backend/ -v -k manifesto` | Backend |
| Backend lint | `cd server && uv run ruff check apps/backend/` | Backend |
| Backend migration | `cd server/apps/backend && uv run alembic upgrade head` | Migration |
| Mobile 320px | 手动测试 | Sign page |
| Mobile 375px | 手动测试 | Sign page |
| Vue Flow scroll | 手动测试 — 页面上下滚动不被 Vue Flow 拦截 | Sign page |
| Dark mode | 手动测试 | Sign page |

---

## Definition of Done

1. 所有 7 个 implementation units 完成并通过验证。
2. `pnpm typecheck` 和 `pnpm lint` 在 main app 中 0 errors。
3. 后端 `pytest -k manifesto` pass; `ruff check` clean; `alembic upgrade head` 成功。
4. `@vue-flow/core` 安装并正确使用，不引入其他新依赖。
5. `/manifesto/sign` 页面展示纵向流程图，当前节点为视觉重点。
6. 成员状态正确区分已签署/已确认/待签署/待确认/已拒绝/已过期。
7. 当前用户有明确的"我"标识。
8. 只有会签阶段 + 当前用户待操作时才展示签署/确认控件。
9. 已签署用户不再看到空白签名板。
10. 已生效状态不显示任何签署操作。
11. 拒绝后页面正确展示拒绝状态，不显示签署操作。
12. 320px-430px 宽度无横向滚动。
13. Vue Flow 不干扰页面正常上下滚动。
14. 暗色模式正常显示。
15. `prefers-reduced-motion: reduce` 时动画降级。
16. 需求文档 29 条验收标准全部满足。

---

## Open Questions

- **Q1. 儿童成员在 main app 的 familyStore.members 中是否可见？** 如果 `GET /family` endpoint 只返回成人成员，则主 app 签署页无法展示儿童状态。需确认 `familyStore.members` 是否包含 `role === 'child'` 的用户。如果不包含，可能需要后端扩展 family members endpoint 或签署页只展示成人状态。
- **Q2. 拒绝原因是否必填？** 需求文档暗示可选（"如果已有拒绝原因"）。计划中设为可选（nullable），与需求一致。
- **Q3. 多轮历史的具体交互？** 需求提到"用户可以通过合理交互查看详情"。计划中历史轮次简化显示在流程节点中。是否需要额外的弹窗/展开查看历史轮次的详细成员状态？可在实现时根据视觉复杂度决定。

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Vue Flow 包体积 | 增加 main app bundle size | `@vue-flow/core` tree-shakeable; 只 import 核心组件; 不用 minimap/controls/background 子包 |
| Vue Flow 滚动冲突 | 移动端页面滚动被 Vue Flow 拦截 | `preventScrolling=true` + `panOnDrag=false` + 容器高度自适应（不用固定高度 overflow）|
| 儿童成员不可见 | 无法在 main app 展示儿童签署状态 | 先验证 `familyStore.members` 数据; 如不可见则在 FlowSigningNode 中只展示成人状态，儿童状态通过 `signed_count` 差值间接体现 |
| 后端 reject 改动影响现有流程 | 拒绝功能与现有签署逻辑冲突 | reject 和 sign 互斥（unique constraint 保护）; 不影响现有 sign 逻辑 |
