---
date: 2026-07-30
module: frontend (child) + backend (chores)
problem_type: feature
artifact_contract: ce-unified-plan/v1
artifact_readiness: requirements-only
product_contract_source: ce-brainstorm
parent: docs/design/family-interaction-rules.md
tags: [education-reward, celebration, child-feedback, manifesto-p3]
---

# B1 教育奖励 — 儿童端感知反馈 Plan

> **状态**: requirements-only — 待 ce-plan 丰富实现细节
> **关联**: [`interaction-rules.md`](../design/family-interaction-rules.md) §6
> **原则**: P3 成就不压力 — 跨角色的认可需要被孩子感知到

## Goal Capsule

**Objective**: 当孩子获得教育奖励时，在 celebration 弹窗中传达"爸爸妈妈奖励了你"的专属文案，让孩子感知到跨角色的认可。

**Product authority**: 交互规范文档 `interaction-rules.md §6` 已定义预期行为。

**Open blockers**: 无。

---

## Product Contract

### Background

后端已完成教育奖励功能（`education_reward_enabled` 家庭开关 + `real_reward_enabled` 模板开关），审批时创建 `Activity(type='education_reward')` 记录在家长账本。但儿童端完全没有信号——孩子只看到 stars/coins 增加，无法区分普通奖励和教育奖励。

`interaction-rules §6` 识别了这个缺口：

> Child 完成任务获得教育奖励时，celebration 动画应包含"爸爸妈妈奖励了你 X 星星币！"的专属文案

### Scope

**In scope**:

1. 后端轮询接口返回教育奖励信号
2. 儿童端 celebration 弹窗展示教育奖励专属文案

**Out of scope**:

- 教育奖励的后端逻辑（已完成）
- 家长端 dashboard 摘要（已完成）
- 教育奖励的金额/换算显示（孩子用星星币思考，不需要知道 yuan）

### User Flow

```
1. 孩子完成任务 → 等待家长审批
2. 家长审批通过 → 后端创建 education_reward Activity（已有）
3. 孩子端轮询检测到 approved → 同时获得 education_reward_coins 信号（新增）
4. Celebration 弹窗展示 → 包含"爸爸妈妈奖励了你 X 星星币！"文案（新增）
```

### Requirements

#### R1: 后端 — 轮询接口扩展

`GET /child/chores/{instance_id}/status` 扩展返回教育奖励信息。

**行为**:
- 当 `status === 'approved'` 时，查询是否存在对应的 `Activity(type='education_reward', entity_id=instance_id)`
- 如果存在，返回 `education_reward_coins`（星星币数量，int）
- 如果不存在或未启用，返回 `education_reward_coins: null`
- 保持轻量：不返回 yuan 金额（孩子不需要知道换算）

**响应示例**:
```json
{
  "status": "approved",
  "education_reward_coins": 50
}
```

#### R2: 前端 — 捕获教育奖励信号

`ChildTasksPage.vue` 的 `pollForApproval()` 捕获 `education_reward_coins`。

**行为**:
- 轮询响应包含 `education_reward_coins` 时，存储到响应式变量
- 传递给 celebration 流程

#### R3: 前端 — Celebration 弹窗展示教育奖励文案

`TreasureRevealPopup.vue` 增加教育奖励文案展示。

**行为**:
- 新增 `educationRewardCoins` prop（可选，number | null）
- 当 `educationRewardCoins > 0` 时，在 `popup-stars` 下方显示专属文案
- 文案样式与现有 celebration 视觉一致（Clay 品牌色，warm 基调）

**文案示例**:
- zh-CN: "爸爸妈妈奖励了你 50 星星币！"
- en-US: "Mom and Dad rewarded you 50 star coins!"

#### R4: i18n Key

新增 i18n key（遵循 repo 约定，不硬编码中文）:

| Key | zh-CN | en-US |
|-----|-------|-------|
| `celebration.educationReward` | 爸爸妈妈奖励了你 {coins} 星星币！ | Mom and Dad rewarded you {coins} star coins! |

### Key Decisions

| 决策 | 选择 | 理由 |
|------|------|------|
| 反馈位置 | 融入 TreasureRevealPopup | 情感最集中，celebration 是核心情感时刻 |
| 信号传递 | 扩展 status 轮询响应 | 轻量，无额外 API 调用 |
| 显示单位 | 星星币（coins） | 孩子用 coins 思考，不需要 yuan 换算 |
| 条件显示 | `education_reward_coins > 0` 时才显示 | 未启用教育奖励时不影响现有 celebration |

### Acceptance Examples

**AE1: 教育奖励启用，家长审批通过**
- 前置: `education_reward_enabled=True`, `real_reward_enabled=True`, 孩子完成任务
- 操作: 家长审批通过
- 预期: 孩子端 celebration 弹窗显示"爸爸妈妈奖励了你 X 星星币！"

**AE2: 教育奖励未启用**
- 前置: `education_reward_enabled=False`
- 操作: 孩子完成任务，家长审批
- 预期: celebration 弹窗正常显示，无教育奖励文案（行为不变）

**AE3: 教育奖励启用但模板关闭**
- 前置: `education_reward_enabled=True`, 该任务模板 `real_reward_enabled=False`
- 操作: 孩子完成该任务，家长审批
- 预期: celebration 弹窗无教育奖励文案（该任务未触发教育奖励）

### Technical Hints (non-binding)

供 ce-plan 参考的实现方向：

- 后端: `get_chore_status()` 查询 `Activity` 表，`entity_id=instance_id, type='education_reward'`
- 前端: `pollForApproval` 返回 `education_reward_coins`，存入 `ref`
- `useCelebration` 或 `CelebrationAnimation` 接收并传递 prop
- `TreasureRevealPopup` 新增 prop + 条件渲染段落
