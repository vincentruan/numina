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

- **Objective:** 8 个学科中每一个都有自己可被孩子识别的招牌挑战体验，同时练习流程恢复可达。
- **Means:** 现有 `ChallengeConfig` 联合类型加入 6 个平等的 discriminator；每个学科一个招牌类型作为首次练习默认入口；限时挑战作为掌握后的复习变体独立于 union。
- **Authority:** 用户主导（全部关键决策来自对话中用户的选择）。
- **Execution profile:** code（前端 Vue 组件 + 静态配置为主；挑战判定后端不涉及。例外：R13a 为 5 个无题目学科补最小题目模板；R13b 为 Rush 判分需要 `session_mode='rush'` 跳过进度更新的最小后端 guard）。
- **Open blockers:** 无阻塞项。所有产品决策已落定；剩余细节留给规划阶段。
- **Ships as:** 3 个 PR（PR1 #210 修复 → PR2 类型与组件 → PR3 招牌映射 + 内容 + Rush + 后端题目模板/guard），见 Implementation Units。

> **Product Contract preservation:** restructured, no scope change. 原「延期到规划阶段」问题已在本规划中解析（见 Planning Contract §KTD1/KTD6/KTD7 与 §Assumptions）。Product Contract 内仅修复 R13 失败时序描述（配合 KTD1）、R18 字段表（去掉不存在的 `hints` 常量字段）、A2 措辞（映射为静态数据非运行时 dispatch）、F2 的 `Covered by` 引用（AE4 实为 R17 覆盖），均不改变产品行为。

---

## Product Contract

### Summary

在修复 #210 阶段流转回归之后，把 6 种新挑战类型（找规律、拼图、估算、连线、找错误、tap 填色网格画图）作为平等成员加入现有 `ChallengeConfig` 联合类型，每种类型各自实现 Vue 组件并复用现有 MOR 调度器与发现式流程；配上学科招牌映射，使 8 个学科各有首次练习的默认入口。限时挑战作为"掌握后才能进入"的复习变体，不进入发现式流程。

### Problem Frame

孩子端现有的动手挑战只覆盖 7 个 topic（6 个数学、1 个科学），8 个学科里 6 个学科完全没有动手环节，绝大多数 topic 直接走答题。#210 上线后还把阶段机接成了死循环——任何 topic 都进不了答题页（没挑战的 topic 在模式页无反应，有挑战的无限重复挑战）。在这条断流之上，4 种挑战类型（3 种偏数学）让孩子的体验在学科之间几乎没有差别。本次工作要解决的，是"学科之间看不出区别"这件事本身，以及让这条练习流程再次可用。

### Key Decisions

- **方案 A：扩展现有联合类型，复用 MOR 调度器**（session-settled: user-directed — 拒绝方案 B 双 shell、方案 C 学科模板优先：现有 MOR dispatcher 已经是 `resolveChallengeComponent(type)` → component 的纯函数映射，扩展 6 种类型只需在注册表加 6 行，代价最小且完全满足学科分工）。Governs R2, R3, R4。
- **每学科一招牌 + 多类型并存**（session-settled: user-directed — 保留现有"一个学科挂多种类型"的灵活性，招牌只是默认入口；拒绝"学科与类型 1:1 固定绑定"的刚性模型）。Governs R5, R6。
- **学科→招牌映射**（session-settled: user-directed，按用户确认的草图；学科键用 `LearningTopic.subject` 的 slug）：
  - mathematics（数学） → 找规律（Pattern）
  - science（科学） → 估算（Estimate）
  - english（语文） → 找错误（Spot the Mistake）
  - history（历史） → 排序（Order，现有类型升为招牌）
  - personal_social → 连线（Connect）
  - life_skills → 估算（Estimate，与科学共用）
  - computing → 拼图（Puzzle）
  - learning_to_learn → 找错误（Spot the Mistake，与语文共用）
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
- R1a. 为 R1 的修复交付一条页面级回归测试（`PracticeSessionPage.test.ts` 或同级），覆盖两条路径：(a) 没有 `TOPIC_CHALLENGE_MAP` 条目的 topic 选择模式后直接进入答题页；(b) 有挑战配置的 topic 走 discovery → mode → answering 不再重入 discovery。

#### 类型扩展

- R2. `ChallengeConfig` 联合类型新增 6 个 discriminator：`pattern`、`puzzle`、`estimate`、`connect`、`spot-the-mistake`、`draw-grid`。每种类型继承 `ChallengeBase` 字段。
- R3. 每种新类型在 `components/learning/challenges/` 下有独立的 Vue 组件，遵守现有接口：接收 `config` 作为 prop，发出 `@complete` 与 `@request-tutor` 事件。
- R4. `components/learning/challenges/index.ts` 的注册表更新，新增 6 种类型到 `CHALLENGE_COMPONENTS`，使 `resolveChallengeComponent` 能正确分发。

#### 学科招牌

- R5. 新增学科招牌映射（per-subject signature mapping），记录每个学科的招牌类型。映射是纯数据（不引入新抽象）。
- R6. 学科招牌映射决定每个学科的招牌类型在哪些示范 topic 上落地（R13），由 R15 静态校验；运行时挑战选择保持 topic_key → config 通过 `TOPIC_CHALLENGE_MAP`，不再引入新的 subject 维度查找。同一学科的其他 topic 可以挂该学科的其他类型，招牌不独占。

#### 评判与提示

- R7. 每种新类型自带本地判定函数（与现有 4 种一致），返回 `{ verdict: 'correct' | 'close' | 'wrong', hint }`。判定规则按类型区分：
  - Pattern：下一项与正确答案一致 → correct；下一项与正确答案差一个索引（如同组元素换序）→ close；否则 wrong
  - Puzzle：碎片位置全部正确 → correct；恰好一个碎片位置错 → close；否则 wrong
  - Estimate：用户输入值落入窄容差 → correct；落入宽容差 → close；否则 wrong
  - Connect：全部配对正确 → correct；恰好一对错 → close；否则 wrong
  - Spot the Mistake：正确标记出错位置 → correct；标记了相邻行 → close；否则 wrong
  - Draw-grid：单元格填充与目标完全一致 → correct；恰好一格不一致 → close；否则 wrong
