---
date: 2026-07-30
module: frontend (main + child)
problem_type: deferred-items-analysis
applies_when: 决定哪些遗留项纳入 Family Manifesto V1 实现范围时参考
tags: [deferred-items, legacy, child-ui, priority, manifesto]
parent: family-manifesto-design.md
---

# 家庭 Manifesto — 遗留目标整合分析

> **状态**：v1.0 — 从 family-manifesto-design.md 拆分
> **日期**：2026-07-30
> **父文档**：[`family-manifesto-design.md`](../family-manifesto-design.md)（愿景 + 原则）
> **关联文档**：[`family-interaction-rules.md`](./family-interaction-rules.md)（交互规范）
> **本文档**：审视 P3 deferred items 和 child-ui-interaction-ideas 中的未实现创意，按角色视角评估去留

---

## 1. 建议纳入 V1 的遗留项

| 项目 | 来源 | 角色 | 理由 | 优先级 |
|------|------|------|------|--------|
| **Child celebration animation** | [`child-ui-interaction-ideas.md`](../ideation/child-ui-interaction-ideas.md) #1 | Child | 直接对应 P3 原则，核心情感缺失 | 🔴 P0 |
| **Swipe-to-complete** | [`child-ui-interaction-ideas.md`](../ideation/child-ui-interaction-ideas.md) #3 | Child | 配合 celebration，核心 loop 升级 | 🔴 P0 |
| **Mystery bonus ~20%** | [`child-ui-interaction-ideas.md`](../ideation/child-ui-interaction-ideas.md) #7 | Child | V1 纳入，不关闭；未触发时给安慰文案避免失望 | 🔴 P0 |
| **Member 通知偏好** | manifesto 新增 | Member | 对应 P2 的"参与不旁观"原则，使用 `van-notify` | 🟡 P1 |
| **Animated Tab Bar** | [`child-ui-interaction-ideas.md`](../ideation/child-ui-interaction-ideas.md) #9 | Child | 低成本高价值，导航邀请感 | 🟢 P2 |
| **Child toast 错误区分** | [`pr-review-p3-items.md`](../pr-review-p3-items.md) #12 | Child | 对应 P3 的"去惩罚化"原则 | 🟢 P2 |

### 纳入标准

只纳入**直接对应 4 条核心原则**的项，避免 manifesto 变成"什么都想做"的需求清单。

---

## 2. 保留为未来参考的项

| 项目 | 来源 | 理由 | 标记 |
|------|------|------|------|
| **Sound & haptic layer** | [`child-ui-interaction-ideas.md`](../ideation/child-ui-interaction-ideas.md) #6 | H5 环境无可靠 API（`navigator.vibrate()` / Web Audio 兼容性有限），保留为未来原生 app 参考 | 🔵 Future |

---

## 3. 建议推迟（不在 V1 范围）

| 项目 | 来源 | 理由 |
|------|------|------|
| **Child "My Room" 首页** | [`child-ui-interaction-ideas.md`](../ideation/child-ui-interaction-ideas.md) #5 | 高价值但高成本，作为长期愿景标注 |
| **Encouraging empty states** | [`child-ui-interaction-ideas.md`](../ideation/child-ui-interaction-ideas.md) #10 | 好但非核心，当前空状态可接受 |
| **D8 双日期 picker** | P3 deferred | 当前区间按钮已满足 90% 场景 |
| **Logout 路由修复** | [`ui-audit-2026-07-26.md`](../ui-audit-2026-07-26.md) P1 | 属于 bug fix，不属于 manifesto 范畴 |

---

## 4. 已完成但需引用的案例

这些项已实现，但体现了 manifesto 原则，在 ce-plan 或后续设计文档中应作为正面案例引用。

| 已完成项 | 体现的原则 | 引用方式 |
|----------|-----------|---------|
| D8 区间收益率 | P1 掌控不焦虑 — 数据叙事让 owner 理解资产表现 | 数据叙事设计参考 |
| A6 PDF 导出 | P2 参与不旁观 — 数据可导出意味着不锁定 | 数据便携性案例 |
| B1 教育奖励摘要 | P3 成就不压力 — 跨角色联动让孩子感到被认可 | 跨角色联动案例（交互层缺口见 interaction-rules §6） |
| L7 抵押物联动 | P1 掌控不焦虑 — 资产全貌给 owner 完整信息 | 全貌可视化案例 |
| N3 币种统一 | P2 参与不旁观 — 多币种家庭不被排除 | 包容性设计案例 |

---

## 5. 优先级排序逻辑

```
P0 (必须 V1): 直接对应核心原则 + 核心情感缺失
P1 (应该 V1): 对应原则 + 中等工作量
P2 (可以 V1): 对应原则 + 低成本
Future:      原则相关但技术条件不成熟
推迟:         不对应原则 / 属于 bug fix / 成本过高
```
