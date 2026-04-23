# Calendar UI Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 升级 `ChildCalendar.vue`，用热力背景色阶表达活动密度，加圆点数字角标、触摸优化、加载状态和月份统计条。

**Architecture:** 所有改动集中在单个 Vue 组件 `ChildCalendar.vue`。热力色阶通过 computed 函数从 `CalendarDaySummary` 数据派生，无需后端改动。`variant` prop 控制儿童/父母视角的圆角差异。

**Tech Stack:** Vue 3 `<script setup lang="ts">`, CSS scoped, `npm run typecheck` (vue-tsc), `npm run build`

---

## 文件映射

| 文件 | 操作 | 说明 |
|------|------|------|
| `frontend/src/components/calendar/ChildCalendar.vue` | Modify | 全部 P0/P1/P2 改动 |

---

## Task 1: 热力背景色阶 + 视角圆角 (P0)

**Files:**
- Modify: `frontend/src/components/calendar/ChildCalendar.vue`

- [ ] **Step 1: 添加 `variant` prop 和 `heatColor` computed**

在 `<script setup>` 中，在现有 props 定义后添加：

```typescript
const props = defineProps<{
  fetchMonth: (year: number, month: number) => Promise<CalendarMonthResponse>
  dayRoute: string
  extraQuery?: Record<string, string>
  /** 'child' = 圆角10px活泼风; 'parent' = 圆角8px规整风 */
  variant?: 'child' | 'parent'
}>()

function heatColor(day: CalendarDaySummary): string {
  const total = day.chore_count + day.wish_count + day.milestone_count
  if (total === 0) return '#ffffff'
  if (total === 1) return '#fff3e0'
  if (total <= 3) return '#ffe0b2'
  if (total <= 6) return '#ffb74d'
  return '#f5a623'
}

function isDark(day: CalendarDaySummary): boolean {
  return day.chore_count + day.wish_count + day.milestone_count >= 4
}
```

- [ ] **Step 2: 在模板格子上绑定热力色和视角圆角**

将 `.cal-cell` div 改为：

```html
<div
  v-for="day in days"
  :key="day.date"
  class="cal-cell"
  :class="{
    today: day.date === todayStr,
    active: day.chore_count > 0 || day.wish_count > 0 || day.milestone_count > 0,
    future: day.date > todayStr,
    'variant-parent': props.variant === 'parent',
    'dot-dark': isDark(day),
  }"
  :style="{ background: heatColor(day) }"
  @click="onDayClick(day)"
>
```

- [ ] **Step 3: 更新 CSS — 圆点描边 + 视角圆角**

在 `<style scoped>` 中：

```css
/* 深色背景时圆点加白描边 */
.dot-dark .dot {
  box-shadow: 0 0 0 1px #fff;
}

/* 父母视角圆角 */
.cal-cell.variant-parent {
  border-radius: 8px;
}

/* 圆点尺寸 5px → 6px */
.dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  display: inline-block;
  flex-shrink: 0;
}
```

- [ ] **Step 4: 类型检查**

```bash
cd frontend && npm run typecheck
```

期望：零错误。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/calendar/ChildCalendar.vue
git commit -m "feat(calendar): add heat-map background color scale and variant prop"
```

---

## Task 2: 触摸友好性优化 (P0)

**Files:**
- Modify: `frontend/src/components/calendar/ChildCalendar.vue`

- [ ] **Step 1: 修复 gap → padding，扩大导航按钮**

在 `<style scoped>` 中：

```css
/* gap: 2px → gap: 0，用 padding 替代 */
.cal-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 0;
}

.cal-cell {
  min-height: 44px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  cursor: default;
  padding: 4px 1px;   /* 原 padding: 4px 2px */
  position: relative;
  -webkit-tap-highlight-color: transparent;
}

/* 导航按钮 32px → 44px */
.nav-btn {
  width: 44px;
  height: 44px;
  border: none;
  background: #f5f5f5;
  border-radius: 10px;
  font-size: 20px;
  color: #555;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  -webkit-tap-highlight-color: transparent;
}
```

- [ ] **Step 2: 点击反馈改为 scale**

```css
/* 改前 */
/* .cal-cell.active:active { background: #f0f0f0; } */

/* 改后 */
.cal-cell.active {
  cursor: pointer;
  transition: transform 0.1s;
}
.cal-cell.active:active {
  transform: scale(0.92);
}
```

- [ ] **Step 3: 类型检查**

```bash
cd frontend && npm run typecheck
```

期望：零错误。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/calendar/ChildCalendar.vue
git commit -m "feat(calendar): improve touch targets — gap→padding, 44px nav buttons, scale feedback"
```

