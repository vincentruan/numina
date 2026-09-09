---
artifact_contract: ce-unified-plan/v1
artifact_readiness: requirements-only
product_contract_source: ce-brainstorm
date: 2026-09-09
topic: signing-timeline-replace-vue-flow
source_ideation: docs/ideation/2026-09-08-manifesto-ceremony-ideation.html (Idea 6)
---

# 签署时间线替换 vue-flow - Plan

## Goal Capsule

**Objective:** 用纯 CSS 垂直签署时间线 (`SigningTimeline.vue`) 替换 `ManifestoFlowViewer.vue` 中的 vue-flow 渲染，消除 `@vue-flow/core` 依赖，保留相同的签署状态语义和流程叙事能力。

**Product authority:** 签署时间线让用户感知「谁签了、谁还没签、流程到哪了」，同时与 manifesto 的仪式感设计语言统一。

**Open blockers:** 无。数据层 (`useManifestoFlow`) 完全不需要改动，仅替换展示层。

## Product Contract

### Key Decisions

- **session-settled: visual-metaphor** — 垂直时间线，非水平步骤条、非卡片序列、非 vue-flow 图
- **session-settled: member-status-embedding** — 成员签署状态内嵌在「签署中」节点内部，不是独立节点
- **session-settled: vue-flow-cleanup** — 完成后彻底删除 vue-flow 相关组件和 `@vue-flow/core` 依赖
- **session-settled: position-preserve** — 保持 `van-collapse` 折叠面板位置不变，先做最小风险替换

### Scope

#### In Scope

1. **新组件 `SigningTimeline.vue`** — 纯 CSS 垂直时间线，替代 `ManifestoFlowViewer.vue`
2. **时间线节点类型** — 映射当前 6 种 flow 节点：
   - 发起节点（金色圆点 + 版本/发起人信息）
   - 签署中节点（金色脉动 + 内嵌成员状态列表）
   - 拒绝节点（红色圆点 + 拒绝理由）
   - 版本更新节点（虚线连接 + 版本号桥接）
   - 生效节点（绿色 ✓ + 生效日期）
   - 等待节点（灰色空心圆 + 虚线）
3. **成员状态内嵌** — 签署中节点内部展示每个成员的状态：
   - 已签署：绿色勾 + 时间戳
   - 已拒绝：红色叉 + 拒绝理由
   - 待签署（当前用户）：金色高亮
   - 待签署（其他）：灰色
   - 已过期：灰色 + 过期标记
   - 儿童确认：区分 `confirmed` / `pending_confirm`
4. **样式** — 使用 manifesto ceremony CSS 变量（gold accent `#c9a84c`、success green `#16A34A`、error red `#DC2626`），适配 dark mode
5. **动画** — CSS `@keyframes` 脉动（签署中节点）+ `<TransitionGroup>` 状态切换
6. **依赖清理** — 删除 `@vue-flow/core` 及其 CSS import

#### Out of Scope

- 折叠面板位置调整（后续迭代）
- 数据层 / `useManifestoFlow` 改动
- API 改动
- 儿童端 (child app) 的签署流程

### Acceptance Examples

**Example 1: 正常签署流程（全部签署完成）**

```
Given 3 位家庭成员，全部已签署，公约已生效
When 用户打开始签页面展开签署进度
Then 看到垂直时间线：
  ● 爸爸发起 v1（金色）
  │  2026-09-01
  ◐ 签署中 3/3（金色脉动）
  │  ✓ 妈妈  已签署 09-05
  │  ✓ 小明  已签署 09-06
  │  ✓ 爸爸  已签署 09-07
  ● 已生效（绿色 ✓）
     2026-09-08
```

**Example 2: 有人拒绝**

```
Given 妈妈拒绝签署并填写理由 "第三条需要修改"
When 用户查看签署时间线
Then 看到：
  ● 爸爸发起 v1
  ◐ 签署中 1/3
  │  ✗ 妈妈  已拒绝
  │    "第三条需要修改"
  │  ✓ 小明  已签署
  │  ◐ 爸爸  待签署（金色高亮，当前用户）
  ✗ 公约被拒绝（红色）
  - - v1 → v2 修改中 - - -（虚线）
  ◐ 新一轮签署中...（灰色脉动）
```

**Example 3: 草稿状态**

```
Given 公约刚创建，尚未发起签署
When 用户查看时间线
Then 只看到一个节点：
  ● 爸爸发起 v1（金色）
     2026-09-09
```

**Example 4: 暗色模式**

```
Given 系统设置为暗色模式
When 用户查看签署时间线
Then 时间线使用暗色变量：背景 #1a1a2e，gold 保持 #d4b86a，
     状态颜色适配暗色对比度
```

### Integration Points

- **`ManifestoSignPage.vue`** — 将 `<ManifestoFlowViewer>` 替换为 `<SigningTimeline>`，传入相同的 props（来自 `useManifestoFlow` 的 computeds）
- **`useManifestoFlow.ts`** — 无改动，数据源不变
- **i18n** — 新增时间线相关的翻译 key（节点标签、状态文本）
- **CSS 变量** — 复用 manifesto ceremony theme tokens（已有 `--ceremony-gold` 等）

### Cleanup Checklist

删除以下文件（全部在 `frontend/apps/main/src/components/manifesto/flow/`）：

| 文件 | 原因 |
|------|------|
| `ManifestoFlowViewer.vue` | 被 `SigningTimeline.vue` 替代 |
| `FlowCreatedNode.vue` | vue-flow 自定义节点 |
| `FlowSigningNode.vue` | vue-flow 自定义节点 |
| `FlowRejectedNode.vue` | vue-flow 自定义节点 |
| `FlowVersionUpdateNode.vue` | vue-flow 自定义节点 |
| `FlowEffectiveNode.vue` | vue-flow 自定义节点 |
| `FlowPendingNode.vue` | vue-flow 自定义节点 |
| `AnimatedFlowEdge.vue` | vue-flow 自定义边 |
| `CompletedFlowEdge.vue` | vue-flow 自定义边 |
| `flowNodeStyles.ts` | vue-flow 节点共享样式 |

**注意:** `MemberStatusList.vue` 的逻辑（状态展示、tag 渲染）应被吸收进 `SigningTimeline.vue` 的签署中节点内嵌部分，然后一并删除。

删除 `@vue-flow/core` 依赖：
```bash
# frontend/apps/main/package.json 移除 "@vue-flow/core"
pnpm install
```

## Outstanding Questions

_无_ — 方向、范围、清理策略均已确认。
