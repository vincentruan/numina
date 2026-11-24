# Learning OS 儿童体验优化 — 实施规划

> **日期**: 2026-11-23  
> **范围**: frontend/apps/child/ — 3 个 P0 优化  
> **目标**: 降低儿童认知负荷，让行动入口首屏可见，让情感高点驱动学习闭环

---

## 背景

UX 评估发现三个 P0 问题：
1. **TopicPage 首屏** — 行动按钮需要滚动 5-6 屏才可见
2. **进度页过重** — 8 个数据面板是成人仪表盘思维，不是儿童体验
3. **Teach-Back 入口断裂** — 掌握知识的最佳教学时机（练习结果页）没有入口

---

## Task 1: TopicPage 首屏优化

**文件**: `frontend/apps/child/src/pages/learning/LearningTopicPage.vue`

### 当前布局（从上到下）

```
1. breadcrumb (返回 + 路径)
2. topic-title-row (标题 + 课标徽章)
3. curriculum-callout (课标编号)
4. mastery-section (状态 + 进度条 + 次数)
5. TopicHookQuestion (好奇钩子)
6. description-section (描述文字)
7. translate-btn (翻译按钮)
8. evidence-section (证据列表)
9. RealWorldConnections (现实连接)
10. graph-section prerequisites (前置 chips)
11. graph-section dependents (后续 chips)
12. path-context-bar (路径上下文)
13. action-buttons (4 个按钮)  ← 需要滚动到这里！
```

### 目标布局（首屏 ~667px 高度内）

```
1. breadcrumb (简化 — 只保留返回箭头)
2. topic-title-row (标题 + 课标友好标签)
3. mastery-section (进度条 — 精简)
4. TopicHookQuestion (好奇钩子 — 保留)
5. description-section (描述 — 保留)
6. ╔═══ 开始学习 ═══╗  ← CTA 首屏可见！
   ╚═════════════════╝
7. [开始练习]
8. ── 了解更多 ── (可折叠区域)
   ├ curriculum-callout
   ├ translate-btn
   ├ evidence-section
   ├ RealWorldConnections
   ├ prerequisites
   ├ dependents
   └ path-context-bar
9. [教 AI] (仅 mastered — 移到这里，从 action-buttons 独立出来)
10. [提交作业] (仅有 pending assignment 时显示)
```

### 实施细节

#### 1a. 面包屑简化

**当前**: 返回按钮 + 完整路径（学习 / 数学 / 分数）  
**优化**: 只保留返回箭头 `<` + 学科名。完整路径移到"了解更多"折叠区。

```vue
<!-- 简化面包屑 -->
<div class="top-bar">
  <button class="top-bar__back" @click="goBack" :aria-label="t('learning.backToMap')">
    <IIcon icon="lucide:chevron-left" size="20" />
  </button>
  <span class="top-bar__subject">{{ subjectLabel(topic.subject) }}</span>
</div>
```

#### 1b. 课标信息儿童友好化

**当前**: 显示 `MA.3.NF.1` 这样的编号  
**优化**: 用孩子能理解的语言，如 "三年级核心知识" / "Grade 3 Core"

```vue
<!-- 课标徽章 — 友好标签替代编号 -->
<span v-if="firstResolvedStandard" class="curriculum-tag">
  {{ curriculumFriendlyLabel(firstResolvedStandard) }}
</span>
```

新增 composable 函数 `curriculumFriendlyLabel(standard)`:
- 解析 standard.code 中的年级和学科信息
- 返回如 `t('learning.curriculum.friendlyGrade', { grade: 3 })` → "三年级核心知识"
- 详细编号移入折叠区

#### 1c. 行动按钮区域重构

```vue
<!-- 首屏 CTA — 主按钮 -->
<div class="hero-actions">
  <button class="btn-primary btn-cta" :disabled="starting" @click="onStartLearning">
    <IIcon icon="lucide:play" size="18" />
    {{ starting ? t('common.loading') : t('learning.startLearning') }}
  </button>
  <button class="btn-secondary" @click="goToPractice">
    {{ t('practice.startPractice') }}
  </button>
</div>

<!-- 教 AI — 仅 mastered 时显示，放在 CTA 下方 -->
<button
  v-if="isMastered"
  class="btn-teach-back"
  @click="goToTeachBack"
>
  🎓 {{ t('learning.teach_back.start_btn') }}
</button>
```