- R8. 每种新类型在 `i18n/locales/zh-CN.ts` 和 `en-US.ts` 下各加一组提示文案（`learning.challenge.<type>.*`），包含正确提示、接近提示、错误提示。

#### 交互

- R9. 所有新类型使用 tap-only 交互：tap-select / tap-place / tap-to-toggle / tap-to-step（tap +/- 步进，用于 Estimate 的数值输入）；不用自由画布、不用 HTML5 drag-and-drop、不用 pointer event 自由绘制、不用 slider 拖动。
- R10. 所有新类型的可点击目标满足移动端触摸最小尺寸（48 CSS px 下限，与 `ChallengeShell` 按钮一致）；`ChallengeShell` 的按钮/区域在移动端视口不溢出、不重叠。`ChallengeShell` 需支持 `verdict` 三态反馈（correct / close / wrong），close 与 wrong 用**非颜色**线索区分（glyph + 样式），让接近反馈在视觉上区别于错误、且对色弱孩子可用。

#### 限时挑战（复习变体）

- R11. Rush 作为"复习变体"独立于 `ChallengeConfig` 联合类型；进入门槛为 `LearningProgress.mastery_level === 'mastered'`（仅已掌握的 topic 显示入口）。
- R12. Rush 不进发现式流程；UI 入口与现有发现式挑战入口分开，避免误触。
- R13b. Rush 判分依赖答案暴露：复用 `createPracticeSession({ session_mode: 'rush' })` 建会话以取得带答案题目（`batchGetQuestions` 仅在活跃会话包含题目时返回答案），`finishPracticeSession` 对 `session_mode === 'rush'` 跳过 `update_progress_from_session`（最小后端 guard，一行分支），保证 Rush 不推进 mastery、不移动 mastered 门槛。

#### 内容

- R13. 每个学科招牌类型至少配置 2-3 个示范 topic（`TOPIC_CHALLENGE_MAP` 条目），使招牌能实际被孩子触达。每个示范 topic 必须有至少一条已批准（approved）的题目，否则孩子完成招牌后 `startSession` 会以 `PRACTICE_NO_QUESTIONS_AVAILABLE` 失败、招牌触达后无法推进到答题。画图（draw-grid）虽非任何学科的招牌，至少配置 1 个 topic 使用 draw-grid 配置，使该类型可被孩子触达。
- R13a. 题目生产覆盖：现有题目模板仅覆盖 math/chinese/english/science 四个学科（`packages/domain/question_templates`），History、Personal & Social、Life Skills、Computing、Learning to Learn 五个学科没有任何已批准题目。本次范围为这五个学科的招牌示范 topic 增加最小题目生产步骤（或把对应的招牌明确移入延期清单），否则其招牌入口无法被触达。
- R14. 修正现有 `mt_skYly2Qm01` 映射错误（配置为 `balance-fruit-weights` 但 topic 是"测量长度"），改为重量类 topic。替换后的 topic 同样必须有一条已批准题目。
- R15. 新增挑战配置静态一致性校验（测试），校验 topic_key 存在于 taxonomy、challenge id 唯一、signature 映射指向已注册的 discriminator、signature 映射的学科键是合法的 subject slug（存在于 `SUBJECT_MAP` 的 value 集合）。

#### 测试

- R16. 6 种新类型每种至少交付一个组件级测试（`components/learning/challenges/__tests__/`），覆盖正确、接近、错误三种判定路径。

#### 约束

- R17. 挑战判定与状态（`sessionStorage` 持久化）完全留在前端；后端不记录挑战尝试、不记录挑战类型。
- R18. 新类型的挑战内容文本（scenario、scenarioZh、discoveryMessage、discoveryMessageZh、conceptName/Zh）沿用现有数据文件的常量写法（与 4 种现有类型一致）；UI chrome 与反馈文案走 R8 的 `learning.challenge.<type>.*` i18n key，判定函数返回的 `hint` 由 i18n key 构造（同现有 `evaluateOrder` 模式）。

### Actors

- A1. **孩子（6-12 岁）**：进入学科 territory、完成招牌挑战、进入答题、在复习模式下进入限时挑战。
- A2. **学科招牌映射**（纯静态数据）：记录每个学科的招牌类型，由 R15 静态校验；运行时挑战分发仍走 `TOPIC_CHALLENGE_MAP`，映射本身不 dispatch。
- A3. **掌握度记录**（现有 `LearningProgress`）：作为 Rush 进入门槛。

### Key Flows

- F1. **首次学科招牌挑战**
  - **Trigger:** 孩子进入某学科的某个 topic，该 topic 配置了招牌类型挑战。
  - **Steps:** 进入 practice session → 直接展示招牌挑战（scenario 阶段）→ 孩子完成 → 发现时刻（揭示 concept name）→ 模式选择 → 答题 → 结果。
  - **Covered by:** R1, R5, R6, AE1。
- F2. **非招牌学科的后续练习**
  - **Trigger:** 孩子再次进入同一学科的其他 topic，该 topic 配了同学科的其他类型。
  - **Steps:** 进入 practice session → 展示该 topic 配置的类型（可能是招牌也可能是次级）→ 完成 → 答题 → 结果。
  - **Covered by:** R6, R7。
- F3. **已掌握 topic 的限时复习**
  - **Trigger:** 孩子进入一个 mastery_level === 'mastered' 的 topic，选择复习模式。
  - **Steps:** 模式选择阶段出现"限时挑战"入口 → 进入 Rush → 请求足够支撑 60 秒的题量 → 60 秒内答题计数 → 显示得分；若提前答完则计时结束，分数屏幕显示剩余时间。
  - **Covered by:** R11, R12, AE2。
  - **中途离开：** 丢弃本次 run，不 resume（Rush 不走 sessionStorage 持久化路径）。

### Acceptance Examples

