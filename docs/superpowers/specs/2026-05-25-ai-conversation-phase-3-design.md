# AI 会话可视化 Phase 3 增强需求

> 在 MVP（commit `73a347c` 已合入）之后，处理 8 个延后项。本文档锁定 WHAT，HOW 由后续 plan 决定。

**Origin:** `docs/superpowers/specs/2024-01-15-ai-conversation-visualization-design.md` §2.2 / §6 / §8 中标注为 Phase 3 的条目；以及 `docs/superpowers/plans/2024-01-15-ai-conversation-visualization.md` "From 2026-05-25 review (round 3)" 段落中明确延后的 10 项。

**Brainstorm date:** 2026-05-25

---

## 1. 背景

MVP 已交付：`AiProcessBlock` / `AiProcessStep` / `AiToolCallStep` / `AiFinalAnswer` + 三个 utility，并完成 `/ai/chat` 集成。轮 3 review 把 8 项视觉/体验增强和 2 项无后端事件支撑的能力明确推迟到 Phase 3。本次头脑风暴的目标是把这 8 项拆成可独立交付的小批次，避免大爆炸式上线，同时把每一项的"做或不做"与"做到什么程度"锁死。

延后项原始清单（取自 plan Deferred section）：

| # | 条目 | Spec 锚点 |
|---|------|-----------|
| 1 | AiFinalAnswer 报告骨架屏 | §6.1 |
| 2 | AI logo 动图替换 | §2.2 |
| 3 | Reasoning body shimmer 动画 | §2.2 |
| 4 | 过程块标题时间感知 | §2.2 |
| 5 | 回到底部按钮（审计） | §2.1 |
| 6 | AiUserBubble Markdown 渲染 | §3.0 |
| 7 | AiConversation 空状态（审计） | §2.1 |
| 8 | Artifact 链接展示 | §3.0 |

---

## 2. 目标与非目标

### 2.1 目标

- 8 项延后内容全部解决（"实现"或"审计后确认无需实现"）
- 分三个独立可发布的 bundle，互不阻塞，按时间或资源就绪情况各自推进
- 每项给出明确的接收条件（acceptance criteria），让 plan 阶段不需要再发明产品行为

### 2.2 非目标

- 不重新设计 MVP 已落地的组件契约（`steps[]` 数组、CSS 变量化、watchdog、retry 等已生效）
- 不引入新的 agent runtime / framework（沿用原始约束）
- 不在 Phase 3 内完成智能体页（AIReportPage 等）的完整 Task 10 集成；Phase 3 只交付**这些页面所需的视觉前置条件**（Bundle C），实际页面切换由独立的 Task 10 plan 推进
- 不引入 Lottie 等重型动画依赖（详见 §3.A1）

---

## 3. Bundle A — 过程块视觉打磨

**作用域:** 三项纯视觉增强，统一在运行中的过程块上发生。零后端依赖，零新资产以外的依赖，可在 1 个 plan 内顺序交付。

### A1. AI logo SVG sprite（原项目 #2）

**当前状态:** 过程块左上角使用文字 glyph `✦` / `✓` / `✗`（运行/完成/错误）作为状态指示。

**目标行为:**

- 用 SVG 资源替换三个文字 glyph，建立专属的 AI 品牌符号
- 三个状态以 sprite/symbol 形式存在，通过 CSS class 切换：
  - `idle` / `thinking`：核心 logo + 微动效（脉冲、旋转，或两者组合）
  - `done`：完成态，静止
  - `error`：错误态，静止
- 颜色使用 `currentColor` 或 DESIGN.md 设计 token，自适应深色模式，无需额外资源文件
- 状态切换通过 opacity transition 渐变，避免硬切

**接收条件:**

- 浅色与深色模式下 logo 可见、可辨识、可与现有 `.status-running/.status-done/.status-error` 容器色协调
- 过程块从 `running → done` 切换时，logo 状态切换有 ≥150ms 的过渡，无生硬跳变
- SVG 资产体积 ≤8KB（gzip 前），inline 在组件或作为静态资源引入均可
- 没有引入 Lottie / GIF / animation library 等依赖

**显式排除:**

- 不引入 Lottie：28px 角标动画的视觉收益不抵 +200KB bundle 与设计师维护 JSON 的成本
- 不做"AI 品牌色系"重设计；颜色继续走现有 status token

**Open assumption:** 假设设计资源在 Phase 3 启动前已就绪（或工程同学可用 figma/sketch 自产）。若资产未就绪，A1 单独退回（保留 MVP glyph），不阻塞 A2 / A3 上线。

