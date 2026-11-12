---
title: Challenge Type Ecosystem Expansion - Plan
type: feat
date: 2026-11-12
topic: challenge-type-ecosystem
artifact_contract: ce-unified-plan/v1
product_contract_source: ce-brainstorm
execution: code
---

## Goal Capsule

- **Objective:** 8 个学科中每一个都有自己可被孩子识别的招牌挑战体验，同时练习流程恢复可达（先解 #210 的阶段流转回归，再扩展 6 种新类型并配上学科招牌映射）。
- **Means:** 现有 `ChallengeConfig` 联合类型加入 6 个平等的 discriminator；每个学科一个招牌类型作为首次练习默认入口；限时挑战作为掌握后的复习变体独立于 union。
- **Authority:** 用户主导（全部关键决策来自对话中用户的选择）。
- **Execution profile:** code（前端 Vue 组件 + 静态配置；后端不涉及）。
- **Open blockers:** 无阻塞项。所有产品决策已落定；剩余细节留给规划阶段。

---

## Product Contract

### Summary

在修复 #210 阶段流转回归之后，把 6 种新挑战类型（找规律、拼图、估算、连线、找错误、tap 填色网格画图）作为平等成员加入现有 `ChallengeConfig` 联合类型，每种类型各自实现 Vue 组件并复用现有 MOR 调度器与发现式流程；配上学科招牌映射，使 8 个学科各有首次练习的默认入口。限时挑战作为"掌握后才能进入"的复习变体，不进入发现式流程。

### Problem Frame

孩子端现有的动手挑战只覆盖 7 个 topic（6 个数学、1 个科学），8 个学科里 6 个学科完全没有动手环节，绝大多数 topic 直接走答题。#210 上线后还把阶段机接成了死循环——任何 topic 都进不了答题页（没挑战的 topic 在模式页无反应，有挑战的无限重复挑战）。在这条断流之上，4 种挑战类型（3 种偏数学）让孩子的体验在学科之间几乎没有差别。本次工作要解决的，是"学科之间看不出区别"这件事本身，以及让这条练习流程再次可用。

### Key Decisions

- **方案 A：扩展现有联合类型，复用 MOR 调度器**（session-settled: user-directed — 拒绝方案 B 双 shell、方案 C 学科模板优先：现有 MOR dispatcher 已经是 `resolveChallengeComponent(type)` → component 的纯函数映射，扩展 6 种类型只需在注册表加 6 行，代价最小且完全满足学科分工）。Governs R2, R3, R4。
- **每学科一招牌 + 多类型并存**（session-settled: user-directed — 保留现有"一个学科挂多种类型"的灵活性，招牌只是默认入口；拒绝"学科与类型 1:1 固定绑定"的刚性模型）。Governs R5, R6。
- **学科→招牌映射**（session-settled: user-directed，按用户确认的草图）：
  - 数学 → 找规律（Pattern）
  - 科学 → 估算（Estimate）
  - 语文 → 找错误（Spot the Mistake）
  - 历史 → 排序（Order，现有类型升为招牌）
  - Personal & Social → 连线（Connect）
  - Life Skills → 估算（Estimate，与科学共用）
  - Computing → 拼图（Puzzle）
  - Learning to Learn → 找错误（Spot the Mistake，与语文共用）
  - 画图（Draw）不作为任何学科的招牌，作为次级类型供数学几何等场景按需调用。
  - Governs R5, R6, AE1。
- **限时挑战（Rush）= 复习变体**（session-settled: user-directed — 拒绝进入发现式流程：倒计时和 #210 的"无打击、可无限重试"原则冲突；接受作为掌握后的复习变体，用现有 `LearningProgress.mastery_level` 做门槛）。Governs R11, R12。
- **画图 = tap 填色网格，非自由画布**（session-settled: user-directed — 拒绝自由画布：实现、评判、触摸适配代价过高；接受在预设网格上 tap 切换单元格填充状态）。Governs R9。
- **#210 阶段流转回归纳入本次范围作为第一优先级**（session-settled: user-directed — 拒绝单独先修：断流不修，后续所有类型无法验证）。Governs R1, AE1, AE2。
- **评判本地化、后端不记录**（session-settled: user-directed — 与现有 4 种类型一致；拒绝新增后端挑战记录）。Governs R7, R17。
- **新类型带测试基线**（user-approved — agent 提议、用户默许：现状 Classify/Distribute 本就缺测试，本次不补旧账；新类型每个交付至少一个组件级测试，防止缺口复制成 10 个）。Governs R16。