- AE1. Covers R1, R5, R6。孩子从数学 territory 进入一个配置了 Pattern 招牌挑战的 Mathematics topic（当前无挑战配置的 topic_key，见 R13）→ 直接看到找规律招牌挑战（scenario 文本："看看这串分数，下一个是什么？"）→ 孩子 tap 选答案 → 正确 → 进入发现时刻 → 继续到答题。
- AE1b. Covers R1。孩子进入一个没有 `TOPIC_CHALLENGE_MAP` 条目的 topic → 选择模式 → 直接进入答题页（不卡在模式页、不重入挑战）。
- AE2. Covers R11, R12。孩子进入一个已掌握的 topic（mastery_level = 'mastered'）→ 模式选择阶段显示"限时挑战"按钮 → 点击进入 → 60 秒倒计时开始 → 连续答题 → 显示得分。同一页面上，未掌握的 topic 不显示该入口。
- AE3. Covers R7, R9, R10。科学 territory 进入一个 Science 估算示范 topic → 看到估算招牌挑战（"这罐豆子大概有多少颗？"）→ 孩子 tap +/- 步进调整数值 → 提交 → 判定在容差内 → 正确反馈。所有交互均为 tap。
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
  - 现有 `cytoscape` 依赖仅用于连线/拼图的静态可视化渲染；交互层由组件自建（tap-to-place / tap-to-toggle，符合 R9/R10）（`frontend/apps/child/package.json`）
- **假设：**
  - 8 学科的 taxonomy `subject` 字段稳定（`server/packages/os_taxonomy/topics.json`）
  - 孩子设备支持 tap 交互（移动端 WebView 或 H5）
  - 招牌映射的学科键用 `LearningTopic.subject` 的 slug 值（`mathematics`, `science`, `english`, `history`, `personal_social`, `life_skills`, `computing`, `learning_to_learn`，见 `server/scripts/seed_learning_topics.py` §SUBJECT_MAP；taxonomy 的 display name 只存在于 `server/packages/os_taxonomy/topics.json`）
  - 现有 `TOPIC_CHALLENGE_MAP` 扩展方式足以覆盖招牌映射，不需要新的查找服务

---

## Planning Contract

### Key Technical Decisions

- KTD1. **阶段流转修复 = 把挑战解析移出 `startSession`。** #210 死循环根因是 `startSession` 同时「建会话」和「解析挑战」：有挑战 topic 走 discovery → mode →（再点模式又触发 `startSession` 重新解析挑战）→ discovery 无限循环；无挑战 topic 因 `startSession` 只把 `phase` 设回 `'mode'` 而卡在模式页。修复 = 页面进入时单次解析挑战决定入口 phase（`onMounted`/`load`），`startSession` 只建会话 + 拉题 + 直进 `'answering'`。Governs R1, R1a。
- KTD2. **三态判定契约 `verdict: 'correct' | 'close' | 'wrong'`。** R7 要求三态、R10 要求 close 视觉区别于 wrong。`ChallengeShell` 的 `feedbackIsCorrect: boolean` 改为 `feedbackVerdict` 三态 prop，4 个现有组件机械迁移（现有类型无 close，只产出 correct/wrong）；判定函数统一返回 `{ verdict, hint }`。close 与 wrong 用非颜色线索区分（glyph + 样式）。**三态推进规则**：correct 置 `completed` 并显示继续按钮（现状）；close 计一次 attempt 且保持检查按钮可重试，`attemptCount >= 2` 时额外解锁继续按钮（同 `showTutorSuggestion` 阈值）；wrong 同现状。Governs R7, R10。
- KTD3. **学科招牌映射 = 纯静态数据 + 静态校验。** 映射按 subject slug 键控，由 R15 的静态校验测试保证一致性（topic_key 在 taxonomy、challenge id 唯一、signature 指向已注册 discriminator、学科键 ∈ `SUBJECT_MAP` 值集）。运行时查找仍走 `TOPIC_CHALLENGE_MAP`，不引入新的 subject 维度查找服务。Governs R5, R6, R15。
- KTD4. **每种新类型的判定为纯函数。** 每个类型一个纯判定函数（接收 config + 用户状态，返回 `{ verdict, hint }`），作为组件旁的导出 helper（非独立文件，与现有 `evaluateOrder` 内嵌模式一致），组件测试覆盖三种判定路径。Governs R7, R16。
- KTD5. **新类型内容沿用现有常量数据文件写法。** 6 个类型的内容数据注册进 `fair-distribution.ts` 的 `CHALLENGE_CONFIGS`；文本沿用 scenario/scenarioZh/… 常量（R18），UI chrome 走 i18n key（R8）。Governs R13, R14, R17, R18。
- KTD6. **Rush = 独立非计分复习路径，用 rush 会话模式取答案。** 原「不创建 practice-session、不新增后端端点」的机制不可行：`batchGetQuestions` 仅在活跃会话包含题目时返回答案（`practice.py` §batch），没有会话就拿不到答案、无法判分。修正为：`createPracticeSession({ session_mode: 'rush' })` 建会话取带答案题目，客户端本地判分（正确数即得分）；`finishPracticeSession` 对 `session_mode === 'rush'` 跳过 `update_progress_from_session`（R13b 的最小 guard）。settled 意图（不进发现式、不推进 mastery、不移动 mastered 门槛）保留；仅机制从「无会话」改为「rush 会话 + 跳过进度」。进入门槛 `mastery_level === 'mastered'`；入口 = 模式选择页独立按钮；计分 = 正确数；提前答完即计时结束、分数屏显示剩余时间。Governs R11, R12, R13b。（注意：此为对原规划假设的可行性修正，不改变 user-directed 的「复习变体不进发现式」决策。）
- KTD7. **Estimate/Draw 的题面参数为静态配置常量，且保证可达/可见。** Estimate 每个 config 自带 `startValue` + `step` + `targetValue` + 窄/宽容差，且 `targetValue === startValue + k * step`（整数 k，静态校验保证目标可达，否则 correct 不可达）；Draw 每个 config 自带预设目标网格，且 `scenario`/`scenarioZh` 必须逐格明确目标布局（否则精确匹配 judge 对 6-12 岁孩子不可玩）。不做运行时形状/题面生成。Governs R7, R9, R13, R15。

### High-Level Technical Design

