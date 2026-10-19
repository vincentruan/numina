# Area 19 — Learning OS optimization (智能推荐 + 双轨审核 + 预设路径 + DNA图谱)

Shared conventions in [`_common.md`](../../_common.md).

> **Why this area exists:** Branch `feat/learning-os-optimization` transforms
> Learning OS from "parent manually drives everything" to "system recommends +
> AI auto-assesses + parent asynchronously supervises." This area verifies the
> **new** surfaces and the **config → use → analyze** closed loop.
>
> Key changes:
> - BabyLearningPage restructured as modular learning hub (5 collapsible modules)
> - Smart recommendation engine (breakpoint + curriculum gap + review due)
> - Preset curriculum paths library (PresetPathsPage)
> - DNA 2D knowledge graph (SVG spiral layout, replaces old list view)
> - AI dual-track review (auto-pass ≥ 0.8 + parent override + circuit breaker)
> - Child app: source tags, review-due priority, rejection feedback
> - Deprecated pages removed (LearningAssignPage / LearningReviewsPage / LearningPathsPage)
>
> Area 16/17/18 remain for base feature coverage. Area 19 focuses on the
> **optimization delta** — what changed or is new.

Auth: adult session (`$SID`) for C19.1–C19.15; child session (`$SID_CHILD`) for
C19.16–C19.22. Routes under `${BASE}` (adult) and `${CHILD_BASE}` (child).

**Prerequisites:**
- `demouser` family has ≥1 child with learning data (progress, sessions).
- DB seeded with Beijing taxonomy topics + curriculum standards.
- **Preset paths seeded** — run `cd server && uv run python scripts/seed_preset_paths.py` (generates 60 paths across grades 1-6).
- **Alembic migrations applied** — run `cd server/apps/backend && uv run alembic upgrade head` (creates `preset_learning_paths` table + override fields).
- AI provider enabled for dual-track cases (C19.15–C19.18). If not enabled,
  mark as `SKIP-AI`.
- **Data dependencies per case:** Cases requiring learning progress (C19.3,
  C19.11, C19.13, C19.14, C19.19, C19.21) or AI assessments (C19.15–C19.18)
  should be marked `SKIP-DATA` or `SKIP-AI` when seed data is insufficient —
  NOT as FAIL.

---

## Part A: Parent Configuration Flow (配置)

### C19.1 BabyLearningPage — modular hub restructure

> Verify the page restructure: 5 modules (推荐 / 审核 / 课程路径库 / 进行中路径 / 图谱),
> high-frequency modules (推荐, 审核) default expanded, low-frequency default collapsed.

```
bsk navigate ${BASE}baby/learning --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c19.1-hub-restructure.png
```

Assertions:
- [ ] Page loads without errors
- [ ] Child switcher visible (大宝/小宝 tabs or dropdown) — reads from `useBabyStore.selectedChildId`
- [ ] 🌟 智能推荐路径 module is present and **default expanded**
- [ ] 📋 待审核 module is present and **default expanded** (or shows count badge)
- [ ] 📚 课程路径库 module is present and **default collapsed** (summary shows "N条可用路径")
- [ ] 📍 进行中的路径 module is present and **default collapsed** (summary shows path progress)
- [ ] 🧬 知识结构图谱 module is present and **default collapsed** (shows thumbnail preview)
- [ ] 🔒 parent-only marker visible on audit section
- [ ] Old "查看地图" / "派发任务" per-child cards are GONE (replaced by hub modules)
- [ ] `[console]` zero errors

### C19.2 Smart recommendation module — rendered with topic tags

> Verify recommendation module shows AI-generated recommendation path.

```
# Observe the expanded recommendation module
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c19.2-recommendations.png
```

Assertions:
- [ ] Summary line shows count: "系统为 {child} 推荐 N 个知识点"
- [ ] Reason breakdown shown: e.g. "基于: N个知识断点 + N个课标必会 + N个待复习"
- [ ] Topic tags visible with reason emoji: 🔗 (知识断点) / 📚 (课标必会) / 🔄 (需要复习) / ⭐ (高基础度)
- [ ] Each topic tag shows topic name
- [ ] [确认派发] button present
- [ ] [微调路径] button present → navigates to `/baby/learning/recommendations`
- [ ] [换一批] button present
- [ ] If no recommendations: empty state "还没有学习数据，先去知识地图探索吧！" with guidance button
- [ ] `[console]` zero errors

