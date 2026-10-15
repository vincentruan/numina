# Area 18 — Learning OS parent management (main app)

Shared conventions in [`_common.md`](../../_common.md).

> **Why this area exists:** This area covers the parent-facing learning
> management features: BabyLearningPage overview, child knowledge map,
> task assignment (single + learning path), review/approval queue, and
> the BabyPage → BabyLearningPage navigation entry point.
>
> These cases verify the parent can monitor children's learning, assign
> tasks, review submissions, and create learning paths.

Auth: adult session (`$SID`) as `demouser` / `DemoPass123` (owner role).
Routes under `${BASE}` (adult SPA).

**Prerequisites:**
- `demouser` family has ≥1 child with learning data (progress, sessions).
- DB seeded with learning topics (Beijing taxonomy for zh-CN).
- AI provider enabled for cases that trigger AI assessment (C18.7).
  If AI is not enabled, mark as `SKIP-AI`.

---

## BabyPage → BabyLearningPage navigation

### C18.1 BabyPage — learning cell visible

```
bsk navigate ${BASE}baby --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c18.1-baby-learning-cell.png
```

Assertions:
- [ ] BabyPage summary section includes a learning cell (icon: `book-o`, label: "学习管理")
- [ ] Learning cell shows the child's total study minutes (from API data)
- [ ] Learning cell is clickable
- [ ] Click navigates to `/baby/learning`
- [ ] `[console]` zero errors

### C18.2 BabyLearningPage — children overview

```
bsk navigate ${BASE}baby/learning --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c18.2-baby-learning.png
```

Assertions:
- [ ] Page loads without errors
- [ ] Each child in the family is shown as a card/section
- [ ] Each child card shows: display_name, age, mastery counts (mastered/learning/available)
- [ ] "查看地图" button per child → navigates to child's knowledge map
- [ ] "派发任务" button per child → navigates to assignment page
- [ ] Pending review count shown (e.g. "📋 待审核 (2)")
- [ ] `[console]` zero errors

### C18.3 BabyLearningPage — KeepAlive caching

```
# Navigate to BabyLearning → switch to another tab → return
bsk navigate ${BASE}baby/learning --session <id> --wait-until networkidle
bsk snapshot --session <id>
# Switch to Dashboard
bsk navigate ${BASE} --session <id> --wait-until networkidle
# Return to BabyLearning
bsk navigate ${BASE}baby/learning --session <id>
bsk snapshot --session <id>
```

Assertions:
- [ ] Page state is preserved on return (no re-fetch flicker)
- [ ] Scroll position preserved (if scrolled before tab switch)
- [ ] Data is not reloaded from scratch (KeepAlive `include` has 'BabyLearning')
- [ ] `[console]` zero errors

---

## Child knowledge map (parent view)

### C18.4 ChildLearningMapPage — parent views child's map

```
# From BabyLearningPage, click "查看地图" for the first child
bsk navigate ${BASE}baby/learning --session <id> --wait-until networkidle
bsk snapshot --session <id>
# Click "查看地图" button
bsk click @eN --session <id>
bsk wait-for --session <id> --text "数学" --timeout 5000
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c18.4-child-map.png
```