**PracticeSessionPage 阶段机（修复后）。** 4 个 phase：`discovery → mode → answering → result`。关键变化是把挑战解析从 `startSession` 移到页面进入时的单次解析：进入时解析 challenge → 有则 `discovery`、无则 `mode`；`startSession` 只负责建会话并直进 `answering`（有 challenge 的 topic 在 discovery 完成后回 `mode` 选题量，选完不再重入 discovery）。

```
           ┌───────────────────────────── entry (load/onMounted)
           │  resolveTopicKey() → getChallengeForTopic()
           │  has challenge? ──yes──▶ discovery
           │       └──no──▶ mode
           ▼
        discovery ──complete──▶ mode
                                   │ startSession(count): create session + batchGetQuestions
                                   ▼
                                answering ──finish──▶ result
             (manipulate phase retired — challenge lives inside discovery only)
```

**组件分发拓扑（新增 6 类型后）。** `ManipulateObserveReflect` 经 `resolveChallengeComponent(type)` 纯函数分发到注册组件；`ChallengeShell` 提供三态 verdict 反馈壳。数据流不变：`TOPIC_CHALLENGE_MAP`（topic_key → config id）→ `CHALLENGE_CONFIGS`（id → config）→ MOR → 类型组件。

```
PracticeSessionPage
  └─ DiscoveryChallengeIntro ─▶ ManipulateObserveReflect
                                   └─ resolveChallengeComponent(type)
                                        ├─ PatternChallenge
                                        ├─ SpotTheMistakeChallenge
                                        ├─ PuzzleChallenge
                                        ├─ ConnectChallenge
                                        ├─ EstimateChallenge
                                        └─ DrawGridChallenge
                                   （每个组件内嵌 ChallengeShell 三态 verdict + 非颜色 glyph）
```

### Assumptions

以下为规划层未经验证的推断（headless 无用户确认，落到 `## Assumptions` 供 reviewer 审视）：

- A1. `english` subject 在 taxonomy 中是「英语」学科（English Thinking / Grammar & Punctuation / Reading Comprehension…），**没有「语文/chinese」学科**。原 Key Decision 将 `english` 标注为「语文」是中文标签的笔误；slug 级映射 `english → spot-the-mistake` 本身技术成立（英语语法/阅读的「找错误」），保持不变。实现只按 slug 键控，不受标签影响。
- A2. `chinese.*` 题目模板（`chinese.literacy` / `chinese.pinyin`）的 topic_key 前缀为 `mtc_*`，与 taxonomy 的 `mt_*` 不一致，疑似孤儿模板。本次不处理；实现 R13a 时若发现 `chinese` 模板无法解析 topic 属于既有问题，不在本次范围。相应地，R13a「已覆盖四学科」的基线实为 math/science/english 三个可解析学科。
- A3. Estimate 容差与 Draw 目标网格均作为 config 内的静态常量（KTD7），不做运行时生成。
- A4. Rush 通过 `session_mode: 'rush'` 会话取答案（KTD6），`finishPracticeSession` 对 rush 模式跳过 `update_progress_from_session`（R13b）；不新增独立端点。
- A5. 6 种新类型判定为纯前端函数，R17 约束下无后端挑战记录；mastery 更新只来自答题阶段（既有 `update_progress_from_session`，rush 模式除外）。
- A6. 招牌示范 topic 的「至少一条已批准题目」约束只能由 R15 静态校验覆盖到「topic_key 在 taxonomy + 配置一致」层；「该 topic 确有 approved 题目」依赖 seed（U12）而非静态数据，由 U12 的模板测试 + seed dry-run 证据兜底，无法在纯前端静态校验中证明（题目在 DB，不在静态文件）。

### Sequencing

- PR1（U1）是后续一切的前置：断流不修，PR2/PR3 的新类型与招牌无法被验证（R1 前置约束）。
- PR2（U2–U9）交付类型 + 组件 + i18n，其组件测试用内联 fixture（`makeConfig`）自证，不依赖 PR3 的内容数据。
- PR3（U10–U13）依赖 PR2 的类型/注册表（内容数据引用新 discriminator）与 PR1 的流程（Rush 入口挂在模式选择页）。PR3 内含后端（U12 模板 + R13b guard），前后端混合是本 PR 的已知代价，因 U11/U12 是双向耦合的联合产物（见 U11/U12）。
- 每个 PR 独立可测：PR1 页面回归测试；PR2 每类型组件测试 + 注册表/类型编译；PR3 静态校验测试 + 后端模板测试。

---

## Implementation Units

### Unit Index

| U-ID | Title | Files touched (primary) | Depends on |
|------|-------|------------------------|-----------|
| U1 | #210 阶段流转修复 + 页面回归测试 | `PracticeSessionPage.vue`, `pages/learning/PracticeSessionPage.test.ts` | — |
| U2 | 联合类型 6 discriminator + 注册表骨架 + ChallengeShell 三态 | `types/learning-challenge.ts`, `challenges/index.ts`, `challenges/ChallengeShell.vue` + 4 现有组件迁移 | U1 |
| U3 | i18n 键（6 类型 × 三态 + hint + Rush） | `i18n/locales/zh-CN.ts`, `en-US.ts` | U2 |
| U4 | Pattern 组件 + 判定 + 测试 | `challenges/PatternChallenge.vue`, `__tests__/PatternChallenge.test.ts` | U2, U3 |
| U5 | Spot-the-Mistake 组件 + 判定 + 测试 | `challenges/SpotTheMistakeChallenge.vue`, `__tests__/SpotTheMistakeChallenge.test.ts` | U2, U3 |
| U6 | Puzzle 组件 + 判定 + 测试 | `challenges/PuzzleChallenge.vue`, `__tests__/PuzzleChallenge.test.ts` | U2, U3 |
| U7 | Connect 组件 + 判定 + 测试 | `challenges/ConnectChallenge.vue`, `__tests__/ConnectChallenge.test.ts` | U2, U3 |
| U8 | Estimate 组件 + 判定 + 测试 | `challenges/EstimateChallenge.vue`, `__tests__/EstimateChallenge.test.ts` | U2, U3 |
| U9 | Draw-grid 组件 + 判定 + 测试 | `challenges/DrawGridChallenge.vue`, `__tests__/DrawGridChallenge.test.ts` | U2, U3 |
| U10 | 学科招牌映射 + 静态校验测试 | `data/learning-challenge/subject-signature.ts`, `data/learning-challenge/static-validation.test.ts` | U2 |
| U11 | 6 类型内容数据 + `TOPIC_CHALLENGE_MAP` + `mt_skYly2Qm01` 修正 | `data/learning-challenge/*-challenges.ts`, `fair-distribution.ts` | U2, U10, U12 |
| U12 | 后端最小题目模板（5 学科）+ seed 步骤 | `packages/domain/question_templates/<subject>_*.py`, `tests/packages/domain/` | U11 |
| U13 | Rush 复习模式（入口 + 计时 + 计分 + 后端 guard） | `PracticeSessionPage.vue`(入口), `components/learning/RushMode.vue`, `__tests__/RushMode.test.ts`, `routers/practice.py`(guard) | U1 |

