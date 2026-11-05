# Area 17 — Learning OS core flows (child app)

Shared conventions in [`_common.md`](../../_common.md).

> **Why this area exists:** Area 16 covers taxonomy localization (curriculum
> badges, edge-status chips, locale filtering). This area covers the **core
> learning experience** on the child app: knowledge map navigation, topic
> detail, AI tutor session, learning progress, the "today learning" card on
> ChildHomePage, and self-selected learning with difficulty warnings.
>
> These cases verify the end-to-end child learning journey described in the
> design spec's "典型学习旅程" walkthrough.

Auth: child session (`$SID_CHILD`). Routes under `${CHILD_BASE}`.

**Prerequisites:**
- DB seeded with learning topics (Beijing taxonomy for zh-CN child).
- At least one child with some `learning_progress` records (topics in various
  mastery states: locked, available, learning, mastered).
- AI provider enabled for AI session cases (C17.5–C17.8). If AI is not
  enabled, mark those cases as `SKIP-AI`.

---

## Knowledge map (LearningMapPage)

### C17.1 Learning map — subject tabs + domain groups rendered

```
bsk navigate ${CHILD_BASE}learning --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c17.1-learning-map.png
```

Assertions:
- [ ] Page loads without errors (HTTP 200, no console errors)
- [ ] Subject tab bar renders with at least one subject tab visible (e.g. 数学, 科学, 语文)
- [ ] Tabs use horizontal scroll (van-tabs swipeable) — not all subjects visible at once on 375px
- [ ] Each visible subject tab shows a count badge (e.g. `数学 (5)`) — the count is the number of available topics
- [ ] Default selected tab is the subject with the most available topics (not necessarily the first alphabetically)
- [ ] Below the tab bar, domain groups render as card sections (e.g. "📐 分数 (3/5 已掌握)")
- [ ] Each domain group shows a progress indicator (mastered/total)
- [ ] Topic nodes render as grid items within each domain group
- [ ] Topic nodes show mastery status icon: ✅ available, 🔵 learning, ⭐ mastered, 🔒 locked, 🟡 review
- [ ] Empty subjects (no available/learning/mastered topics for this child) are hidden — not shown as empty tabs
- [ ] `[console]` zero errors

### C17.2 Learning map — topic node navigation

```
# From the learning map, click on an available (unlocked) topic node
bsk snapshot --session <id>
# Find an available topic node (@eN) and click it
bsk click @eN --session <id>
bsk wait-for --session <id> --text "开始学习"
bsk snapshot --session <id>
```

Assertions:
- [ ] Clicking a topic node navigates to `/learning/topic/<id>`
- [ ] URL changes to the topic detail page
- [ ] `[console]` zero errors

### C17.3 Learning map — empty state (first-time user)

> **前置:** Child with no learning progress records. If demouser's child already
> has progress, this case may show content — note in report and skip gracefully.