### C19.3 Recommendation — verify via API

> Cross-check UI against API response to ensure data consistency.
> **Data dependency:** Requires child with learning progress records.
> If API returns NOT_FOUND or empty topics → mark `SKIP-DATA` (not FAIL).

```bash
# Use the adult token from Phase 1.5 gate
RECS=$(curl -s -H "$AUTH" "${API_BASE}/family/learning/children/{child_id}/recommendations")
echo "$RECS" | jq '.data.path.topics[:5] | .[] | {topic_name, reasons}'
```

Assertions:
- [ ] API returns `path.topics` array with ≥0 items (or NOT_FOUND if no data → SKIP-DATA)
- [ ] Each topic has `topic_id` (string — Snowflake), `topic_name`, `reasons` (array), `centrality`, `prerequisites_met`, `suggested_position`
- [ ] Topics sorted by priority: 知识断点 before 课标必会 before 需要复习
- [ ] Topics with multiple reasons have merged labels (e.g. `["知识断点", "课标必会"]`)
- [ ] `[console]` zero errors

### C19.4 PresetPathsPage — filter + assign

> Verify preset curriculum path library. **Requires:** `preset_learning_paths`
> table exists (Alembic migration applied) + seed script run.

```
# Navigate to PresetPathsPage
bsk navigate ${BASE}baby/learning/preset-paths --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c19.4-preset-paths.png
```

Assertions:
- [ ] Page loads without errors
- [ ] Filter chips present: grade (年级 1-6) → semester (学期 fall/spring) → subject (学科 math/chinese/english/science)
- [ ] At least one preset path card visible after selecting a grade (e.g. Grade 3 Math has paths from seed)
- [ ] Each card shows: subject icon + path name + topic count + mastery progress
- [ ] Click card → expands topic list preview + [一键派发] button
- [ ] Empty filter result (e.g. Grade 6 with no data) → "该年级暂无预设路径" shown
- [ ] If table missing (migration not applied) → mark `SKIP-INFRA`, NOT FAIL
- [ ] `[console]` zero errors

### C19.5 PresetPathsPage — one-click assign

> Verify assigning a preset path creates a learning path for the child.

```
# Click on a preset path card to expand
bsk snapshot --session <id>
bsk click @eN --session <id>   # expand card
bsk wait-ms --session <id> 1000
bsk snapshot --session <id>
# Click [一键派发]
bsk click @eN --session <id>   # assign button
bsk wait-ms --session <id> 2000
bsk snapshot --session <id>
```

Assertions:
- [ ] Assign succeeds (toast "已派发" or redirect to BabyLearningPage)
- [ ] Verify via API: learning path created for the child
- [ ] Back on BabyLearningPage, "进行中的路径" module shows the new path
- [ ] `[console]` zero errors

### C19.6 RecommendationsPage — fine-tune path

> Verify the recommendation detail page for drag-sort, remove, replace.

```
# Navigate from BabyLearningPage [微调路径] button
bsk navigate ${BASE}baby/learning/recommendations --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c19.6-recommendations-page.png
```

Assertions:
- [ ] Page loads with recommended topics as cards
- [ ] Each card shows: reason emoji + topic name + centrality indicator
- [ ] Swipe left on a card → [移除] button appears
- [ ] Click a card → alternative topics shown (same dimension replacement)
- [ ] [从知识图谱添加] button at bottom → navigates to DNA graph
- [ ] [确认派发] button at top → creates assignments for all topics in order
- [ ] `[console]` zero errors

### C19.7 DNA 2D knowledge graph — rendered in ChildLearningMapPage

> Verify the DNA graph renders as SVG spiral (not placeholder).
> **Note:** BabyLearningPage embeds a thumbnail preview via `DnaGraph2D` component.
> Full-screen mode navigates to `/baby/learning/:childId/map`.