### PR 1 — #210 阶段流转修复（前置）

#### U1. 修复 #210 阶段流转回归并交付页面回归测试

- **Goal:** 让无挑战 topic 能进入答题、有挑战 topic 走 discovery → mode → answering 不再死循环。
- **Requirements:** R1, R1a。
- **Files:** `frontend/apps/child/src/pages/learning/PracticeSessionPage.vue`；新增 `frontend/apps/child/src/pages/learning/PracticeSessionPage.test.ts`。
- **Approach:** 将 `startSession` 内的挑战解析（`resolveTopicKey()` + `getChallengeForTopic()`）移到页面进入时的单次解析（`load()`/`onMounted`），据此设 `phase = 'discovery' | 'mode'`；`startSession` 只 `createPracticeSession` + `batchGetQuestions` + `phase = 'answering'`（并在 `phase === 'mode'` 时才允许调用）。`onDiscoveryComplete` 维持 `phase = 'mode'`；第二次 `startSession` 不再解析挑战。删除已无消费者的 `'manipulate'` phase 分支（challenge 只活在 discovery 内）。遵循 KTD1。
- **Execution note:** 先写失败的页面回归测试复现死循环，再改代码使其通过（test-first）。
- **Test Scenarios:**
  - 无 `TOPIC_CHALLENGE_MAP` 条目的 topic：mock `getTopicDetail`/`getChallengeForTopic` 返回 null → 点模式按钮 → `startSession` 后 `phase === 'answering'`，渲染 `PracticeQuestionCard`，不卡在 mode 页。
  - 有挑战的 topic：进入即 `phase === 'discovery'` → `onDiscoveryComplete` → `phase === 'mode'` → 点模式按钮 → `phase === 'answering'` 且 `createPracticeSession` 只被调用一次（断言不重入 discovery）。
  - `startSession` 失败（如 `PRACTICE_NO_QUESTIONS_AVAILABLE`）→ 显示错误、phase 不回退到 discovery。
- **Verification:** `cd frontend/apps/child && pnpm test:run src/pages/learning/PracticeSessionPage.test.ts`；`pnpm typecheck`。

### PR 2 — 挑战类型基础设施（前端）

#### U2. 联合类型 6 discriminator + 注册表骨架 + ChallengeShell 三态

- **Goal:** 类型层与共享反馈壳支持 6 新类型。
- **Requirements:** R2, R4, R10。
- **Files:** `types/learning-challenge.ts`；`components/learning/challenges/index.ts`；`components/learning/challenges/ChallengeShell.vue`；迁移 `DistributeChallenge.vue` / `ClassifyChallenge.vue` / `OrderChallenge.vue` / `BalanceChallenge.vue`。
- **Approach:** 在 `types/learning-challenge.ts` 新增 `PatternChallenge`/`PuzzleChallenge`/`EstimateChallenge`/`ConnectChallenge`/`SpotTheMistakeChallenge`/`DrawGridChallenge` 接口（继承 `ChallengeBase`，各自字段：Pattern=候选数组+`correctAnswer`；Puzzle=`correctPlacement` 映射；Estimate=`startValue`+`step`+`targetValue`+`narrowTolerance`+`wideTolerance`；Connect=`pairs` 映射；SpotTheMistake=`lines`+`mistakeLineIndex`；Draw-grid=`gridRows`/`gridCols`+`targetCells`），并加入 union。`ChallengeShell` 的 `feedbackIsCorrect: boolean` 改为 `feedbackVerdict: 'correct' | 'close' | 'wrong'`，新增 `--close` 样式与**非颜色 glyph**（correct=✓、close=≈、wrong=✗，三个不同字符），实现 KTD2 三态推进规则（close 计 attempt、`attemptCount>=2` 解锁继续）。4 个现有组件把 `feedbackIsCorrect` 布尔映射为 `'correct' | 'wrong'`。注册表 `index.ts` 只保留现有 4 个条目 + 类型定义骨架；**每个新组件的 import + 注册行由创建它的 U4–U9 各自添加**（不在 U2 落占位，避免 DoD 占位 stub 冲突与 typecheck 引用不存在文件失败）。
- **Test Scenarios:** `ChallengeShell.test.ts` 扩展：`feedbackVerdict='close'` 时渲染 `--close` 样式类与 close glyph，不渲染 correct/wrong glyph；`'correct'`/`'wrong'` 各自样式类与 glyph 正确；close 且 `attemptCount>=2` 时继续按钮解锁。
- **Verification:** `cd frontend/apps/child && pnpm typecheck && pnpm test:run src/components/learning/challenges/__tests__/ChallengeShell.test.ts`。

#### U3. i18n 键（6 类型 × 三态 + hint + Rush）