```
# If testing with a child that has no progress:
bsk navigate ${CHILD_BASE}learning --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] Empty state shows "🎉 开始你的学习之旅！" or similar onboarding text
- [ ] A guidance button is present (e.g. "去选择学科" or "让家长指派任务")
- [ ] No error state or blank page
- [ ] `[console]` zero errors

### C17.4 Learning map — loading skeleton

> Verify skeleton renders during data fetch. Use network throttling or observe
> the initial render.

```
# Navigate with slow network or observe the initial flash
bsk navigate ${CHILD_BASE}learning --session <id>
# Immediately snapshot before data loads
bsk snapshot --session <id>
```

Assertions:
- [ ] Skeleton placeholders render for domain groups (van-skeleton or similar)
- [ ] Skeleton transitions to real content within 3 seconds (on local dev)
- [ ] No layout shift after content loads (skeleton → content uses same grid layout)

---

## Topic detail (LearningTopicPage)

### C17.5 Topic detail — description + mastery progress + prerequisites

```
# Navigate to a topic the child has started learning (mastery_level = "learning")
bsk navigate ${CHILD_BASE}learning/topic/<learning_topic_id> --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c17.5-topic-detail.png
```

Assertions:
- [ ] Topic title renders (name_zh for zh-CN, or name fallback)
- [ ] Breadcrumb shows subject > domain (e.g. "数学 > 分数")
- [ ] Mastery progress bar renders with correct percentage (mastery_score × 100%)
- [ ] Mastery status label matches the state (e.g. "学习中", "已掌握", "待学习")
- [ ] Description section renders (description_zh preferred, English fallback)
- [ ] Prerequisites section ("前置知识") renders with at least one prerequisite topic chip
- [ ] Prerequisite chips show mastery icon: ✅ mastered, 🔓 available, 🔒 locked
- [ ] Next-steps section ("解锁后" / "后续") renders with dependent topic chips
- [ ] "[ 🎓 开始学习 ]" button is visible when mastery_level is "available" or "learning"
- [ ] "[ 📝 提交审核 ]" button is visible when mastery_level is "learning" (parent_review path)
- [ ] `[console]` zero errors

### C17.6 Topic detail — locked topic (prerequisites not met)

```
# Navigate to a locked topic (hard prerequisite not mastered)
bsk navigate ${CHILD_BASE}learning/topic/<locked_topic_id> --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] Topic title and description render normally
- [ ] Mastery status shows "未解锁" or "🔒" icon
- [ ] Prerequisites section shows which prerequisites are NOT yet mastered (🔒 icon on unmet prereqs)
- [ ] "开始学习" button is NOT visible (or is disabled) — locked topics cannot be started
- [ ] `[console]` zero errors

### C17.7 Topic detail — mastered topic

```
# Navigate to a mastered topic
bsk navigate ${CHILD_BASE}learning/topic/<mastered_topic_id> --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] Mastery progress bar shows 100% (or full)
- [ ] Status shows "已掌握" / "⭐"
- [ ] "开始学习" button is replaced with a review/continue option or is hidden
- [ ] Evidence list (学习目标) is visible — what the child has demonstrated mastery of
- [ ] `[console]` zero errors

---

## AI tutor session (LearningSessionPage)

> **Requires AI provider enabled.** If not enabled, mark as `SKIP-AI`.

### C17.8 AI session — tutorial mode (chat UI + streaming)

```
# Start a learning session for an available topic
# First navigate to topic detail, then click "开始学习"
bsk navigate ${CHILD_BASE}learning/topic/<available_topic_id> --session <id> --wait-until networkidle
bsk snapshot --session <id>
# Click "开始学习" button
bsk click @eN --session <id>   # @eN = the 开始学习 button
# Wait for session page to load
bsk wait-for --session <id> --text "学习模式" --timeout 10000
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c17.8-ai-session.png
```

Assertions:
- [ ] LearningSessionPage loads with blue header indicating tutorial mode
- [ ] AI greeting message appears (mentions child's name, e.g. "嗨 {name}！")
- [ ] AI message content relates to the topic being studied
- [ ] Chat input field is visible at the bottom — child can type responses
- [ ] Messages render in chat bubble style (AI left, child right)
- [ ] Streaming works — AI text appears incrementally (not all at once after long delay)
- [ ] Page title/header shows the topic name
- [ ] `[console]` zero errors

### C17.9 AI session — child can send messages

```
# Type a response in the chat input
bsk snapshot --session <id>
bsk fill @eN --session <id> --value "我觉得分数就是把披萨切开"
bsk click @eN --session <id>   # send button
# Wait for AI response
bsk wait-ms --session <id> 3000
bsk snapshot --session <id>
```

Assertions:
- [ ] Child's message appears in the chat (right-aligned bubble)
- [ ] AI responds with a relevant message (streaming)
- [ ] AI response is encouraging (growth mindset language, not "你错了")
- [ ] Input field clears after sending
- [ ] `[console]` zero errors

### C17.10 AI session — session completion

> This case requires the full tutorial + assessment cycle to complete, which
> may take significant time. If the session cannot complete within the test
> window, note partial progress and SKIP the completion assertions.

```
# After several rounds of interaction, check for session end state
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c17.10-session-complete.png
```

Assertions (when session completes):
- [ ] Completion/result screen appears (e.g. "🎉 太棒了！你完成了！")
- [ ] Score or progress indicator is shown
- [ ] Coin reward is mentioned (e.g. "+10 ⭐")
- [ ] Navigation options available: "返回地图" and/or "查看下一题"
- [ ] `[console]` zero errors

### C17.11 AI session — connection error handling

> Verify graceful handling when AI connection fails.

```
# If possible, trigger a connection failure (e.g. stop the agent service briefly)
# Or navigate to a session that was interrupted
bsk navigate ${CHILD_BASE}learning/session/<interrupted_session_id> --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] Error state shows "AI 连接超时" or similar user-friendly message
- [ ] A retry button or "选择家长审核模式" option is available
- [ ] No blank page or unhandled exception
- [ ] `[console]` zero errors (or errors are caught and displayed)