### A2. Reasoning body shimmer（原项目 #3）

**当前状态:** 工具调用参数已有 `.args-running` shimmer 动画；reasoning 步骤只有 marker pulse，body 文字无 shimmer 反馈。

**目标行为:**

- 在 `AiProcessStep`（type=reasoning，status=streaming）的 body 区域追加 shimmer 动画
- 视觉强度与 `.args-running` 一致（同一个 keyframe，同一个色相），保证 reasoning 与 tool 步骤的"运行中"反馈感统一
- streaming 切换为 done 时立即停止动画

**接收条件:**

- 视觉表现：reasoning body 在 streaming 时有可感知但不喧宾夺主的横向 shimmer，与 args 区一致
- 不影响 reasoning 内容的可读性（contrast 仍满足 WCAG AA）
- 移动端（≤768px）shimmer 仍存在，无性能下降（CSS-only，不引入 JS 计时器）

**显式排除:**

- 暂不抽 `.shimmer` 共享 utility 类。当前只两处复用（args + reasoning），DRY 收益小于改动已上线 `AiToolCallStep` 的回归风险；如果未来 Bundle C 的 skeleton 也用 shimmer，再统一抽取。

### A3. 过程块标题时间感知（原项目 #4）

**当前状态:** 过程块 primary title 静态显示 `t('aiProcess.title')`（执行过程），subtitle 显示 `statusRunning/statusDone/statusError` 三态。无时间感知。

**目标行为:**

- Primary title 按 phase 切换：
  - `connecting` / `thinking` → `t('aiProcess.thinkingTitle')`（如"正在思考..."）
  - `answering` → `t('aiProcess.answeringTitle')`（如"正在生成回答..."）
  - `done` → `t('aiProcess.title')`（"执行过程"，与现状一致）
  - `error` → `t('aiProcess.errorTitle')`（如"执行出错"）
- Subtitle 在 thinking phase 显示已思考时长：`已思考 X 秒`，每秒更新；done 后冻结为最终时长
- 时长通过现有 `reasoningStartTime` + 一个每秒触发的响应式 ref 计算；不引入新的状态字段

**接收条件:**

- thinking 持续 ≥1s 后，subtitle 开始展示"已思考 1 秒"，并按秒递增
- phase 切换到 answering / done 时，subtitle 文案立刻同步切换；不出现"已思考 999 秒"残影
- 新增 i18n key 同时提供中英双语
- 旧 `statusRunning/statusDone/statusError` 文案保留为 fallback，phase 字段缺失时仍可工作（防止历史消息回放破图）

**显式排除:**

- 不做"AI 已生成 X 字"或"工具调用第 N/M 步"等更细粒度文案 — 收益边际递减且需要更多字段。

---

## 4. Bundle B — 聊天页 UX

**作用域:** 三项围绕 `/ai/chat` 用户侧体验的工作，其中两项是审计（确认是否需要新建），一项是新建。所有项目都隔离在 `AIChatPage.vue` 与（若新建）`AiUserBubble.vue` 内，零后端依赖。

### B1. 回到底部按钮审计（原项目 #5）

**当前状态（已验证）:** `frontend/apps/main/src/pages/AIChatPage.vue` 已有 `scrollToBottom()`（line 764）和 `.scroll-to-bottom-btn`（line 339-346 模板，line 2418 样式）。

**目标行为:**

- 审计现有按钮是否覆盖 spec §2.1 全部期望：
  1. 用户向上滚动时按钮可见
  2. 距底部 < N px 时按钮自动隐藏
  3. 点击平滑滚动到底部
  4. 流式过程中如果用户上滚，自动滚动暂停（不强制把用户拖回底部）
- 缺哪条补哪条；不重写已有逻辑

**接收条件:**

- 上述 4 条逐一确认（pass / 已存在 / 需要补丁）
- 如果全部已满足：在 plan 中标注 "verified, no code change"，关闭该项
- 如果有缺口：每个缺口对应一个 plan task，引用现有代码行号

### B2. AiUserBubble Markdown 渲染（原项目 #6）

**当前状态:** 用户气泡是 `AIChatPage.vue` 内联 `.bubble.user`（line 1898 / 1911 / 2273），渲染纯文本，依赖 `white-space: pre-wrap` 保留换行。

**目标行为:**