- **Goal:** 6 新类型 + Rush 的反馈文案就位，组件不硬编码。
- **Requirements:** R8, R12。
- **Files:** `frontend/apps/child/src/i18n/locales/zh-CN.ts`, `en-US.ts`。
- **Approach:** 在 `learning.challenge` 下按类型新增键组，每类型 correct/wrong/close-hint（close 反馈用共享 `learning.challenge.verdictClose` 通用文案 + 判定返回的 `hint` 在 `feedbackMessage` 槽渲染）；estimate 额外 `estimate.step`。新增 `learning.rush.*` 键组（入口标签「60 秒冲刺」/「60-second Sprint」、退出、倒计时、得分、剩余时间），避免与现有 `practice.mode.challenge`「挑战模式」标签冲突。沿用现有 `learning.challenge` 平铺写法，双语各一份。
- **Test Scenarios:** 无需独立测试（由 U4–U9/U13 组件测试通过渲染断言间接覆盖）；`pnpm typecheck` 确保键名被引用。
- **Verification:** `cd frontend/apps/child && pnpm typecheck`。

#### U4. Pattern 组件 + 判定 + 测试

- **Goal:** 找规律类型可玩可判。
- **Requirements:** R3, R7, R9, R16。
- **Files:** `components/learning/challenges/PatternChallenge.vue`（含导出的 `judgePattern` 纯函数 helper）；`__tests__/PatternChallenge.test.ts`。
- **Approach:** tap-select 候选答案（`options`）；`judgePattern(selectedId, config)` 返回 `{ verdict, hint }`：与 `correctAnswer` 一致 → correct；与正确答案同组相邻（差一个索引）→ close；否则 wrong。`hint` 由 i18n key 构造并渲染进 `ChallengeShell` 的 `feedbackMessage` 槽（close/wrong 时）。`sessionStorage` 持久化（沿用 OrderChallenge 的 `numina:challenge:<id>` 模式，R17）。内嵌 `ChallengeShell` 三态，遵循 KTD2 推进规则。
- **Test Scenarios:** 选 `correctAnswer` → verdict correct（`--correct` 类 + glyph + 正确文案）；选相邻候选 → close（`--close` 类 + close 文案）；选无关候选 → wrong；close 且 `attemptCount>=2` 后继续按钮解锁；判定返回的 hint 在 close/wrong 时渲染；`@complete` 在 continue 后发出；状态重挂载从 sessionStorage 恢复。
- **Verification:** `cd frontend/apps/child && pnpm test:run src/components/learning/challenges/__tests__/PatternChallenge.test.ts`。

#### U5. Spot-the-Mistake 组件 + 判定 + 测试

- **Goal:** 找错误类型可玩可判。
- **Requirements:** R3, R7, R9, R10, R16。
- **Files:** `components/learning/challenges/SpotTheMistakeChallenge.vue`（含 `judgeSpotMistake`）；`__tests__/SpotTheMistakeChallenge.test.ts`。
- **Approach:** 展示若干行文本，每行渲染为 `min-height: 48px` 的全宽行控件（独立标记 gutter），tap 标记出错行；`judgeSpotMistake(selectedLineIndex, config)`：等于 `mistakeLineIndex` → correct；相邻行（±1）→ close；否则 wrong。行高满足 R10 的 48px 触摸下限。hint 走 i18n 并渲染进 feedback 槽。内嵌 `ChallengeShell` 三态 + sessionStorage 持久化，遵循 KTD2。
- **Test Scenarios:** 标记正确行 → correct；标记相邻行 → close；标记其他行 → wrong；tap 重选切换标记；行控件高度 ≥48px（触摸下限断言）；`@complete` 发出。
- **Verification:** `cd frontend/apps/child && pnpm test:run src/components/learning/challenges/__tests__/SpotTheMistakeChallenge.test.ts`。

#### U6. Puzzle 组件 + 判定 + 测试

- **Goal:** 拼图类型可玩可判。
- **Requirements:** R3, R7, R9, R10, R16。
- **Files:** `components/learning/challenges/PuzzleChallenge.vue`（含 `judgePuzzle`）；`__tests__/PuzzleChallenge.test.ts`。
- **Approach:** 碎片槽位 tap-place（先选碎片再 tap 槽位，复用 OrderChallenge 的 select-then-place 交互）；`judgePuzzle(placement, config)`：全部位置正确 → correct；恰一个位置错 → close；否则 wrong。槽位 `min-height: 48px`。cytoscape 仅用于静态渲染（如需要），交互层自建（R9）。hint 走 i18n。内嵌 `ChallengeShell` 三态 + sessionStorage，遵循 KTD2。
- **Test Scenarios:** 全对 → correct；恰一错 → close；多错 → wrong；槽位/碎片 tap 放置与回退；槽位高度 ≥48px；hint 渲染；`@complete` 发出。
- **Verification:** `cd frontend/apps/child && pnpm test:run src/components/learning/challenges/__tests__/PuzzleChallenge.test.ts`。

#### U7. Connect 组件 + 判定 + 测试

- **Goal:** 连线类型可玩可判。
- **Requirements:** R3, R7, R9, R10, R16。
- **Files:** `components/learning/challenges/ConnectChallenge.vue`（含 `judgeConnect`）；`__tests__/ConnectChallenge.test.ts`。
- **Approach:** 左列/右列 tap-to-pair（tap 左侧项再 tap 右侧项建立配对，tap 已配对项解除）；`judgeConnect(pairs, config)`：全部配对正确 → correct；恰一对错 → close；否则 wrong。配对目标 `min-height: 48px`。无自由画线（R9）。hint 走 i18n。内嵌 `ChallengeShell` 三态 + sessionStorage，遵循 KTD2。
- **Test Scenarios:** 全对 → correct；恰一对错 → close；多对错 → wrong；配对/解除交互；目标高度 ≥48px；hint 渲染；`@complete` 发出。
- **Verification:** `cd frontend/apps/child && pnpm test:run src/components/learning/challenges/__tests__/ConnectChallenge.test.ts`。

#### U8. Estimate 组件 + 判定 + 测试