### Requirements

#### 流程修复（前置）

- R1. 修复 #210 引入的阶段流转回归：`PracticeSessionPage` 必须能从未进入过挑战的 topic 进入答题阶段，已完成的挑战后流程能继续推进到模式选择并再次答题，不再出现死循环。

#### 类型扩展

- R2. `ChallengeConfig` 联合类型新增 6 个 discriminator：`pattern`、`puzzle`、`estimate`、`connect`、`spot-the-mistake`、`draw-grid`。每种类型继承 `ChallengeBase` 字段。
- R3. 每种新类型在 `components/learning/challenges/` 下有独立的 Vue 组件，遵守现有接口：接收 `config` 作为 prop，发出 `@complete` 与 `@request-tutor` 事件。
- R4. `components/learning/challenges/index.ts` 的注册表更新，新增 6 种类型到 `CHALLENGE_COMPONENTS`，使 `resolveChallengeComponent` 能正确分发。

#### 学科招牌

- R5. 新增学科招牌映射（per-subject signature mapping），记录每个学科的招牌类型。映射是纯数据（不引入新抽象）。
- R6. 首次进入某学科的新 topic 时，优先加载该学科的招牌类型作为默认挑战；同一学科的其他 topic 可以挂该学科的其他类型，招牌不独占。

#### 评判与提示

- R7. 每种新类型自带本地判定函数（与现有 4 种一致），返回 `{ isCorrect, hint }`。判定规则按类型区分：
  - Pattern：序列下一项与正确答案一致
  - Puzzle：碎片位置正确
  - Estimate：用户输入值落入容差范围
  - Connect：所有配对正确
  - Spot the Mistake：正确标记出错位置
  - Draw-grid：单元格填充与目标一致
- R8. 每种新类型在 `i18n/locales/zh-CN.ts` 和 `en-US.ts` 下各加一组提示文案（`learning.challenge.<type>.*`），包含正确提示、接近提示、错误提示。

#### 交互

- R9. 所有新类型使用 tap-only 交互：tap-select / tap-place / tap-to-toggle；不用自由画布、不用 HTML5 drag-and-drop、不用 pointer event 自由绘制。
- R10. 所有新类型的可点击目标满足移动端触摸最小尺寸；`ChallengeShell` 的按钮/区域在移动端视口不溢出、不重叠。

#### 限时挑战（复习变体）

- R11. Rush 作为"复习变体"独立于 `ChallengeConfig` 联合类型；进入门槛为 `LearningProgress.mastery_level` 非 `'locked'`。
- R12. Rush 不进发现式流程；UI 入口与现有发现式挑战入口分开，避免误触。

#### 内容

- R13. 每个学科招牌类型至少配置 2-3 个示范 topic（`TOPIC_CHALLENGE_MAP` 条目），使招牌能实际被孩子触达。
- R14. 修正现有 `mt_skYly2Qm01` 映射错误（配置为 `balance-fruit-weights` 但 topic 是"测量长度"），改为重量类 topic。
- R15. 新增挑战配置静态一致性校验（测试），校验 topic_key 存在于 taxonomy、challenge id 唯一、signature 映射指向已注册的 discriminator。

#### 测试

- R16. 6 种新类型每种至少交付一个组件级测试（`components/learning/challenges/__tests__/`），覆盖正确、接近、错误三种判定路径。

#### 约束

- R17. 挑战判定与状态（`sessionStorage` 持久化）完全留在前端；后端不记录挑战尝试、不记录挑战类型。
- R18. 所有新类型的文本字段（scenario、scenarioZh、discoveryMessage、discoveryMessageZh、conceptName/Zh、hints）必须通过 i18n key 或常量定义，遵守仓库 i18n 规则（不硬编码中文）。

### Actors

- A1. **孩子（6-12 岁）**：进入学科 territory、完成招牌挑战、进入答题、在复习模式下进入限时挑战。
- A2. **学科招牌映射**（数据实体）：决定每个学科首次挑战的默认类型。
- A3. **掌握度记录**（现有 `LearningProgress`）：作为 Rush 进入门槛。

### Key Flows

- F1. **首次学科招牌挑战**
  - **Trigger:** 孩子进入某学科的某个 topic，该 topic 配置了招牌类型挑战。
  - **Steps:** 进入 practice session → 直接展示招牌挑战（scenario 阶段）→ 孩子完成 → 发现时刻（揭示 concept name）→ 模式选择 → 答题 → 结果。
  - **Covered by:** R1, R5, R6, AE1。