#### 1d. "了解更多"折叠区域

使用 van-collapse 或自定义展开/折叠。默认收起，展开后显示所有详细信息。

```vue
<!-- 了解更多 — 可折叠详细信息 -->
<div class="details-section">
  <button class="details-toggle" @click="detailsExpanded = !detailsExpanded">
    <span>{{ t('learning.learnMore') }}</span>
    <IIcon :icon="detailsExpanded ? 'lucide:chevron-up' : 'lucide:chevron-down'" size="16" />
  </button>
  <div v-show="detailsExpanded" class="details-body">
    <!-- curriculum-callout (详细编号) -->
    <!-- translate-btn -->
    <!-- evidence-section -->
    <!-- RealWorldConnections -->
    <!-- prerequisites chips -->
    <!-- dependents chips -->
    <!-- path-context-bar -->
  </div>
</div>

<!-- 提交作业 — 底部独立 -->
<button
  v-if="hasPendingAssignment"
  class="btn-secondary"
  :disabled="submitting"
  @click="onSubmitAssignment"
>
  {{ submitting ? t('common.loading') : t('learning.submitAssignment') }}
</button>
```

#### 1e. 新增 i18n keys

```typescript
// zh-CN.ts
'learning.curriculum.friendlyGrade': '{grade}年级核心知识',
'learning.learnMore': '了解更多',
'learning.submitAssignment': '提交作业',

// en-US.ts
'learning.curriculum.friendlyGrade': 'Grade {grade} Core',
'learning.learnMore': 'Learn more',
```

### 验证

- [ ] 390px 宽度首屏截图：CTA 按钮可见
- [ ] 折叠/展开动画流畅
- [ ] KeepAlive 缓存状态保持（`onActivated` 重新加载）
- [ ] Dark mode 样式正确
- [ ] 所有 i18n 键存在

---

## Task 2: 进度页儿童友好化

**文件**: `frontend/apps/child/src/pages/learning/LearningProgressPage.vue`

### 当前布局（8 个数据区域）

```
1. 页面标题 "学习进度"
2. 城堡入口卡片
3. XP/Level/Streak 区域
4. 4 个统计卡片（已掌握/学习中/可学习/待复习）
5. 学习时间（总计/今日）
6. 最近活动列表
7. 薄弱知识点列表
8. 最近练习会话列表
```

### 目标布局（3 个区域）

```
1. 页面标题 "我的学习"
2. 城堡入口卡片 (保留，主视觉)
3. "接下来学什么" 推荐卡 (新增)
4. 学习热力图 (简化 — 7 天火苗)
```

### 实施细节

#### 2a. 页面标题改文案

```typescript
// zh-CN.ts
'learning.progress.childTitle': '我的学习',
// en-US.ts  
'learning.progress.childTitle': 'My Learning',
```

#### 2b. "接下来学什么" 推荐卡

复用 `useRecommendationPath` composable（已在 LearningMapPage 使用），取第一个非 mastered 的推荐主题。

```vue
<!-- 接下来学什么 -->
<div v-if="nextRecommendation" class="next-up-card" @click="goToTopic(nextRecommendation.topic_id)">
  <div class="next-up-card__header">
    <span class="next-up-card__icon">🎯</span>
    <span class="next-up-card__label">{{ t('learning.progress.nextUp') }}</span>
  </div>
  <p class="next-up-card__name">{{ topicDisplayName(nextRecommendation.topic) }}</p>
  <p class="next-up-card__reason">{{ formatReasons(nextRecommendation.reasons) }}</p>
  <button class="next-up-card__cta">
    {{ t('learning.startLearning') }}
  </button>
</div>
```

推荐数据获取（复用 `useRecommendationPath` composable）：