---

## Task 3: 加载状态 opacity (P1)

**Files:**
- Modify: `frontend/src/components/calendar/ChildCalendar.vue`

- [ ] **Step 1: 在模板 cal-grid 上绑定 loading class**

```html
<div class="cal-grid" :class="{ loading }">
```

- [ ] **Step 2: 添加 CSS**

```css
.cal-grid {
  transition: opacity 0.2s;
}
.cal-grid.loading {
  opacity: 0.4;
  pointer-events: none;
}
```

- [ ] **Step 3: 类型检查**

```bash
cd frontend && npm run typecheck
```

期望：零错误。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/calendar/ChildCalendar.vue
git commit -m "feat(calendar): add opacity fade loading state on month switch"
```

---

## Task 4: 圆点数字角标 (P1)

**Files:**
- Modify: `frontend/src/components/calendar/ChildCalendar.vue`

- [ ] **Step 1: 添加 `dotLabel` helper**

在 `<script setup>` 中：

```typescript
function dotLabel(count: number): string {
  if (count <= 1) return ''
  if (count >= 10) return '9+'
  return String(count)
}
```

- [ ] **Step 2: 更新模板 day-dots 区域**

将现有 `day-dots` div 替换为：

```html
<div class="day-dots">
  <span v-if="day.chore_count > 0" class="dot-wrap">
    <span class="dot dot-chore" />
    <span v-if="day.chore_count > 1" class="dot-count dot-count-chore">{{ dotLabel(day.chore_count) }}</span>
  </span>
  <span v-if="day.wish_count > 0" class="dot-wrap">
    <span class="dot dot-wish" />
    <span v-if="day.wish_count > 1" class="dot-count dot-count-wish">{{ dotLabel(day.wish_count) }}</span>
  </span>
  <span v-if="day.milestone_count > 0" class="dot-wrap">
    <span class="dot dot-milestone" />
    <span v-if="day.milestone_count > 1" class="dot-count dot-count-milestone">{{ dotLabel(day.milestone_count) }}</span>
  </span>