---

## Learning progress (LearningProgressPage)

### C17.12 Learning progress — mastery counts + study minutes

```
bsk navigate ${CHILD_BASE}learning/progress --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c17.12-progress.png
```

Assertions:
- [ ] Page loads without errors
- [ ] Mastery count summary shows: mastered count, learning count, available count
- [ ] Study time is displayed: total study minutes (real value from backend, NOT xp_earned proxy)
- [ ] Today's study minutes shown separately (or within the same stat row)
- [ ] If child has zero study sessions, study minutes show "0" (not null/undefined/NaN)
- [ ] `[console]` zero errors

### C17.13 Learning progress — empty state

> **前置:** Child with no learning progress at all.

```
# If testing with a child that has no progress:
bsk navigate ${CHILD_BASE}learning/progress --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] Empty state shows "还没有学习记录哦，快去学习吧！" or similar
- [ ] A navigation button/link to the learning map is present
- [ ] No blank page or error
- [ ] `[console]` zero errors

---

## Today learning card (ChildHomePage)

### C17.14 Today learning card — pending assignment display

> **前置:** Child has at least one pending learning assignment (parent-assigned).

```
bsk navigate ${CHILD_BASE} --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c17.14-today-learning.png
```

Assertions:
- [ ] TodayLearningCard is visible on ChildHomePage (after the ProgressRing section)
- [ ] If pending assignment exists: shows "📝 提交作业: {topic_name}" with topic name
- [ ] Card is clickable — navigates to `/learning/topic/{topic_id}`
- [ ] Footer shows "今日已学习 {N} 分钟" (study_minutes_today)
- [ ] Study minutes is a non-negative integer (0 when no sessions today)
- [ ] `[console]` zero errors

### C17.15 Today learning card — priority branches

> Verify the card shows the correct topic based on priority:
> pending_assignment > current_topic > recommended_topic > fallback.

```
# Observe which topic the card shows and verify priority logic
bsk snapshot --session <id>
```

Assertions:
- [ ] If pending_assignment exists → card shows pending assignment topic (not current or recommended)
- [ ] If no pending but current_topic (mastery_level="learning") exists → card shows current topic with "📖 继续学习"
- [ ] If no pending/current but recommended exists → card shows recommended with "🌟 开始新知识"
- [ ] If none exist → card shows fallback "📚 去学习地图探索" → navigates to `/learning`
- [ ] Card display matches the actual data state (verify against API response)

### C17.16 Today learning card — loading state

```
# Navigate to child home and observe the card during load
bsk navigate ${CHILD_BASE} --session <id>
bsk snapshot --session <id>
```

Assertions:
- [ ] Card has a loading skeleton or shimmer during data fetch
- [ ] Skeleton transitions to real content smoothly
- [ ] No layout shift when card content loads

---

## Self-selected learning (difficulty warning)

### C17.17 Self-selected learning — age difficulty warning

> **前置:** Child attempts to learn a topic with age_group higher than their own
> (e.g. a 8-year-old "mid" child selecting a "high" topic).

```
# Navigate to a topic that is age-inappropriate for the child
bsk navigate ${CHILD_BASE}learning/topic/<high_difficulty_topic_id> --session <id> --wait-until networkidle
bsk snapshot --session <id>
# Click "开始学习"
bsk click @eN --session <id>
bsk wait-ms --session <id> 2000
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c17.17-difficulty-warning.png
```

Assertions:
- [ ] A dialog/modal appears with age difficulty warning
- [ ] Warning text is friendly and non-blocking (e.g. "这个任务可能有点挑战")
- [ ] Warning mentions a recommended alternative topic (same subject, age-appropriate)
- [ ] Two action buttons: "继续学习这个" (continue) and "去看看推荐的" (navigate to recommended)
- [ ] Clicking "继续学习这个" proceeds to the session normally
- [ ] Clicking "去看看推荐的" navigates to the recommended topic's detail page
- [ ] `[console]` zero errors

### C17.18 Self-selected learning — prerequisite warning

> **前置:** Child selects a topic whose hard prerequisites are not all mastered.

```
# Navigate to a topic with unmet prerequisites
bsk navigate ${CHILD_BASE}learning/topic/<topic_with_unmet_prereqs> --session <id> --wait-until networkidle
bsk snapshot --session <id>
# Click "开始学习" (self-selected bypasses locked state)
bsk click @eN --session <id>
bsk wait-ms --session <id> 2000
bsk snapshot --session <id>
```

Assertions:
- [ ] A dialog/modal appears with prerequisite warning
- [ ] Warning mentions unmet prerequisites (e.g. "建议先学习: {prereq_name}")
- [ ] Warning is non-blocking — child can still choose to continue
- [ ] Action buttons: "继续学习" and "先去学前置知识"
- [ ] `[console]` zero errors

### C17.19 Self-selected learning — auto-creates self_selected assignment

> Verify that starting a self-selected topic creates an assignment record.

```
# After C17.17 or C17.18, verify via API
curl -s -H "Cookie: $CHILD_COOKIE" "${API_BASE}/child/learning/assignments" | jq '.data[] | select(.assignment_type == "self_selected")'
```

Assertions:
- [ ] A `self_selected` assignment record exists for the topic
- [ ] The assignment's `created_by` is the child's ID (self-assigned)
- [ ] `[console]` zero errors

---

## Translation button (conditional display)

### C17.20 Translation button — hidden for already-translated topics

> **前置:** zh-CN child, topic with `name_zh` already populated (pre-translated seed).

```
bsk navigate ${CHILD_BASE}learning/topic/<translated_topic_id> --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] No "翻译成中文" button visible (topic already has Chinese translation)
- [ ] Topic content displays in Chinese (name_zh, description_zh)
- [ ] `[console]` zero errors