```typescript
import { useRecommendationPath } from '@/composables/useRecommendationPath'
import { useLocalizedTopic } from '@/composables/useLocalizedTopic'

const { allPathTopics, refresh: refreshRecommendations } = useRecommendationPath()
const { topicDisplayName } = useLocalizedTopic()

const masteredIds = computed(() =>
  new Set(progressList.value.filter(p => p.mastery_level === 'mastered').map(p => p.topic_id))
)

const nextRecommendation = computed(() => {
  return allPathTopics.value.find(
    rec => !masteredIds.value.has(rec.topic_id)
  ) ?? null
})
```

```typescript
// 方案 A（推荐 — 无需后端改动）: 从 progress list 的 last_practice_at 推算
// 每个 topic 的 last_practice_at 告诉我们"这一天有学习活动"
// 虽然不精确（同一天的多个 topic 只算一天），但足以展示"哪些天有学习"
const last7Days = computed(() => {
  const practiceDates = new Set<string>()
  for (const p of progressList.value) {
    if (p.last_practice_at) {
      practiceDates.add(p.last_practice_at.slice(0, 10))
    }
  }
  const days = []
  const now = new Date()
  for (let i = 6; i >= 0; i--) {
    const d = new Date(now)
    d.setDate(d.getDate() - i)
    const dateStr = d.toISOString().slice(0, 10)
    days.push({
      date: dateStr,
      dayLabel: d.toLocaleDateString(locale.value, { weekday: 'short' }),
      active: practiceDates.has(dateStr),
      isToday: i === 0,
    })
  }
  return days
})

// 方案 B（后续迭代）: 新增 GET /child/learning/stats/daily?days=7
// 返回 { "2026-11-17": { minutes: 15 }, ... } — 精确到天的学习时间
// 当前用方案 A 足够，方案 B 作为 follow-up
```

#### 2c. 7 天学习热力图

替代精确的"总计 X 分钟 / 今日 Y 分钟"，用视觉化的 7 天热力图。

```vue
<!-- 7 天学习热力图 -->
<div class="streak-section">
  <h2 class="section-title">{{ t('learning.progress.streakTitle') }}</h2>
  <div class="streak-dots">
    <div
      v-for="day in last7Days"
      :key="day.date"
      class="streak-dot"
      :class="{
        'streak-dot--active': day.minutes > 0,
        'streak-dot--today': day.isToday,
      }"
    >
      <span class="streak-dot__day">{{ day.dayLabel }}</span>
      <span class="streak-dot__fire" v-if="day.minutes > 0">🔥</span>
    </div>
  </div>
  <p class="streak-summary">
    {{ streakSummary }}
  </p>
</div>
```

样式：7 个圆点水平排列，有学习记录的天亮色 + 火焰 emoji，无记录的灰色。今日用边框高亮。

```typescript
const last7Days = computed(() => {
  const days = []
  const now = new Date()
  for (let i = 6; i >= 0; i--) {
    const d = new Date(now)
    d.setDate(d.getDate() - i)
    const dateStr = d.toISOString().slice(0, 10)
    const minutes = dailyMinutesMap.value.get(dateStr) ?? 0
    days.push({
      date: dateStr,
      dayLabel: d.toLocaleDateString(locale.value, { weekday: 'short' }),
      minutes,
      isToday: i === 0,
    })
  }
  return days
})

const streakSummary = computed(() => {
  const activeDays = last7Days.value.filter(d => d.minutes > 0).length
  return t('learning.progress.streakSummary', { days: activeDays })
  // → "这周你学了 X 天！" / "You studied X days this week!"
})
```

#### 2d. 移除的区域（移至家长端）

以下区域从儿童进度页**移除**（不删除代码，注释掉或加 feature flag），后续加到 `BabyLearningPage.vue`：

- XP/Level/Streak 详细区域 → 家长端
- 4 个统计卡片网格 → 家长端
- 学习时间数字 → 已被热力图替代
- 最近活动列表 → 家长端
- 薄弱知识点列表 → 家长端
- 最近练习会话列表 → 家长端

#### 2e. 新增 i18n keys