```
# Navigate to child's learning map (parent view)
bsk navigate ${BASE}baby/learning --session <id> --wait-until networkidle
bsk snapshot --session <id>
# Click the DNA graph module's [展开] to expand the thumbnail preview
bsk click @eN --session <id>   # expand DNA graph module
bsk wait-for --session <id> --text "数学" --timeout 5000
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c19.7-dna-graph.png
```

Assertions:
- [ ] DNA 2D graph renders as SVG (spiral layout) — NOT "知识图谱预览即将上线" placeholder
- [ ] Subject filter chips visible (数学 / 语文 / 英语 / 科学 etc.)
- [ ] Nodes colored by subject (math=blue, chinese=red, english=green, science=purple)
- [ ] Mastery visualization:
  - Mastered: bright solid + glow effect
  - Learning: pulse animation
  - Available: semi-transparent
  - Locked: dark, faded
  - Review: yellow blink
- [ ] Legend visible (can toggle)
- [ ] Click a node → bottom sheet with topic detail + action buttons
- [ ] Action buttons: "查看详情" / "添加到路径" / "直接派发" / "查看前置"
- [ ] [全屏] button → navigates to `/baby/learning/:childId/map`
- [ ] Empty state (no data): `EmptyState` with "learning.noGraphData" i18n key
- [ ] `[console]` zero errors

### C19.8 Deprecated pages — removed

> Verify old pages are no longer accessible.

```
# Attempt to navigate to deleted routes
bsk navigate ${BASE}baby/learning/assign --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] `/baby/learning/assign` → 404 or redirect (page deleted)
- [ ] `/baby/learning/reviews` → 404 or redirect (merged into BabyLearningPage)
- [ ] `/baby/learning/paths` → 404 or redirect (merged into BabyLearningPage)
- [ ] `[console]` zero errors (no dangling route warnings)

### C19.9 useBabyStore — child selection persists across navigation

> Verify child selection state is carried from BabyPage to BabyLearningPage.
> **Note:** BabyLearningPage should show which child's data is being viewed.

```
# Navigate to BabyPage, select a specific child
bsk navigate ${BASE}baby --session <id> --wait-until networkidle
bsk snapshot --session <id>
# Click on second child tab (if multiple children)
bsk click @eN --session <id>   # child tab
bsk wait-ms --session <id> 500
# Navigate to BabyLearningPage
bsk navigate ${BASE}baby/learning --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] BabyLearningPage shows the same child that was selected on BabyPage
- [ ] **Child indicator visible** — page header or module area shows selected child's name (e.g. "大宝的学习" or child name in header)
- [ ] No child selector "select child" prompt if child was already selected
- [ ] Switching child on BabyLearningPage updates all modules (independent loading)
- [ ] Each module shows skeleton during reload, old data visible until new data arrives
- [ ] `[console]` zero errors

---

## Part B: Child Usage Flow (使用)

### C19.10 TodayLearningCard — source tag display

> Verify source tags show task origin: 🌟 系统推荐 / 📝 爸妈布置 / 🔍 自己探索

```
# Use child session
bsk navigate ${CHILD_BASE} --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c19.10-source-tag.png
```

Assertions:
- [ ] TodayLearningCard shows a source tag when assignment has `assignment_type`:
  - `self_selected` → "🔍 自己探索"
  - path name includes "智能推荐" → "🌟 系统推荐"
  - `parent_assigned` → "📝 爸妈布置"
- [ ] Source tag uses correct van-tag type (color coding)
- [ ] Tag only shows when displayMode indicates an active assignment (not in explore/fallback mode)
- [ ] `[console]` zero errors

### C19.11 TodayLearningCard — review_due priority

> Verify review_due appears between pending_assignment and current_topic in priority.

```
# Check the TodayLearningCard display mode
bsk snapshot --session <id>
```