Assertions:
- [ ] ChildLearningMapPage loads showing the child's knowledge map
- [ ] Subject tabs visible (same subjects as child sees, based on child's locale)
- [ ] Topic nodes show the child's mastery status (not parent's — parent is viewing child's data)
- [ ] Domain groups with progress indicators render
- [ ] Clicking a topic navigates to topic detail (parent view)
- [ ] `[console]` zero errors

### C18.5 ChildLearningMapPage — locale consistency

> Verify parent sees the same topic set their child sees (based on child's locale,
> not parent's locale).

```
# Verify the map shows topics consistent with the child's locale
bsk snapshot --session <id>
```

Assertions:
- [ ] For zh-CN child: Beijing taxonomy topics visible (语文, 道德与法治 if present)
- [ ] No deprecated topics shown
- [ ] Topic names show in the child's language (name_zh for zh-CN children)
- [ ] `[console]` zero errors

---

## Task assignment (LearningAssignPage)

### C18.6 LearningAssignPage — single task assignment

```
bsk navigate ${BASE}baby/learning/assign --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c18.6-assign-single.png
```

Assertions:
- [ ] Page loads without errors
- [ ] Child selector is present (if multiple children, can pick target child)
- [ ] Topic selector/search is visible — parent can browse available topics
- [ ] Topic list shows topic names (localized — Chinese for zh-CN parent)
- [ ] Parent can select a topic and create an assignment
- [ ] "单个任务" mode is the default (or clearly selected)
- [ ] `[console]` zero errors

### C18.7 LearningAssignPage — create assignment flow

```
# Select a child and a topic, then submit
bsk snapshot --session <id>
# Select topic from the list
bsk click @eN --session <id>   # @eN = a topic item
bsk snapshot --session <id>
# Click submit/create button
bsk click @eN --session <id>   # @eN = the submit button
bsk wait-ms --session <id> 2000
bsk snapshot --session <id>
```

Assertions:
- [ ] Assignment created successfully (success toast or redirect)
- [ ] Assignment type is `parent_assigned`
- [ ] Child receives the assignment (visible in their `/child/learning/assignments`)
- [ ] Notification may be sent to child (if notification system is wired)
- [ ] `[console]` zero errors

### C18.8 LearningAssignPage — learning path mode (if implemented)

> **前置:** Learning path feature (方案 #2) is implemented. If not yet
> implemented, mark as `SKIP-FEATURE` and note in report.

```
# Switch to "学习路径" mode
bsk navigate ${BASE}baby/learning/assign --session <id> --wait-until networkidle
bsk snapshot --session <id>
# Look for tab/toggle to switch to path mode
bsk click @eN --session <id>   # @eN = "学习路径" tab or toggle
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c18.8-assign-path.png
```

Assertions:
- [ ] "学习路径" mode is accessible via tab/toggle
- [ ] Parent can select multiple topics (checkbox selection)
- [ ] Path name input is available
- [ ] per_task_score, bonus_score inputs are visible with defaults (5, 10)
- [ ] Optional milestone configuration is available
- [ ] Preview card shows: "N 个任务 · 每个 N 分 · 里程碑: ..."
- [ ] Topics are auto-sorted by prerequisite order (topological sort)
- [ ] Submit creates the learning path
- [ ] `[console]` zero errors

---

## Review queue (LearningReviewsPage)

### C18.9 LearningReviewsPage — pending reviews list

> **前置:** At least one child has submitted a learning task for parent review
> (mastery_level = "parent_review").

```
bsk navigate ${BASE}baby/learning/reviews --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c18.9-reviews.png
```

Assertions:
- [ ] Page loads without errors
- [ ] Pending review items are listed (child name + topic name)
- [ ] Each item shows: child display_name, topic name, learning duration, attempt count
- [ ] Evidence list is visible (what the child should demonstrate)
- [ ] 💡 Parent-friendly mastery explanation shown (e.g. "您的孩子是否能独立完成以下任务？")
- [ ] 📋 Reference questions shown (2-3 questions parent can ask verbally)
- [ ] `[console]` zero errors

### C18.10 LearningReviewsPage — approve flow

```
# Click approve on a pending review item
bsk snapshot --session <id>
# May need to expand evidence details first (anti-rubber-stamp mechanism)
bsk click @eN --session <id>   # expand evidence / approve button
bsk snapshot --session <id>
# Confirm approve
bsk click @eN --session <id>   # confirm approve
bsk wait-ms --session <id> 2000
bsk snapshot --session <id>
```

Assertions:
- [ ] Approve button may require expanding evidence first (anti-rubber-stamp)
- [ ] After approval, mastery_level changes to "mastered"
- [ ] completed_via is set to "parent_approval"
- [ ] Coin reward is triggered (child's coin balance increases)
- [ ] Review item disappears from the pending list
- [ ] Success feedback shown (toast or item removal animation)
- [ ] `[console]` zero errors

### C18.11 LearningReviewsPage — reject flow

```
# Click reject on a pending review item
bsk navigate ${BASE}baby/learning/reviews --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk click @eN --session <id>   # reject button
bsk wait-ms --session <id> 2000
bsk snapshot --session <id>
```

Assertions:
- [ ] Reject button is available
- [ ] After rejection, mastery_level changes to "learning" (child must continue learning)
- [ ] Review item disappears from the pending list
- [ ] Child is notified of rejection (if notification system is wired)
- [ ] `[console]` zero errors

### C18.12 LearningReviewsPage — empty state

> **前置:** No pending reviews.

```
bsk navigate ${BASE}baby/learning/reviews --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] Empty state shows "🎉 没有待审核的任务" or similar
- [ ] No error or blank page
- [ ] `[console]` zero errors

### C18.13 LearningReviewsPage — short learning time warning

> **前置:** Child submitted for review after < 3 minutes of learning time.

```
# Find a review item with short learning duration
bsk navigate ${BASE}baby/learning/reviews --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] If learning duration < 3 min, a warning appears: "学习时长较短，建议先和孩子聊聊这个知识点"
- [ ] Warning does NOT block approve/reject — parent can still act
- [ ] `[console]` zero errors

---

## Learning path management (parent view)

> **前置:** Learning path feature (方案 #2) is implemented. If not, mark
> C18.14–C18.16 as `SKIP-FEATURE`.

### C18.14 Learning paths list

```
bsk navigate ${BASE}baby/learning --session <id> --wait-until networkidle
bsk snapshot --session <id>
# Navigate to paths list if separate, or observe paths on overview
```

Assertions:
- [ ] Active learning paths are listed per child
- [ ] Each path shows: name, progress (N/M completed), status
- [ ] Path with all items completed shows "已完成" status
- [ ] `[console]` zero errors

### C18.15 Learning path detail — parent view

```
# Click on a path to see detail
bsk click @eN --session <id>
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c18.15-path-detail.png
```

Assertions:
- [ ] Path detail shows all items with their status (pending/in_progress/completed/skipped)
- [ ] Items are in prerequisite-sorted order
- [ ] Progress bar shows completed/total
- [ ] Next milestone indicator visible (e.g. "再完成 2 个任务获得 +10 分奖励")
- [ ] Score breakdown shown: per_task + milestone + bonus
- [ ] `[console]` zero errors

### C18.16 Learning path — archive

```
# Archive a completed path
bsk snapshot --session <id>
bsk click @eN --session <id>   # archive button
bsk wait-ms --session <id> 2000
bsk snapshot --session <id>
```

Assertions:
- [ ] Archive action available for completed paths
- [ ] After archiving, path moves to archived state (no longer in active list)
- [ ] Path data is preserved (not deleted) — can view historical records
- [ ] `[console]` zero errors

---

## Quick Reference

| Case | Feature | Route | Key assertion |
|------|---------|-------|---------------|
| C18.1 | BabyPage learning cell | `/baby` | Cell visible + navigates to `/baby/learning` |
| C18.2 | BabyLearningPage | `/baby/learning` | Children overview + mastery counts + study time |
| C18.3 | KeepAlive caching | `/baby/learning` | Page state preserved across tab switch |
| C18.4 | Child map (parent) | `/baby/learning/:childId/map` | Child's mastery status visible to parent |
| C18.5 | Locale consistency | `/baby/learning/:childId/map` | Topics match child's locale |
| C18.6 | Assign page | `/baby/learning/assign` | Topic selector + child selector |
| C18.7 | Create assignment | `/baby/learning/assign` | Assignment created + child receives it |
| C18.8 | Path mode | `/baby/learning/assign` | Multi-select + score config + auto-sort |
| C18.9 | Reviews list | `/baby/learning/reviews` | Pending items + evidence + reference questions |
| C18.10 | Approve | `/baby/learning/reviews` | mastery→mastered + coin reward |
| C18.11 | Reject | `/baby/learning/reviews` | mastery→learning + item removed |
| C18.12 | Reviews empty | `/baby/learning/reviews` | "🎉 没有待审核的任务" |
| C18.13 | Short time warning | `/baby/learning/reviews` | Warning when learning < 3 min |
| C18.14 | Paths list | `/baby/learning` | Active paths + progress |
| C18.15 | Path detail | path detail page | Items sorted + progress + milestone |
| C18.16 | Path archive | path detail page | Completed path archived |