- **Goal:** 估算类型可玩可判。
- **Requirements:** R3, R7, R9, R16。
- **Files:** `components/learning/challenges/EstimateChallenge.vue`（含 `judgeEstimate`）；`__tests__/EstimateChallenge.test.ts`。
- **Approach:** tap +/- 步进调值（从 `startValue` 起步，`step` 为步长，仅 stepper、无候选数值、无 slider），提交后 `judgeEstimate(value, config)`：`|value - targetValue| ≤ narrowTolerance` → correct；`≤ wideTolerance` → close；否则 wrong。config 契约保证 `targetValue === startValue + k * step`（KTD7，静态校验兜底）。hint 走 i18n。内嵌 `ChallengeShell` 三态 + sessionStorage，遵循 KTD2。
- **Test Scenarios:** 值落窄容差 → correct；落宽容差 → close；超出 → wrong；tap +/- 步进更新显示值；`targetValue` 从 `startValue` 整步可达（静态校验断言）；hint 渲染；`@complete` 发出。
- **Verification:** `cd frontend/apps/child && pnpm test:run src/components/learning/challenges/__tests__/EstimateChallenge.test.ts`。

#### U9. Draw-grid 组件 + 判定 + 测试

- **Goal:** tap 填色网格画图类型可玩可判。
- **Requirements:** R3, R7, R9, R10, R16。
- **Files:** `components/learning/challenges/DrawGridChallenge.vue`（含 `judgeDrawGrid`）；`__tests__/DrawGridChallenge.test.ts`。
- **Approach:** 网格单元格 tap-to-toggle 填充态；`judgeDrawGrid(filledCells, config)`：与 `targetCells` 完全一致 → correct；恰一格不一致 → close；否则 wrong。config 契约：`scenario`/`scenarioZh` 逐格明确目标布局（KTD7），`gridCols` 上限使 320px 视口下单元格边长 ≥48px（R10）。无自由画布（R9）。hint 走 i18n。内嵌 `ChallengeShell` 三态 + sessionStorage，遵循 KTD2。
- **Test Scenarios:** 与目标一致 → correct；恰一格差 → close；多格差 → wrong；tap 切换填充；单元格边长 ≥48px（320px 视口断言）；scenario 文本标识每个目标格；hint 渲染；`@complete` 发出。
- **Verification:** `cd frontend/apps/child && pnpm test:run src/components/learning/challenges/__tests__/DrawGridChallenge.test.ts`。

### PR 3 — 招牌映射 + 内容 + Rush + 后端题目模板/guard

#### U10. 学科招牌映射 + 静态校验测试

- **Goal:** 每个学科的招牌类型落成纯数据，并有静态校验护航。
- **Requirements:** R5, R6, R15。
- **Files:** 新增 `frontend/apps/child/src/data/learning-challenge/subject-signature.ts`；新增 `static-validation.test.ts`。
- **Approach:** `SUBJECT_SIGNATURE: Record<string, ChallengeType>`（8 个 slug → 招牌 discriminator，按 Key Decision 草图，draw-grid 不在其中）。`static-validation.test.ts` 校验：(a) 每个 `TOPIC_CHALLENGE_MAP` 的 topic_key 在 taxonomy（`server/packages/os_taxonomy/topics.json`）可解析；(b) `CHALLENGE_CONFIGS` 的 challenge id 唯一；(c) 每个 `SUBJECT_SIGNATURE` 值 ∈ 已注册 `CHALLENGE_COMPONENTS` 的 discriminator 集合；(d) 每个 `SUBJECT_SIGNATURE` 键 ∈ `SUBJECT_MAP` 的 value 集合；(e) 每个招牌类型对应的 `TOPIC_CHALLENGE_MAP` 条目 ≥2 个（R13 的 2-3 示范 topic），draw-grid 至少 1 个；(f) 每个 Estimate config 的 `targetValue` 从 `startValue` 整步可达（KTD7）。遵循 KTD3。读 taxonomy 的测试需在 vitest 配置放宽 server 目录读取（或把 taxonomy 快照复制进测试 fixture），实现时选其一并注明。
- **Test Scenarios:** 注入一个不存在 topic_key → 校验失败；注入重复 challenge id → 失败；signature 指向未注册类型 → 失败；signature 键非法 → 失败；某招牌 topic 数 <2 → 失败；estimate 目标不可达 → 失败；合法数据 → 通过。
- **Verification:** `cd frontend/apps/child && pnpm test:run src/data/learning-challenge/static-validation.test.ts`。

#### U11. 6 类型内容数据 + `TOPIC_CHALLENGE_MAP` + `mt_skYly2Qm01` 修正

- **Goal:** 招牌/次级类型被真实 topic 触达。
- **Requirements:** R13, R14, R18。
- **Files:** 新增 `data/learning-challenge/pattern-challenges.ts`、`puzzle-challenges.ts`、`estimate-challenges.ts`、`connect-challenges.ts`、`spot-mistake-challenges.ts`、`draw-grid-challenges.ts`；修改 `fair-distribution.ts`。
- **Approach:** 每个招牌学科配 2-3 个示范 topic（选择 taxonomy 中已有已批准题目的 topic_key，或配合 U12 新增的题目 topic）；draw-grid 至少 1 个 topic。内容文本沿用常量写法（scenario/scenarioZh/…，R18），hint 不落常量（走 R8 i18n）。`mt_skYly2Qm01` 由「测量长度」topic 改为重量类 topic 的 `balance-fruit-weights`（替换后的 topic 须有已批准题目，见 U12/R13a）。遵循 KTD5。**与 U12 双向耦合**：U11 选定示范 topic_key 供 U12 产题，U12 若发现某 topic_key 不可解析则替换为同类可解析 topic_key 并同步回 U11——两者在 PR3 内作为一次联合产物原子落地。
- **Test Scenarios:** 静态校验（U10）在数据落定后仍通过；`getChallengeForTopic(newTopicKey)` 返回正确 config；`mt_skYly2Qm01` 映射到重量类 topic。
- **Verification:** `cd frontend/apps/child && pnpm test:run src/data/learning-challenge/static-validation.test.ts && pnpm typecheck`。

#### U12. 后端最小题目模板（5 学科）+ seed 步骤