Assertions:
- [ ] If `review_due_topic` exists (mastered + next_review_at ≤ now): card shows "🔄 需要复习: {topic_name}"
- [ ] Priority order verified: pending_assignment > review_due > current_topic > recommended_topic > fallback
- [ ] review_due card navigates to the topic for review
- [ ] `[console]` zero errors

### C19.12 Knowledge map — source badges + review-due pulse + rejection markers

> Verify the child learning map shows the new visual indicators.

```
bsk navigate ${CHILD_BASE}learning --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c19.12-map-markers.png
```

Assertions:
- [ ] Topic nodes with parent-assigned work show a source badge (📝 corner badge)
- [ ] Topic nodes that are system-recommended show star badge (🌟)
- [ ] Review-due topics (mastered + next_review_at ≤ now) show yellow pulse marker
- [ ] Rejected topics (after failed assessment) show red dashed border + exclamation icon
- [ ] All markers are visible at 375px viewport without overlap
- [ ] `[console]` zero errors

### C19.13 Rejection feedback on TodayLearningCard

> Verify rejection feedback shows weakness + relearn button.

> **前置:** Child has at least one rejected topic (mastery_level = "learning" after
> assessment failure, or parent_review rejected).

```
# Navigate to child home where rejection is shown
bsk navigate ${CHILD_BASE} --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] If rejected topic exists: TodayLearningCard shows "❌ 需重学" status
- [ ] Weakness summary text shown (from AI evaluation JSON or parent feedback)
- [ ] [重新学习] button navigates to topic session
- [ ] [去练习场] button navigates to practice
- [ ] `[console]` zero errors

### C19.14 Topic detail — rejection banner

> Verify rejection feedback on the topic detail page.

```
# Navigate to a rejected topic
bsk navigate ${CHILD_BASE}learning/topic/<rejected_topic_id> --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c19.14-rejection-banner.png
```

Assertions:
- [ ] Top banner shows weakness points (薄弱点)
- [ ] [重新学习] button visible
- [ ] [去练习场] button visible
- [ ] Normal topic content (description, prerequisites) still visible below banner
- [ ] `[console]` zero errors

---

## Part C: Parent Analysis Flow (分析)

### C19.15 AI dual-track review — auto-pass results in learning activity

> Verify AI auto-pass (score ≥ 0.8) shows in the parent's review section.

> **Requires AI enabled.** Mark `SKIP-AI` if not configured.

```
# After child completes a learning session that AI auto-passed:
bsk navigate ${BASE}baby/learning --session <id> --wait-until networkidle
bsk snapshot --session <id>
# Find the review/学习动态 section
bsk click @eN --session <id>   # expand if needed
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c19.15-auto-pass.png
```

Assertions:
- [ ] Review section shows recent AI assessment results
- [ ] Auto-passed items show "✅ 已通过 (AI评估)" with score
- [ ] Items with score < 0.8 show "❌ 建议重学" with weakness points
- [ ] [展开证据] button opens bottom sheet (van-popup position=bottom)
- [ ] Evidence panel shows: AI评分详情 / 薄弱点分析 / 建议重学知识点 / 推荐练习题
- [ ] Short learning (<3 min) auto-passed items marked "需关注"
- [ ] `[console]` zero errors

### C19.16 Parent override — override AI pass to reject

> Verify parent can downgrade an AI auto-pass.

```
# Click [展开证据] on an auto-passed item
bsk snapshot --session <id>
bsk click @eN --session <id>   # expand evidence
bsk wait-ms --session <id> 1000
bsk snapshot --session <id>
# Click [覆盖为需重学] or similar override button
bsk click @eN --session <id>   # override button
bsk wait-ms --session <id> 2000
bsk snapshot --session <id>
```

Assertions:
- [ ] Override button available on AI-assessed items
- [ ] After override, status changes from "已通过" to "需重学"
- [ ] Override reason can be entered (optional text field)
- [ ] `overridden_by` recorded (parent user_id)
- [ ] `overridden_at` timestamp recorded
- [ ] Child sees the rejection feedback (verify on child side)
- [ ] `[console]` zero errors

### C19.17 Parent override — override AI reject to pass

> Verify parent can upgrade an AI rejection.

```
# Find an AI-rejected item
bsk navigate ${BASE}baby/learning --session <id> --wait-until networkidle
bsk snapshot --session <id>
# Click expand on a rejected item
bsk click @eN --session <id>
bsk wait-ms --session <id> 1000
bsk snapshot --session <id>
# Override to pass
bsk click @eN --session <id>   # [覆盖为通过]
bsk wait-ms --session <id> 2000
bsk snapshot --session <id>
```

Assertions:
- [ ] Override button available on AI-rejected items
- [ ] After override, status changes from "建议重学" to "已通过"
- [ ] Coin reward triggered (child balance increases)
- [ ] `[console]` zero errors

### C19.18 Circuit breaker — 5 consecutive overrides pause AI auto-pass

> Verify the consecutive override counter triggers the circuit breaker.

> This is a state-dependent test. If the counter is already at N, note it.
> To test from scratch, reset via API if available.

```bash
# Check current circuit breaker status
curl -s -H "$AUTH" "${API_BASE}/family/learning/children/{child_id}/ai-review-status" | jq '.'
```

Assertions:
- [ ] API returns `ai_auto_pass_paused: bool` and `consecutive_overrides: int`
- [ ] After 5 consecutive overrides, `ai_auto_pass_paused` becomes `true`
- [ ] When paused, new AI assessments go to `parent_review` instead of auto-pass
- [ ] Parent notification appears: "AI 评估可能需要调整"
- [ ] Parent can manually re-enable via `/children/{child_id}/ai-review-resume` API
- [ ] `[console]` zero errors

### C19.19 Self-exploration tracking — "自主探索" section

> Verify parent can see child's self-selected learning in BabyLearningPage.

```
# Navigate to BabyLearningPage
bsk navigate ${BASE}baby/learning --session <id> --wait-until networkidle
bsk snapshot --session <id>
# Look for 自主探索 section or similar
```

Assertions:
- [ ] If child has `self_selected` assignments, a section shows self-exploration history
- [ ] Topics with `centrality ≥ 0.7` are highlighted: "孩子主动学了重要知识点"
- [ ] Topics with `centrality < 0.7` are shown normally without highlight
- [ ] If child has 3+ consecutive low-centrality explorations, parent is prompted: "孩子最近在探索非核心知识点，是否需要关注？"
- [ ] `[console]` zero errors

### C19.20 AI-disabled degradation — BabyLearningPage still works

> Verify BabyLearningPage modules degrade gracefully when AI is not enabled.

> **前置:** AI not enabled for the family (or temporarily disable).

```
bsk navigate ${BASE}baby/learning --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] 🌟 智能推荐路径 still visible (recommendation logic doesn't depend on AI)
- [ ] 📚 课程路径库 still visible
- [ ] 📋 待审核 shows "纯家长手动审核" mode (no AI assessment results)
- [ ] 📍 进行中的路径 still visible
- [ ] 🧬 知识结构图谱 still visible
- [ ] No error messages or blank modules
- [ ] `[console]` zero errors

---

## Part D: Cross-role Closed-loop Verification

### C19.21 End-to-end: parent assigns → child learns → parent reviews

> The full config → use → analyze loop in one flow.

```
# === CONFIG (parent) ===
# 1. Navigate to BabyLearningPage
bsk navigate ${BASE}baby/learning --session <id> --wait-until networkidle
bsk snapshot --session <id>
# 2. View recommendations → click [确认派发]
bsk click @eN --session <id>   # confirm assign on recommendation
bsk wait-ms --session <id> 2000
bsk snapshot --session <id>

# === USE (child) ===
# 3. Switch to child session
# (child session should already be established from G0)
bsk navigate ${CHILD_BASE} --session <id> --wait-until networkidle
bsk snapshot --session <id>
# 4. Verify TodayLearningCard shows the assigned topic with source tag
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c19.21-e2e-child.png
# 5. Navigate to the topic and start learning
bsk navigate ${CHILD_BASE}learning --session <id> --wait-until networkidle
bsk snapshot --session <id>
# (Full learning session is time-consuming — verify topic is accessible)

# === ANALYZE (parent) ===
# 6. Return to parent session
bsk navigate ${BASE}baby/learning --session <id> --wait-until networkidle
bsk snapshot --session <id>
# 7. Verify review section shows the child's activity
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c19.21-e2e-parent.png
```

Assertions:
- [ ] Parent can see recommendations and assign with one click
- [ ] Child sees the assignment with "📝 爸妈布置" or "🌟 系统推荐" source tag
- [ ] Child can navigate to the assigned topic from TodayLearningCard
- [ ] Parent's review section reflects the child's latest activity
- [ ] The loop is coherent: no data lost between roles
- [ ] `[console]` zero errors

### C19.22 Preset path assign → child sees → parent tracks

> Verify the preset path lifecycle.

```
# === CONFIG (parent) ===
# 1. Go to PresetPathsPage, assign a path
bsk navigate ${BASE}baby/learning/preset-paths --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk click @eN --session <id>   # select a path
bsk wait-ms --session <id> 500
bsk click @eN --session <id>   # assign button
bsk wait-ms --session <id> 2000
bsk snapshot --session <id>

# === USE (child) ===
# 2. Child sees the path topics in order
bsk navigate ${CHILD_BASE}learning --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c19.22-preset-child.png

# === ANALYZE (parent) ===
# 3. Parent sees path progress in BabyLearningPage
bsk navigate ${BASE}baby/learning --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk click @eN --session <id>   # expand 进行中的路径
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c19.22-preset-parent.png
```

Assertions:
- [ ] Preset path assigned successfully
- [ ] Child's knowledge map shows path topics in prerequisite order
- [ ] Parent's "进行中的路径" shows path with progress (0/N initially)
- [ ] Path progress updates as child completes topics
- [ ] `[console]` zero errors

---

## Quick Reference

| Case | Feature | Route | Role | Key assertion |
|------|---------|-------|------|---------------|
| C19.1 | Hub restructure | `/baby/learning` | adult | 5 modules, correct expand/collapse |
| C19.2 | Recommendation module | `/baby/learning` | adult | Topic tags with reason emoji |
| C19.3 | Recommendation API | API | — | Priority sort + merged labels |
| C19.4 | PresetPathsPage | `/baby/learning/preset-paths` | adult | Filter chips + path cards |
| C19.5 | Preset assign | `/baby/learning/preset-paths` | adult | One-click creates learning path |
| C19.6 | RecommendationsPage | `/baby/learning/recommendations` | adult | Swipe-remove + replace + confirm |
| C19.7 | DNA 2D graph | `/baby/learning/:childId/map` | adult | SVG spiral + mastery colors |
| C19.8 | Deprecated pages | old routes | adult | 404 or redirect |
| C19.9 | useBabyStore | navigation | adult | Child selection persists |
| C19.10 | Source tag | `/` (ChildHome) | child | 🌟/📝/🔍 based on assignment_type |
| C19.11 | Review-due priority | `/` (ChildHome) | child | review_due between pending & current |
| C19.12 | Map markers | `/learning` | child | Source badges + pulse + rejection |
| C19.13 | Rejection card | `/` (ChildHome) | child | ❌ 需重学 + weakness + buttons |
| C19.14 | Rejection banner | `/learning/topic/:id` | child | Weakness + relearn + practice |
| C19.15 | AI auto-pass | `/baby/learning` | adult | Assessment results in review section |
| C19.16 | Override pass→reject | `/baby/learning` | adult | Downgrade AI pass |
| C19.17 | Override reject→pass | `/baby/learning` | adult | Upgrade AI reject |
| C19.18 | Circuit breaker | API | — | 5 overrides pause AI auto-pass |
| C19.19 | Self-exploration | `/baby/learning` | adult | Track self_selected + centrality |
| C19.20 | AI-disabled degrade | `/baby/learning` | adult | All modules work without AI |
| C19.21 | E2E closed loop | multi | both | Assign → learn → review coherence |
| C19.22 | Preset path lifecycle | multi | both | Preset assign → child see → parent track |