### C17.21 Translation button — shown for untranslated topics

> **前置:** zh-CN child, topic with `name_zh` = null (untranslated).

```
bsk navigate ${CHILD_BASE}learning/topic/<untranslated_topic_id> --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] "翻译成中文" button is visible (only when `*_zh` fields are null)
- [ ] Topic content currently displays in English (fallback since `_zh` is null)
- [ ] Clicking the button initiates translation (loading state)
- [ ] `[console]` zero errors

---

## Smart Tutor — Socratic guided problem-solving (Issue #191)

> **Why this section exists:** Issue #191 新增了「智能解题」功能 — 不同于
> C17.8–C17.11 的 AI 辅导对话（topic exploration），Smart Tutor 是**题目驱动**
> 的苏格拉底式引导：child 带着具体题目进入，AI 教师通过提问引导解题，
> 而非直接给出答案。UI 包含教师头像、4 阶段引导进度条、快捷操作按钮、
> 知识桥接叠加层。
>
> 路由：`${CHILD_BASE}learning/smart-tutor/:sessionId?questionId=X&subject=math&ageGroup=mid`
> 前置：需要 child session + 有效的 learning session（含 question_id）。
> AI 必须启用；未启用则标记 `SKIP-AI`。

### C17.22 Smart Tutor — page load with teacher avatar + welcome

> 验证 SmartTutorPage 加载后渲染教师头像和欢迎消息。

```
# Navigate to smart-tutor with a valid session and question
bsk navigate "${CHILD_BASE}learning/smart-tutor/<session_id>?questionId=<question_id>&subject=math&ageGroup=mid" --session <id> --wait-until networkidle
bsk wait-ms --session <id> 3000
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c17.22-smart-tutor-welcome.png
```

Assertions:
- [ ] SmartTutorPage loads without errors (HTTP 200, no console errors)
- [ ] TeacherAvatar component renders (teacher icon/illustration at top)
- [ ] Welcome message visible: "欢迎来到智能解题课堂！老师会一步步引导你思考，而不是直接告诉你答案。" 或类似文本
- [ ] "开始解题" button is visible and clickable
- [ ] Subject-specific persona is applied (math → 逻辑推理趣味型 for mid age)
- [ ] `[console]` zero errors

### C17.23 Smart Tutor — Socratic phase indicator (SocraticSteps)

> 验证 4 阶段引导进度条渲染并随对话推进。

```
# After starting the session and exchanging at least one message:
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c17.23-socratic-steps.png
```

Assertions:
- [ ] SocraticSteps component shows 4 phases: 诊断 → 引导 → 验证 → 巩固 (or Chinese equivalents)
- [ ] Current phase is highlighted/active
- [ ] Progress bar or step counter shows advancement (e.g. "步骤 2/5")
- [ ] Phase transitions are visible after multiple exchanges (diagnose → focused_guidance)
- [ ] `[console]` zero errors

### C17.24 Smart Tutor — child sends answer, AI responds with guidance

> 验证 child 可以在输入框提交答案，AI 以苏格拉底方式回应（不给答案，而是引导）。

```
# Type answer in the input field
bsk snapshot --session <id>
bsk fill @eN --session <id> --value "我觉得应该是 1/2"
bsk click @eN --session <id>   # send button
bsk wait-ms --session <id> 5000
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c17.24-smart-tutor-answer.png
```

Assertions:
- [ ] Child's message appears in the chat area (user bubble)
- [ ] AI responds with streaming text (incremental appearance)
- [ ] AI response does NOT directly give the answer — instead asks a guiding question or provides a hint
- [ ] Response uses age-appropriate language (matches the ageGroup persona)
- [ ] Input field clears after sending
- [ ] `[console]` zero errors

### C17.25 Smart Tutor — quick action buttons (hint/understand/more help)

> 验证 QuickActions 组件渲染三个快捷按钮。

```
bsk snapshot --session <id>
```

Assertions:
- [ ] "给个提示" button is visible and clickable
- [ ] "我理解了" button is visible and clickable
- [ ] "需要更多帮助" button is visible (may be conditional on guidance phase)
- [ ] Clicking "给个提示" sends a hint request message on behalf of the child
- [ ] AI responds to the hint request with a targeted hint (not the full answer)
- [ ] `[console]` zero errors

### C17.26 Smart Tutor — knowledge bridge overlay

> 验证知识桥接叠加层显示前置知识链和断点。

```
# After AI triggers get_knowledge_bridge (when child is stuck):
# The overlay should appear as a bottom panel
bsk wait-ms --session <id> 3000
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c17.26-knowledge-bridge.png
```

Assertions:
- [ ] KnowledgeBridgeOverlay renders when knowledge bridge data is available
- [ ] Title "知识桥接地图" is visible
- [ ] Prerequisite chain shows as nodes with color-coded mastery dots:
  - 🟢 Mastered: bright/solid
  - 🔵 Learning: pulse/semi-transparent
  - 🔒 Locked/Available: dark/faded
- [ ] Current topic is marked with "当前" badge
- [ ] If broken_link exists: red alert shows "发现知识断点：{name} 还没有掌握"
- [ ] If no bridge data: shows "暂无知识图谱数据"
- [ ] `[console]` zero errors

### C17.27 Smart Tutor — error handling (AI connection failure)

> 验证 AI 连接失败时的优雅降级。

```
# If possible, trigger a failure (e.g. agent service temporarily unavailable)
# Or navigate with an invalid/expired session
bsk navigate "${CHILD_BASE}learning/smart-tutor/invalid-session-id?questionId=999&subject=math&ageGroup=mid" --session <id> --wait-until networkidle
bsk wait-ms --session <id> 2000
bsk snapshot --session <id>
```

Assertions:
- [ ] Error toast/message shows "启动智能导师失败: {status}" or similar user-friendly text
- [ ] No blank page or unhandled exception
- [ ] A retry or back navigation option is available
- [ ] `[console]` zero errors (or errors are caught and displayed)

### C17.28 Smart Tutor — streaming + SSE protocol

> 验证 SSE 流式传输正常工作（消息增量出现，非一次性加载）。

```
# Start a fresh session and observe the streaming behavior
bsk navigate "${CHILD_BASE}learning/smart-tutor/<new_session_id>?questionId=<question_id>&subject=math&ageGroup=mid" --session <id>
# Observe the first AI message — it should appear incrementally
bsk wait-ms --session <id> 2000
bsk snapshot --session <id>
```

Assertions:
- [ ] AI greeting text appears incrementally (streaming), not after a long delay all at once
- [ ] Status indicator shows "connecting" → "streaming" → completion (via useSmartTutor composable)
- [ ] Phase tracking updates during streaming (currentPhase changes from idle to a phase name)
- [ ] Step counter increments as tutoring progresses
- [ ] `[console]` zero errors

---

## Quick Reference

| Case | Feature | Route | Key assertion |
|------|---------|-------|---------------|
| C17.1 | Learning map | `/learning` | Subject tabs + domain groups + topic nodes with mastery icons |
| C17.2 | Map navigation | `/learning` | Click topic → navigates to detail |
| C17.3 | Map empty state | `/learning` | Onboarding text + guidance button |
| C17.4 | Map skeleton | `/learning` | Skeleton → content transition |
| C17.5 | Topic detail | `/learning/topic/:id` | Progress bar + prereqs + next-steps + action buttons |
| C17.6 | Locked topic | `/learning/topic/:id` | No start button, unmet prereqs shown |
| C17.7 | Mastered topic | `/learning/topic/:id` | 100% progress, evidence list |
| C17.8 | AI tutorial | `/learning/session/:id` | Chat UI + streaming + child name greeting |
| C17.9 | AI interaction | `/learning/session/:id` | Child sends message → AI responds |
| C17.10 | Session complete | `/learning/session/:id` | Completion screen + coins |
| C17.11 | Connection error | `/learning/session/:id` | Friendly error + retry option |
| C17.12 | Progress page | `/learning/progress` | Mastery counts + real study minutes |
| C17.13 | Progress empty | `/learning/progress` | Empty state + map link |
| C17.14 | Today card | `/` (ChildHome) | Pending assignment + study minutes footer |
| C17.15 | Today card priority | `/` (ChildHome) | Correct branch based on data state |
| C17.16 | Today card loading | `/` (ChildHome) | Skeleton → content |
| C17.17 | Age warning | `/learning/topic/:id` | Non-blocking dialog + recommendation |
| C17.18 | Prereq warning | `/learning/topic/:id` | Non-blocking dialog + prereq link |
| C17.19 | Self-selected assignment | API check | `self_selected` assignment created |
| C17.20 | Translate hidden | `/learning/topic/:id` | No button for translated topics |
| C17.21 | Translate shown | `/learning/topic/:id` | Button visible for untranslated topics |
| C17.22 | Smart Tutor welcome | `/learning/smart-tutor/:id` | Teacher avatar + welcome text + start button |
| C17.23 | Socratic phases | `/learning/smart-tutor/:id` | 4-phase indicator + progress bar |
| C17.24 | Tutor answer flow | `/learning/smart-tutor/:id` | Child sends answer → AI guides (no direct answer) |
| C17.25 | Quick actions | `/learning/smart-tutor/:id` | Hint / understand / more-help buttons |
| C17.26 | Knowledge bridge | `/learning/smart-tutor/:id` | Prerequisite chain + broken link alert |
| C17.27 | Tutor error | `/learning/smart-tutor/:id` | Friendly error + retry/back option |
| C17.28 | Tutor SSE streaming | `/learning/smart-tutor/:id` | Incremental text + phase tracking |