- 抽出独立 `AiUserBubble.vue` 组件（在 `frontend/apps/main/src/components/ai/` 下），承接当前 `.bubble.user` 的视觉，无视觉回归
- 通过 `marked` + `DOMPurify` 渲染 Markdown，并配置**严格 inline-only 白名单**：
  - 允许：换行（br/p）、加粗（strong/b）、斜体（em/i）、内联代码（code）、自动链接（a，需附加 `rel="noopener noreferrer"` + `target="_blank"`）
  - 禁止：image、script、iframe、style、event handler 属性（onclick 等）、block-level（h1-h6、pre/code block、table、blockquote、hr）
- DOMPurify 配置走允许列表（`ALLOWED_TAGS` / `ALLOWED_ATTR`），不依赖 default profile

**接收条件:**

- 用户输入 `**bold** *italic* \`code\` https://example.com 换行测试\n第二行` 在气泡内正确渲染
- XSS 测试用例全部失败注入：`<img src=x onerror=alert(1)>`、`<script>alert(1)</script>`、`[xss](javascript:alert(1))`、`<a href="javascript:..." onclick="...">`、`<iframe>` 等
- 块级 Markdown（如 `# 标题`、`\`\`\`code block\`\`\``、table）在气泡中**降级为纯文本**，不破坏布局
- 单元测试覆盖：基础渲染 + XSS allowlist + 块级降级
- 视觉与 MVP 的纯文本气泡保持一致（padding、font、background 不变）

**显式风险:**

- XSS surface 是 Phase 3 中唯一的安全敏感项。plan 阶段必须包含独立的安全测试 task，且 DOMPurify 配置作为代码评审重点。

**显式排除:**

- 不支持附件预览、表情包、@mention — 与本次需求无关
- 不支持用户在气泡中编辑已发送消息

### B3. AiConversation 空状态审计（原项目 #7）

**当前状态:** `AIChatPage.vue` 在 `messages.length === 0` 时的渲染未审计。MVP 期间用户进入 `/ai/chat` 直接见到的视觉未在 spec 中明确。

**目标行为:**

- 审计 `messages.length === 0` 状态：
  - 当前展示了什么？
  - 是否提供了"开始一次对话"的引导（如示例问题、输入提示、空状态图）？
- 不足部分补齐：至少一句引导文案 + 输入框聚焦提示；丰富版可加 3 个示例问题 chip（如"看一下我家的资产分布"）
- 走 i18n，不硬编码中文

**接收条件:**

- 审计结论书面化：`docs/` 内一行说明 "exists" / "exists but lacks X" / "missing entirely"
- 缺口补齐后，新用户首次进入 `/ai/chat` 5 秒内即理解"这里可以做什么"
- 示例问题 chip（若实现）点击后填充到输入框并 focus，不直接发送

---

## 5. Bundle C — 智能体页耦合

**作用域:** 两项只在智能体页（AIReportPage 等）集成 `AiFinalAnswer` 后才有消费场景。Bundle C **依赖 Task 10**（5 个智能体页迁移），独立交付不产生价值。

### C1. AiFinalAnswer 流式骨架屏（原项目 #1）

**当前状态:** MVP 已 strip 报告模式 props，含 TODO(phase-3) 标记。`/ai/chat` 内 streaming 期间用 cursor `▋` 表示生成中，没有骨架屏。

**目标行为:**

- 在 `AiFinalAnswer` 中：当 `streaming && !content.length`（首字符尚未抵达）时，渲染 van-skeleton 骨架屏（3-5 行 + 1 个块状区域）
- 首字符抵达后，立即切换为正常 markdown 渲染 + cursor
- `/ai/chat` 场景中通常首字符在 100-500ms 内抵达，骨架屏几乎闪过；但智能体页等待 LLM 启动可能 ≥2s，骨架屏会有可感知存在
- 同时恢复 `isReport` / `reportTitle` / `reportMeta` props（之前 strip 的）配合 Task 10 使用

**接收条件:**

- `streaming && !content` 时骨架屏可见，平滑过渡到 markdown
- `streaming && content.length > 0` 时不显示骨架屏（避免首字符抵达后骨架与正文同时存在）
- 报告模式（`isReport=true`）下，header 与 meta 信息独立于骨架屏渲染（即使正文尚未抵达，header 也立刻可见）
- 与 MVP 的 cursor 行为不冲突

**显式依赖:** Task 10 中至少有一个智能体页落地后才完成此项的端到端验证；纯 `/ai/chat` 场景该项视觉收益小。

### C2. Artifact 链接区（原项目 #8）

**当前状态:** `NormalizedAiEvent` 已包含 `artifact` 事件（轮 2 spec 修订时恢复），`NormalizationState.artifacts` 数组也已存在。但 `/ai/chat` 后端目前不发出 artifact 事件，前端无消费点。

