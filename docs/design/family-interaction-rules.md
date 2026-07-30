---
date: 2026-07-30
module: frontend (main + child)
problem_type: interaction-design
applies_when: 实现具体交互效果（shimmer、弹窗、动画、通知）时作为规范
tags: [interaction-rules, shimmer, animation, dialog, notification, cross-app]
parent: family-manifesto-design.md
---

# 家庭交互规则详细规范

> **状态**：v1.0 — 从 family-manifesto-design.md 拆分
> **日期**：2026-07-30
> **父文档**：[`family-manifesto-design.md`](../family-manifesto-design.md)（愿景 + 原则）
> **本文档**：交互规则的具体实现规范，供 ce-plan 和前端开发直接引用

---

## 1. Shimmer / Loading 时机

### 1.1 角色感知规则

| 场景 | Owner | Member | Child |
|------|-------|--------|-------|
| **设置页加载** | 慢 shimmer（600ms），逐行展开 | 标准（300ms） | N/A（child 无此页） |
| **列表加载** | 信息骨架（300ms），保持布局 | 同 owner | 品牌色块脉动 + 微弹跳（Clay 风格） |
| **AI 响应** | 思考链骨架屏 + 进度 | 同 owner | N/A（child 不直接面对 AI） |
| **详情页加载** | 内容骨架，避免全页闪烁 | 同 owner | 全页渐变过渡（不用 skeleton） |
| **审批列表加载** | 标准骨架 + badge 数字 | N/A | N/A |

### 1.2 Child 特殊规则

- 列表 shimmer 使用 Clay 品牌色（`brand-pink` / `brand-ochre` / `brand-teal`）的柔和脉动
- 配合 `scale(0.98) → scale(1.0)` 的呼吸动画，传达"宝箱快打开了"的期待感
- **绝对不用灰色 skeleton** — 灰色在 Clay 世界中传达"故障"而非"加载中"

### 1.3 可复用组件：RoleShimmer

已决策（O4）：需要一个可复用的 `RoleShimmer` CSS 组件，根据角色自动切换样式：
- **Owner/Member**：标准 `van-skeleton` 骨架屏
- **Child**：Clay 品牌色脉动 + 微弹跳

实现层面由 ce-plan 负责。

---

## 2. 弹窗 / 对话框分类

### 2.1 分类表

| 场景类型 | 交互形式 | 动画 | 原因 |
|----------|---------|------|------|
| **破坏性确认**（Owner 删除资产/成员） | 底部 slide-up 面板 | 300ms ease-out | 底部面板比中心弹窗更有"掌控感" |
| **破坏性确认**（Child 删除心愿） | **不用弹窗** | inline 撤销提示（snackbar 3s） | 中心弹窗对孩子 = 警告/惩罚 |
| **审批请求**（Child 完成 → Parent 审批） | 设置页卡片微呼吸动画 | border glow 脉冲 2s + badge | "你的家人需要你了"而非"又一个待办" |
| **财务决策**（大额操作、策略选择） | 半屏 bottom-sheet | 200ms 慢入 | 创造思考空间 |
| **孩子成就**（任务完成、心愿达成） | 全屏 celebration overlay | confetti + 1s burst | 核心情感时刻需要放大 |
| **错误/异常**（所有角色） | Toast slide-down + 自动消失 | 300ms ease-in, 3s 自动消失 | 错误不应变成"惩罚感" |
| **信息提示**（非阻断性） | 顶部 banner | fade-in 200ms | 可忽略，不强制 attention |

### 2.2 关键约束

- Child 端**禁止使用** `van-dialog` 的居中弹出模式做破坏性确认
- 审批通知的视觉语言是"被需要"而非"催促"
- 错误 toast 自动消失时间统一 3s，不需要用户手动关闭

---

## 3. 动画时长规范

### 3.1 按类型分角色