- F2. **非招牌学科的后续练习**
  - **Trigger:** 孩子再次进入同一学科的其他 topic，该 topic 配了同学科的其他类型。
  - **Steps:** 进入 practice session → 展示该 topic 配置的类型（可能是招牌也可能是次级）→ 完成 → 答题 → 结果。
  - **Covered by:** R6, R7, AE4。
- F3. **已掌握 topic 的限时复习**
  - **Trigger:** 孩子进入一个 mastery_level != 'locked' 的 topic，选择复习模式。
  - **Steps:** 模式选择阶段出现"限时挑战"入口 → 进入 Rush → 60 秒内答题计数 → 显示得分。
  - **Covered by:** R11, R12, AE2。

### Acceptance Examples

- AE1. Covers R1, R5, R6。孩子从数学 territory 进入"分数理解"topic → 直接看到找规律招牌挑战（scenario 文本："看看这串分数，下一个是什么？"）→ 孩子 tap 选答案 → 正确 → 进入发现时刻 → 继续到答题。
- AE2. Covers R11, R12。孩子进入一个已掌握的 topic（mastery_level = 'mastered'）→ 模式选择阶段显示"限时挑战"按钮 → 点击进入 → 60 秒倒计时开始 → 连续答题 → 显示得分。同一页面上，未掌握的 topic 不显示该入口。
- AE3. Covers R7, R9, R10。科学 territory 进入"测量估算"topic → 看到估算招牌挑战（"这罐豆子大概有多少颗？"）→ 孩子 tap 滑动条调整数值 → 提交 → 判定在容差内 → 正确反馈。所有交互均为 tap。
- AE4. Covers R17。孩子完成任何挑战后，后端 `learning_progress` 表只有 mastery 更新（来自答题阶段），没有挑战尝试记录；`sessionStorage` 本地有挑战状态用于页面离开恢复。
- AE5. Covers R14, R15。`fair-distribution.ts` 现有 `mt_skYly2Qm01` 条目改为重量类 topic 的 balance 配置；静态校验测试通过，所有 topic_key 在 taxonomy 中可解析。

### Scope Boundaries

- **延期（Deferred for later）**
  - 批量内容生产：1590 topic 的模板化/生成式挑战配置生产路径（本次只覆盖招牌 + 少量示范）。
  - 后端挑战记录：挑战尝试、挑战类型的持久化。
  - 自由画布画图：Draw 类型保持 tap 填色网格。
  - Rush 进入发现式流程。
  - 现有 4 种挑战类型的测试补齐（Classify/Distribute）。
- **不在本产品身份内（Outside this product's identity）**
  - 非练习流程的迷你游戏或奖励驱动挑战。
  - 学科招牌的导航/可视化重构（由其他 plan 负责）。

### Dependencies / Assumptions

- **依赖：**
  - `#210` 已合入 main（阶段流程断流，本次修复）
  - 现有掌握度数据可访问（`LearningProgress.mastery_level`，已验证存在于 `server/packages/db/models/learning/progress.py`）
  - 现有 `cytoscape` 依赖可用于连线/拼图可视化（`frontend/apps/child/package.json`）
- **假设：**
  - 8 学科的 taxonomy `subject` 字段稳定（`server/packages/os_taxonomy/topics.json`）
  - 孩子设备支持 tap 交互（移动端 WebView 或 H5）
  - 招牌映射的学科名用 taxonomy 的 subject 英文值（`Mathematics`, `Science`, `English`, `History`, `Personal & Social Development`, `Life Skills`, `Computing`, `Learning to Learn`）
  - 现有 `TOPIC_CHALLENGE_MAP` 扩展方式足以覆盖招牌映射，不需要新的查找服务

### Outstanding Questions

- **延期到规划阶段（Deferred to Planning）：**
  - 6 种新类型的测试策略（unit / component / E2E 具体分配）
  - Rush 的 UI 入口位置（模式选择页的按钮 vs. 单独的复习 tab）
  - Rush 的计分公式（正确数 vs. 正确率）
  - 每种新类型的容差/难度分级策略（Estimate 的容差范围，Draw 的目标形状生成）
  - 是否需要在 PracticeSessionPage 的 `startSession` 中做"已创建 session 时跳过重复挑战查找"的守卫