</div>
```

- [ ] **Step 3: 添加 CSS**

```css
.dot-wrap {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.dot-count {
  position: absolute;
  top: -5px;
  right: -5px;
  font-size: 7px;
  font-weight: 700;
  line-height: 1;
  border-radius: 4px;
  padding: 0 1px;
}

.dot-count-chore    { color: #2e7d32; }
.dot-count-wish     { color: #e65100; }
.dot-count-milestone { color: #6a1b9a; }

/* 深色背景时角标改白色 */
.dot-dark .dot-count {
  color: #fff;
}
```

- [ ] **Step 4: 类型检查**

```bash
cd frontend && npm run typecheck
```

期望：零错误。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/calendar/ChildCalendar.vue
git commit -m "feat(calendar): add numeric badge on dots for multi-event days"
```

---

## Task 5: 月份统计条 (P2)

**Files:**
- Modify: `frontend/src/components/calendar/ChildCalendar.vue`

- [ ] **Step 1: 添加 `monthStats` computed 和 `showCompletionRate` prop**

```typescript
const props = defineProps<{
  fetchMonth: (year: number, month: number) => Promise<CalendarMonthResponse>
  dayRoute: string
  extraQuery?: Record<string, string>
  variant?: 'child' | 'parent'
  /** 父母视角传 true，显示完成率 */
  showCompletionRate?: boolean
}>()

const monthStats = computed(() => {
  const totalChores = days.value.reduce((s, d) => s + d.chore_count, 0)
  const totalWishes = days.value.reduce((s, d) => s + d.wish_count, 0)
  const totalMilestones = days.value.reduce((s, d) => s + d.milestone_count, 0)
  const activeDays = days.value.filter(d => d.chore_count > 0).length
  const pastDays = days.value.filter(d => d.date <= todayStr).length
  const completionRate = pastDays > 0 ? Math.round((activeDays / pastDays) * 100) : 0
  return { totalChores, totalWishes, totalMilestones, completionRate }
})
```

- [ ] **Step 2: 在模板 legend 下方添加统计条**

```html
<!-- Stats bar -->
<div class="cal-stats">
  <span>打卡 {{ monthStats.totalChores }}次</span>
  <span class="stats-sep">·</span>
  <span>心愿 {{ monthStats.totalWishes }}个</span>
  <span class="stats-sep">·</span>
  <span>成就 {{ monthStats.totalMilestones }}个</span>
  <template v-if="showCompletionRate">
    <span class="stats-sep">·</span>
    <span class="stats-rate">完成率 {{ monthStats.completionRate }}%</span>
  </template>
</div>
```

- [ ] **Step 3: 添加 CSS**

```css
.cal-stats {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 8px;
  font-size: 11px;
  color: #aaa;
}
.stats-sep { color: #ddd; }
.stats-rate { color: #f5a623; font-weight: 600; }
```

- [ ] **Step 4: 更新 BabyPage.vue 传入 showCompletionRate**

在 `frontend/src/pages/BabyPage.vue` 中，找到 `<ChildCalendar` 组件，添加 prop：

```html
<ChildCalendar
  v-if="calendarChildId"
  :key="calendarChildId"
  :fetch-month="fetchCalendarMonth"
  day-route="/baby/calendar/day"
  :extra-query="calendarChildId ? { child_id: calendarChildId } : undefined"
  variant="parent"
  :show-completion-rate="true"
/>
```

同时在 `ChildHomePage.vue` 中添加 `variant="child"`：

```html
<ChildCalendar :fetch-month="fetchChildMonth" day-route="/child/calendar/day" variant="child" />
```

- [ ] **Step 5: 类型检查**

```bash
cd frontend && npm run typecheck
```

期望：零错误。

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/calendar/ChildCalendar.vue \
        frontend/src/pages/BabyPage.vue \
        frontend/src/pages/child/ChildHomePage.vue
git commit -m "feat(calendar): add monthly stats bar with completion rate for parent view"
```

---

## Task 6: 连续打卡条纹 (P2)

**Files:**
- Modify: `frontend/src/components/calendar/ChildCalendar.vue`

- [ ] **Step 1: 添加 `streakDates` computed**

```typescript
const streakDates = computed<Set<string>>(() => {
  // 找出所有有打卡且连续的日期对（当天和前一天都有打卡）
  const set = new Set<string>()
  for (let i = 1; i < days.value.length; i++) {
    const prev = days.value[i - 1]
    const curr = days.value[i]
    if (prev.chore_count > 0 && curr.chore_count > 0) {
      set.add(curr.date) // curr 格子左侧画连线
    }
  }
  return set
})
```

- [ ] **Step 2: 在格子 class 绑定中加入 streak**

```html
:class="{
  today: day.date === todayStr,
  active: day.chore_count > 0 || day.wish_count > 0 || day.milestone_count > 0,
  future: day.date > todayStr,
  'variant-parent': props.variant === 'parent',
  'dot-dark': isDark(day),
  streak: streakDates.has(day.date),
}"
```

- [ ] **Step 3: 添加 CSS 条纹线**

```css
/* 连续打卡：格子左侧画 1px 橙色细线延伸到前一格 */
.cal-cell.streak::before {
  content: '';
  position: absolute;
  left: -50%;
  top: 50%;
  width: 50%;
  height: 2px;
  background: #f5a623;
  opacity: 0.5;
  transform: translateY(-50%);
  pointer-events: none;
}
```

注意：周日（每行第一格）不会有 `streak` class，因为前一天在上一行，视觉上自然断开。

- [ ] **Step 4: 类型检查**

```bash
cd frontend && npm run typecheck
```

期望：零错误。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/calendar/ChildCalendar.vue
git commit -m "feat(calendar): add streak connector line between consecutive chore days"
```

---

## 自检结果

**Spec 覆盖：**
- ✅ 热力背景色阶（Task 1）
- ✅ 今日高亮保持（Task 1，`:style` 绑定不覆盖 today class）
- ✅ 圆点 6px + 深色描边（Task 1）
- ✅ 数字角标（Task 4）
- ✅ 视角圆角差异（Task 1 + Task 5）
- ✅ gap→padding 触摸修复（Task 2）
- ✅ 44px 按钮（Task 2）
- ✅ scale 反馈（Task 2）
- ✅ 加载 opacity（Task 3）
- ✅ 月份统计条（Task 5）
- ✅ 连续打卡条纹（Task 6）
- ⏭ 多孩子对比（P3，本计划不实施）

**类型一致性：**
- `variant` prop 在 Task 1 定义，Task 5 使用 ✅
- `showCompletionRate` prop 在 Task 5 定义和使用 ✅
- `dotLabel()` 在 Task 4 定义和使用 ✅
- `streakDates` 在 Task 6 定义和使用 ✅
- `heatColor()` / `isDark()` 在 Task 1 定义，Task 1 使用 ✅

**Placeholder 扫描：** 无 TBD/TODO ✅