**目标行为:**

- 在 `AiFinalAnswer` 附近（推荐：紧贴 markdown 主体下方、actions 上方）增加 artifact 链接区
- 渲染 `artifacts: Array<{ id, title, url?, path? }>`，每个 artifact 一张小卡片：图标 + 标题 + 链接（如有 url）/ 路径标签（如有 path）
- 0 个 artifact 时该区域不渲染（不留空容器）
- 仅在以下情境消费此事件：智能体页（Task 10 集成时）+ 后端开始发出 artifact 事件后的 `/ai/chat`

**接收条件:**

- 给定测试 fixture（mock 1-3 个 artifact），UI 正确渲染
- 0 artifact 时区域完全消失
- artifact 链接点击行为：有 url 走 `target="_blank" rel="noopener"`；只有 path 时显示为可复制的代码样式标签（不导航）
- 与 `AiFinalAnswer` 视觉协调（DESIGN.md token 一致）

**显式依赖:** 后端 artifact 事件路径就绪 + Task 10 集成。在两者完成前，该项可以先实现并通过 fixture 测试，但端到端 verification 需等待。

---

## 6. 依赖与排序

```
Bundle A (零依赖)  ──→ 可立即开始
Bundle B (零依赖)  ──→ 可立即开始（与 A 并行）
Bundle C ──→ 依赖 Task 10 至少 1 个智能体页落地 + 后端 artifact 事件（C2）
```

**推荐时序:**

1. Bundle A 与 Bundle B 并行启动（无相互依赖）
2. Bundle A 中 A1（SVG asset）等设计资产，A2/A3 不依赖资产
3. Bundle B 中 B1/B3（审计）先行，B2（Markdown bubble）需要安全评审
4. Bundle C 在 Task 10 plan 启动后才进入实现；之前可写代码但无法端到端验证

**plan 拆分建议:**

- `docs/superpowers/plans/2026-XX-XX-ai-viz-bundle-a-process-polish.md`
- `docs/superpowers/plans/2026-XX-XX-ai-viz-bundle-b-chat-ux.md`
- `docs/superpowers/plans/2026-XX-XX-ai-viz-bundle-c-agent-coupling.md`（与 Task 10 plan 同步或后置）

---

## 7. 全局接收条件

- Phase 3 完整交付后，spec §2.1 / §2.2 / §3.0 / §6.1 中所有 Phase 3 标注的条目状态变为 "shipped" 或 "verified, no code change"
- plan Deferred section（轮 3 "From 2026-05-25 review (round 3)"）的 10 项中，至少 8 项被消化（剩余 2 项："MVP boundary" / "History replay" 与 Task 10 主体一起处理，不在本次范围）
- 工程质量保持 MVP 标准：i18n 覆盖、emoji prefix（toast/error）、CSS variables、DESIGN.md 4/8 px 圆角、`@media (max-width: 768px)`、无 `as any`
- B2（Markdown bubble）通过独立的 XSS 测试套件

---

## 8. 假设与开放问题

**假设:**

1. SVG 资产（A1）可在 Bundle A plan 启动前就绪。否则 A1 单独跳过，A2/A3 仍可上线。
2. 后端会在 Task 10 周期内补齐 artifact 事件发射；如果不补，C2 退化为"只有结构、无端到端消费"。
3. `/ai/chat` 当前 messages.length === 0 状态已有某种 fallback（标题 + 输入框），B3 是补强而非从零搭建。

**开放问题（不阻塞 plan 起步）:**

1. A1 的"thinking" 动效形式：脉冲 vs. 旋转 vs. 两者组合？由设计师定，工程实现支持任意 CSS keyframe。
2. B3 是否要做示例问题 chip？需要看产品同学是否愿意维护示例问题列表（i18n + 业务相关性）。
3. C2 artifact 卡片是否需要预览（如 thumbnail for image artifact）？默认不做，等真实 artifact 类型出现再加。

---

## 9. 显式排除（YAGNI 清单）

下列内容**不在 Phase 3 范围**，避免 scope creep：

- 多分支 message branch（spec §9.2 原始排除项）
- token usage 细分统计
- follow-up suggestions（"你可能还想问…"）
- subagent 复杂详情页
- tool result 富媒体预览（图表、文件预览）
- 语法高亮代码块（marked + highlight.js 集成）
- 用户消息编辑（已发出的）
- 历史会话搜索
- AI logo 品牌色系统重做
- shimmer 共享 utility 抽取（除非 C1 skeleton 也需要）

这些条目如果未来需要，发起新的 brainstorm。