| 动画类型 | Owner/Member (main app) | Child (clay app) |
|----------|------------------------|-------------------|
| **页面转场** | 200ms ease-out | 300ms spring |
| **列表项出现** | 150ms stagger (每项延迟 30ms) | 200ms stagger + 微弹跳 |
| **弹窗进入** | 250ms ease-out | 300ms spring + scale |
| **弹窗退出** | 200ms ease-in | 250ms ease-in |
| **按钮反馈** | 100ms scale(0.96) | 150ms scale(0.92) |
| **Tab 切换** | 200ms slide | 250ms slide + 弹性 |
| **Celebration** | N/A | ≤ 1500ms total |

### 3.2 压力规避规则

- 任何动画不得 > **2000ms**（避免"等待动画结束"的焦虑）
- `prefers-reduced-motion: reduce` 时所有动画降级为 fade（50ms）
- 错误状态的动画使用 shake 300ms（不超过 3 次抖动），不用 flash/blink

---

## 4. 跨角色通知策略

### 4.1 通知矩阵

| 事件 | Owner 接收 | Member 接收 | Child 看到 |
|------|-----------|------------|-----------|
| 新成员加入家庭 | ✅ 即时通知 | ✅ 即时通知 | N/A |
| 成员被停用 | ✅ 即时通知 | ✅ 仅自己收到 | N/A |
| 孩子完成任务待审批 | ✅ badge + 列表 | ❌ | ❌ |
| 审批通过/拒绝 | ❌ | ❌ | ✅ 温和庆祝/安慰动画 |
| 家庭设置变更 | ✅ toast 确认 | ✅ 下次打开时 banner | ❌ |
| AI 主动建议（Dashboard） | ✅ 卡片 | ✅ 同等卡片 | N/A |
| 心愿达成 | ❌ | ❌ | ✅ celebration 全屏 |

### 4.2 通知原则

- 孩子端的"通知"只通过**视觉变化**传达（badge、动画），不推送
- 家长端的审批通知不应该用"催促"语气
- 设置变更的通知应该说明"什么变了 + 对你有什么影响"
- Member 通知使用 `van-notify` 顶部通知条（已决策 O2），不做独立偏好设置页

---

## 5. 跨端一致性规则

### 5.1 "两个设计系统，一个家庭" 的边界

| 维度 | 可以不同 | 必须一致 |
|------|---------|---------|
| 色彩 | ✅ 各 app 用各自己的品牌色 | ❌ 语义色含义不能冲突（success 不能一边绿一边红） |
| 动画风格 | ✅ main 克制，child 活泼 | ❌ 时长上限必须遵守（都 ≤ 2000ms） |
| 字体大小 | ✅ child 可以更大 | ❌ 最小可读尺寸必须 ≥ 14px |
| 交互模式 | ✅ main 用列表/表格，child 用卡片/游戏 | ❌ 同一数据在两端不能传达矛盾信息 |
| 加载体验 | ✅ main 用 skeleton，child 用品牌色脉动 | ❌ 两者都不能超过 600ms（child）/ 300ms（main） |
| 错误体验 | ✅ main 用 toast，child 用 inline 提示 | ❌ 都不能用"惩罚式"语气 |

### 5.2 共享语义 Token 约束

从 [`docs/design-tokens.md`](../design-tokens.md) 继承的硬规则：

- `--color-success`：两端都表示"成功/正向"，不允许出现语义漂移
- `--color-error`：两端都表示"错误/危险"
- `--color-canvas`：各自值可以不同，但都是"页面背景"
- `--color-muted`：两端都表示"次要/辅助文字"

**已知 gap**：Main `--color-muted (#93939f)` on canvas 对比度仅 3.0:1（仅达 large text AA），需关注。

---

## 6. B1 教育奖励的交互层完善

> B1 后端已完成（教育奖励 Activity 记录 + 摘要统计），但**交互层**在 manifesto 视角下有缺口。

**当前缺口**：
- Child 端：完成任务 → 获得教育奖励 → **无感知反馈**（只看到 coins 增加，不知道这是"教育奖励"）
- Parent 端：可以在 Dashboard 看到摘要 → 但 child 端的"被认可感"没有被传达

**交互规范建议**：
- Child 完成任务获得教育奖励时，celebration 动画应包含"爸爸妈妈奖励了你 X 星星币！"的专属文案
- 这是 P3（成就不压力）原则的具体体现：跨角色的认可需要被孩子感知到