```typescript
// zh-CN.ts
'learning.progress.nextUp': '接下来学',
'learning.progress.streakTitle': '这周的学习',
'learning.progress.streakSummary': '这周你学了 {days} 天！',

// en-US.ts
'learning.progress.nextUp': 'Up next',
'learning.progress.streakTitle': 'This week',
'learning.progress.streakSummary': 'You studied {days} days this week!',
```

### 验证

- [ ] 页面只有 3 个区域，总高度 < 2 屏
- [ ] 推荐卡点击正确导航
- [ ] 热力图 7 天渲染正确，today 高亮
- [ ] 移除的区域代码未删除（后续 Task 2b 移至家长端）
- [ ] 无 API 调用浪费（移除了 getWeakTopics / listPracticeSessions 调用）

---

## Task 3: Teach-Back 入口前置

**文件**: 
- `frontend/apps/child/src/components/learning/PracticeResultSummary.vue`
- `frontend/apps/child/src/pages/learning/PracticeSessionPage.vue`
- `frontend/apps/child/src/i18n/locales/zh-CN.ts` + `en-US.ts`

### 当前流程

```
练习完成 → PracticeResultSummary 显示:
  1. 发现 emoji + 文案
  2. 分数
  3. 奖励（XP/coins/掌握状态）
  4. 城堡 CTA (仅 isFirstMastery)
  5. [再来一次] [返回地图]
```

### 目标流程

```
练习完成 → PracticeResultSummary 显示:
  1. 发现 emoji + 文案
  2. 分数
  3. 奖励
  4. 🆕 Teach-Back CTA (仅 isFirstMastery，在城堡 CTA 之前)
  5. 城堡 CTA (仅 isFirstMastery)
  6. [再来一次] [返回地图]
```

### 实施细节

#### 3a. PracticeResultSummary.vue — 新增 Teach-Back 按钮

在 `btn-castle` 之前插入 Teach-Back 按钮：

```vue
<!-- Teach-Back CTA — 首次掌握时出现，位于城堡 CTA 之前 -->
<button
  v-if="showTeachBackCta"
  type="button"
  class="btn-teach-back"
  data-test="teach-back-cta"
  @click="goToTeachBack"
>
  <span class="btn-teach-back__icon">🎓</span>
  <span class="btn-teach-back__text">
    {{ t('learning.teach_back.result_cta') }}
  </span>
</button>
```

Script 部分新增：

```typescript
const props = defineProps<{
  result: PracticeResultResponse
  challengeDiscovery?: string
  topicId?: string
  isFirstMastery?: boolean
  /** Topic subject — needed for teach-back route query. */
  topicSubject?: string
  /** Topic age_group — needed for teach-back route query. */
  topicAgeGroup?: string
}>()

const showTeachBackCta = computed(
  () => Boolean(props.isFirstMastery) && Boolean(props.topicId),
)

function goToTeachBack(): void {
  if (!props.topicId) return
  const subject = props.topicSubject || 'mathematics'
  const ageGroup = props.topicAgeGroup || 'mid'
  router.push(
    `/learning/teach-back/${props.topicId}?subject=${subject}&ageGroup=${ageGroup}`,
  )
}
```

#### 3b. PracticeResultSummary.vue — 样式

```css
/* Teach-Back CTA — 温暖色强调，与城堡 CTA 视觉层级一致 */
.btn-teach-back {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  min-height: 52px;
  margin-bottom: 10px;
  border: 2px solid var(--color-brand-ochre, #e8b94a);
  border-radius: 14px;
  background: var(--color-surface-card);
  color: var(--color-ink);
  font-size: 16px;
  font-weight: 600;
  transition: transform 0.1s;
}
.btn-teach-back:active {
  transform: scale(0.97);
}
.btn-teach-back__icon {
  font-size: 22px;
}
```

设计说明：
- 用 border 强调（2px ochre 边框），与城堡 CTA（实心 ochre 背景）形成层级：城堡 > Teach-Back > 普通按钮
- 52px 高度（>44px touch target）
- 暖色调与学习系统一致

#### 3c. PracticeSessionPage.vue — 传入新 props