- **Goal:** History / Personal & Social / Life Skills / Computing / Learning to Learn 的招牌示范 topic 各有一条已批准题目。
- **Requirements:** R13a。
- **Files:** 新增 `server/packages/domain/question_templates/history_*.py`（或按学科拆文件）、`personal_social_*.py`、`life_skills_*.py`、`computing_*.py`、`learning_to_learn_*.py`；`__init__.py` 引入使 `@register_template` 生效；新增 `server/tests/packages/domain/test_question_templates_<subject>.py`。
- **Approach:** 每学科至少 1 个模板（对应 U11 选定的招牌示范 topic 的 topic_key），`generate_question` 产出 `review_status='approved'`（source="template" 自动 approve）。`seed_questions_from_templates` 现成可跑（`cd server && uv run python scripts/seed_learning_dev_data.py --questions-only`）。注意：`seed_questions_from_templates` 用空 params 生成、按 content_hash 去重，每个模板仅产一条唯一题，故「至少一条 approved」恰好满足（每模板一条）；模板的 `topic_key` 必须与 U11 的示范 topic_key 精确一致，否则 `skipped_no_topic` 使题目不落地。若某招牌示范 topic 的 topic_key 在 taxonomy 不存在，本单元用可解析的同类 topic_key 替代并同步回 U11。
- **Test Scenarios:** 每个新模板 `generate_question` 返回合法 `GeneratedQuestion`（stem/answer/topic_key 非空，difficulty 合法）；模板 id 在 `TEMPLATE_REGISTRY` 注册；`seed_questions_from_templates(topic_filter=...)` dry_run 时 generated>0 且 skipped_no_topic=0。
- **Verification:** `cd server && uv run pytest tests/packages/domain/test_question_templates_<subject>.py -v`。

#### U13. Rush 复习模式（入口 + 计时 + 计分 + 后端 guard）

- **Goal:** 已掌握 topic 可进入 60 秒限时复习，独立于发现式流程、不误改 mastery。
- **Requirements:** R11, R12, R13b。
- **Files:** 新增 `components/learning/RushMode.vue`；修改 `PracticeSessionPage.vue`（模式选择页按 mastery 条件渲染「60 秒冲刺」入口）；新增 `__tests__/RushMode.test.ts`；修改 `server/apps/backend/app/routers/practice.py`（`finishPracticeSession` 对 rush 模式跳过 `update_progress_from_session`）。
- **Approach:** 模式选择页新增「60 秒冲刺」按钮（`learning.rush.entry`），仅当该 topic `mastery_level === 'mastered'` 时渲染。mastery 来源：`PracticeSessionPage` 页面进入时调 `getMyLearningMap()`（返回 `ProgressResponse[]` 含 `mastery_level`，已存在于 `api/learning.ts`），按当前 topic_id 查 mastery——**不是** `getTopicDetail`（`TopicResponse` 无 mastery 字段）。点击进入 `RushMode`：`createPracticeSession({ session_mode: 'rush', count: 60s 题量 })` → `batchGetQuestions`（活跃会话上下文返回带答案题目）→ 客户端本地判分 → 60 秒倒计时内答题计数，正确数即得分；提前答完计时结束、分数屏显示剩余时间；结束调用 `finishPracticeSession`（后端对 rush 模式跳过进度更新，避免移动 mastery/mastered 门槛）。四个具名状态：常驻顶栏「退出」丢弃 run（无确认框，因无持久化）；拉题 loading；拉题失败 error + 重试；答题规则=提交即推进、无逐题正确反馈、0:00 未答不计分。中途离开不持久化。遵循 KTD6。
- **Test Scenarios:** mastered topic → 模式页渲染「60 秒冲刺」入口，未掌握 topic 不渲染；进入 Rush 后倒计时递减；答对计数累加；提前答完显示剩余时间；拉题 loading/error 状态；离开不持久化（sessionStorage 无 Rush 状态）；后端 `finishPracticeSession` 对 `session_mode='rush'` 不调 `update_progress_from_session`（后端单测）。
- **Verification:** `cd frontend/apps/child && pnpm test:run src/components/learning/__tests__/RushMode.test.ts && pnpm test:run src/pages/learning/PracticeSessionPage.test.ts`；`cd server && uv run pytest tests/backend/ -k rush -v`。

---

## Verification Contract

- **前端（`frontend/apps/child`）**：`pnpm typecheck`；`pnpm test:run`（或按单元路径 scope，如上）。
- **后端（`server`）**：`uv run ruff check <path>`；`uv run mypy <path>`；`uv run pytest tests/packages/domain/<file> -v`。
- **全量（本 PR 涉及前后端时）**：`pnpm -r lint && pnpm -r typecheck && pnpm -r test:run`（前端 workspace）+ `uv run pytest`（server，需时）。
- **关键证明**：U1 的页面回归测试证明 #210 修复（R1/R1a）；U4–U9 的组件测试证明 6 类型三态判定 + 三态推进规则（R7/R16/R10）；U10 静态校验证明映射一致性 + 招牌 topic 数 + estimate 可达（R5/R6/R13/R15）；U12 模板测试证明 5 学科题目生产（R13a）；U13 前后端测试证明 Rush 入口门槛 + 非计分（R11/R12/R13b）。
- **浏览器验证**：PR2 合入后由 `ce-test-browser`（LFG step 8）对子端 practice 流程做冒烟（招牌挑战进入 → 完成 → 答题）；PR3 合入后冒烟 Rush 入口（仅 mastered 显示 + 60 秒计时）。

## Definition of Done

- **全局：**
  - R1–R18 全部有对应实现与测试证据，无 `test.skip`/`.only`/占位 stub；弃用的 `'manipulate'` phase 死代码已移除。
  - 每个新类型组件通过其组件测试（覆盖 correct/close/wrong 三路径 + 三态推进规则），且注册进 `CHALLENGE_COMPONENTS`。
  - 静态校验测试通过（topic_key 可解析、challenge id 唯一、signature 指向已注册 discriminator、学科键合法、招牌 topic 数 ≥2、estimate 目标可达）。
  - 前后端 `typecheck`/`ruff`/`mypy`/相关 `pytest` 均通过。
  - 无后端挑战记录新增（R17）；mastery 更新只来自答题阶段（rush 模式除外，R13b）。
  - Rush 通过 `session_mode='rush'` 取答案，`finishPracticeSession` 跳过 rush 模式的进度更新。
- **每单元：** 其 Test Scenarios 全部通过，`Verification` 命令全绿，无未提交的弃用尝试代码。