```vue
<PracticeResultSummary
  :result="sessionResult!"
  :challenge-discovery="challengeDiscoveryMessage || undefined"
  :topic-id="topicId"
  :is-first-mastery="isFirstMastery"
  :topic-subject="topicSubject"
  :topic-age-group="topicAgeGroup"
  @again="onAgain"
  @back="goBack"
/>
```

新增 computed：

```typescript
/** Topic subject for teach-back route — sourced from the topic detail fetched
 * during resolveTopicChallenge, or from the session's topic. */
const topicSubject = computed(() => {
  // topicDetail is already fetched in resolveTopicChallenge for challenge resolution
  return targetTopicDetail.value?.subject ?? 'mathematics'
})

const topicAgeGroup = computed(() => {
  return targetTopicDetail.value?.age_group ?? 'mid'
})
```

**注意**: `targetTopicDetail` 当前只获取 `name` 和 `name_zh`。需要扩展 `getTopicDetail` 的返回值来包含 `subject` 和 `age_group`：

```typescript
// 在 fetchDiagnosisAndTarget() 中
targetTopicDetail.value = {
  name: detail.name,
  name_zh: detail.name_zh,
  subject: detail.subject,
  age_group: detail.age_group,
}
```

#### 3d. 同时移除 TopicPage 底部的 Teach-Back 按钮

**不立即移除** — 保留 TopicPage 的 Teach-Back 入口作为降级路径（用户可能直接从地图进入 TopicPage 而非通过练习）。但将其视觉权重降低：从独立按钮改为文字链接。

```vue
<!-- 原来: <button class="btn-secondary"> -->
<!-- 改为: -->
<div v-if="isMastered" class="teach-back-link-row">
  <button class="text-link" @click="goToTeachBack">
    🎓 {{ t('learning.teach_back.start_btn') }}
  </button>
</div>
```

#### 3e. 新增 i18n keys

```typescript
// zh-CN.ts
'learning.teach_back.result_cta': '当小老师教 AI',

// en-US.ts  
'learning.teach_back.result_cta': 'Teach it to AI',
```

### 验证

- [ ] 首次掌握时 PracticeResultSummary 显示 Teach-Back 按钮
- [ ] 非首次掌握时不显示
- [ ] 点击正确导航到 `/learning/teach-back/:topicId?subject=...&ageGroup=...`
- [ ] TopicPage 仍保留降级入口（文字链接形式）
- [ ] 按钮高度 ≥ 44px touch target
- [ ] Dark mode 样式正确

---

## 实施顺序

建议按依赖关系排序：

| 顺序 | Task | 预计工作量 | 风险 |
|------|------|-----------|------|
| 1 | Task 3: Teach-Back 入口前置 | 小 (~1h) | 低 — 新增按钮，不改现有逻辑 |
| 2 | Task 1: TopicPage 首屏优化 | 中 (~3h) | 中 — 重构页面布局，需要仔细测试 |
| 3 | Task 2: 进度页儿童化 | 中 (~3h) | 中 — 移除区域需确认家长端有对应功能再接 |

Task 3 最先做，因为改动最小且效果最直接。Task 1 和 Task 2 涉及较大布局重构，需要更多测试。

---

## 跨 Task 注意事项

### i18n 完整性

所有新增字符串必须同时添加 `zh-CN.ts` 和 `en-US.ts`。运行 `pnpm -r lint` 检查。

### Dark Mode

所有新增/修改的 CSS 必须同时检查 `:root` 和 `[data-theme="dark"]` 的 token。使用 clay.css 变量而非硬编码颜色。

### KeepAlive

LearningMapPage 和 LearningProgressPage 可能有 KeepAlive 缓存。修改后需确认 `onActivated` 仍正确触发数据刷新。

### 移动端测试

所有变更需在 390px (iPhone 14) 和 768px (iPad) 宽度下测试。CTA 按钮高度 ≥ 44px。

### 不删除代码

Task 2 中移除的区域，代码注释掉而非删除。后续需要在家长端 BabyLearningPage 添加对应功能后再清理。
