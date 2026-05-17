<template>
  <div class="child-calendar">
    <!-- Month navigation -->
    <div class="cal-header">
      <button class="nav-btn" :aria-label="t('calendar.prevMonth')" @click="prevMonth">‹</button>
      <span class="cal-title">{{ t('calendar.monthTitle', { year, month }) }}</span>
      <button class="nav-btn" :aria-label="t('calendar.nextMonth')" @click="nextMonth">›</button>
    </div>

    <!-- Weekday labels -->
    <div class="cal-weekdays">
      <span v-for="d in weekdays" :key="d">{{ d }}</span>
    </div>

    <!-- Day grid -->
    <div class="cal-grid" :class="{ loading }">
      <!-- Leading empty cells -->
      <div v-for="n in leadingBlanks" :key="`b-${n}`" class="cal-cell empty" />

      <!-- Day cells -->
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
          streak: streakDates.has(day.date),
        }"
        :style="{ background: heatColor(day) }"
        :aria-label="t('calendar.dayLabel', { month: parseInt(day.date.slice(5, 7), 10), day: dayNum(day.date), count: dayTotal(day) })"
        @click="onDayClick(day)"
      >
        <span class="day-num">{{ dayNum(day.date) }}</span>
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
      </div>
    </div>

    <!-- Legend -->
    <div class="cal-legend">
      <span class="legend-item"><span class="dot dot-chore" />{{ t('calendar.legendChore') }}</span>
      <span class="legend-item"><span class="dot dot-wish" />{{ t('calendar.legendWish') }}</span>
      <span class="legend-item"><span class="dot dot-milestone" />{{ t('calendar.legendMilestone') }}</span>
    </div>

    <!-- Stats bar -->
    <div class="cal-stats">
      <span>{{ t('calendar.statsChores', { count: monthStats.totalChores }) }}</span>
      <span class="stats-sep">·</span>
      <span>{{ t('calendar.statsWishes', { count: monthStats.totalWishes }) }}</span>
      <span class="stats-sep">·</span>
      <span>{{ t('calendar.statsMilestones', { count: monthStats.totalMilestones }) }}</span>
      <template v-if="showCompletionRate">
        <span class="stats-sep">·</span>
        <span class="stats-rate">{{ t('calendar.statsRate', { rate: monthStats.completionRate }) }}</span>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { type CalendarDaySummary, type CalendarMonthResponse } from '@/api/calendar'

const props = defineProps<{
  /** If provided, uses parent-view data loader; otherwise child-view */
  fetchMonth: (year: number, month: number) => Promise<CalendarMonthResponse>
  /** Route prefix for day detail: '/child/calendar/day' or '/baby/calendar/day' */
  dayRoute: string
  /** Extra query params to pass to day detail route (e.g. { child_id: '123' }) */
  extraQuery?: Record<string, string>
  /** 'child' = 圆角10px活泼风; 'parent' = 圆角8px规整风 */
  variant?: 'child' | 'parent'
  /** 父母视角传 true，显示完成率 */
  showCompletionRate?: boolean
}>()

function dotLabel(count: number): string {
  if (count <= 1) return ''
  if (count >= 10) return '9+'
  return String(count)
}

function dayTotal(day: CalendarDaySummary): number {
  return day.chore_count + day.wish_count + day.milestone_count
}

// Heat colors use CSS variables so dark mode overrides apply automatically.
// We return a var() string; the actual color is resolved by the browser.
function heatColor(day: CalendarDaySummary): string {
  const total = dayTotal(day)
  if (total === 0) return 'transparent'
  if (total === 1) return 'var(--heat-1)'
  if (total <= 3) return 'var(--heat-2)'
  if (total <= 6) return 'var(--heat-3)'
  return 'var(--heat-4)'
}

function isDark(day: CalendarDaySummary): boolean {
  return dayTotal(day) >= 4
}

const router = useRouter()
const { t, tm } = useI18n()

const today = new Date()
const todayStr = today.toISOString().slice(0, 10)

const year = ref(today.getFullYear())
const month = ref(today.getMonth() + 1)
const days = ref<CalendarDaySummary[]>([])
const loading = ref(false)

const weekdays = computed(() => tm('calendar.weekdays') as string[])

const leadingBlanks = computed(() => {
  const first = new Date(year.value, month.value - 1, 1)
  return first.getDay() // 0=Sun
})

const monthStats = computed(() => {
  const totalChores = days.value.reduce((s, d) => s + d.chore_count, 0)
  const totalWishes = days.value.reduce((s, d) => s + d.wish_count, 0)
  const totalMilestones = days.value.reduce((s, d) => s + d.milestone_count, 0)
  const activeDays = days.value.filter(d => d.chore_count > 0).length
  const pastDays = days.value.filter(d => d.date <= todayStr).length
  const completionRate = pastDays > 0 ? Math.round((activeDays / pastDays) * 100) : 0
  return { totalChores, totalWishes, totalMilestones, completionRate }
})

const streakDates = computed<Set<string>>(() => {
  const set = new Set<string>()
  for (let i = 1; i < days.value.length; i++) {
    const prev = days.value[i - 1]
    const curr = days.value[i]
    if (prev.chore_count > 0 && curr.chore_count > 0) {
      set.add(curr.date)
    }
  }
  return set
})

function dayNum(dateStr: string): number {
  return parseInt(dateStr.slice(8), 10)
}

async function loadMonth() {
  loading.value = true
  try {
    const res = await props.fetchMonth(year.value, month.value)
    days.value = res.days ?? []
  } catch {
    days.value = []
  } finally {
    loading.value = false
  }
}

function prevMonth() {
  if (month.value === 1) {
    year.value--
    month.value = 12
  } else {
    month.value--
  }
}

function nextMonth() {
  if (month.value === 12) {
    year.value++
    month.value = 1
  } else {
    month.value++
  }
}

function onDayClick(day: CalendarDaySummary) {
  if (day.chore_count === 0 && day.wish_count === 0 && day.milestone_count === 0) return
  router.push({ path: props.dayRoute, query: { date: day.date, ...props.extraQuery } })
}

watch([year, month], loadMonth)
onMounted(loadMonth)
</script>

<style scoped>
.child-calendar {
  /* Heat color tokens — light mode: warm amber tones */
  --heat-1: #fff3e0;
  --heat-2: #ffe0b2;
  --heat-3: #ffb74d;
  --heat-4: #f5a623;

  background: var(--color-surface-card);
  border-radius: 12px;
  padding: 12px;
}

/* Dark mode heat colors: teal-green tones with enough contrast against #152828 */
:global([data-theme="dark"]) .child-calendar {
  --heat-1: rgba(34, 197, 94, 0.12);
  --heat-2: rgba(34, 197, 94, 0.25);
  --heat-3: rgba(34, 197, 94, 0.45);
  --heat-4: rgba(34, 197, 94, 0.70);
}

/* Header */
.cal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.cal-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-ink);
}
.nav-btn {
  width: 44px;
  height: 44px;
  border: none;
  background: var(--color-surface-strong);
  border-radius: 10px;
  font-size: 20px;
  color: var(--color-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  -webkit-tap-highlight-color: transparent;
}
.nav-btn:active {
  background: var(--color-hairline);
}

/* Weekday row */
.cal-weekdays {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  margin-bottom: 4px;
}
.cal-weekdays span {
  text-align: center;
  font-size: 11px;
  color: var(--color-muted-soft);
  padding: 4px 0;
}

/* Grid */
.cal-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 0;
  transition: opacity 0.2s;
}
.cal-grid.loading {
  opacity: 0.4;
  pointer-events: none;
}

.cal-cell {
  min-height: 44px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  cursor: default;
  padding: 4px 1px;
  position: relative;
  -webkit-tap-highlight-color: transparent;
}
.cal-cell.empty {
  pointer-events: none;
}
.cal-cell.active {
  cursor: pointer;
  transition: transform 0.1s;
}
.cal-cell.active:active {
  transform: scale(0.92);
}
.cal-cell.today .day-num {
  background: var(--color-brand-ochre);
  color: var(--color-surface-dark);
  border-radius: 50%;
  width: 26px;
  height: 26px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
}
.cal-cell.future {
  opacity: 0.35;
  pointer-events: none;
}

.day-num {
  font-size: 13px;
  color: var(--color-ink);
  line-height: 1;
  width: 26px;
  height: 26px;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* Dots */
.day-dots {
  display: flex;
  gap: 2px;
  margin-top: 3px;
  min-height: 6px;
}
.dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  display: inline-block;
  flex-shrink: 0;
}
.dot-chore { background: var(--color-success); }
.dot-wish  { background: var(--color-brand-ochre); }
.dot-milestone { background: var(--color-brand-lavender); }

/* 深色背景时圆点加描边 */
.dot-dark .dot {
  box-shadow: 0 0 0 1px var(--color-canvas);
}

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

.dot-count-chore    { color: var(--color-success); }
.dot-count-wish     { color: var(--color-brand-ochre); }
.dot-count-milestone { color: var(--color-brand-lavender); }

.dot-dark .dot-count {
  color: var(--color-on-dark);
}

/* 父母视角圆角 */
.cal-cell.variant-parent {
  border-radius: 8px;
}

/* Legend */
.cal-legend {
  display: flex;
  gap: 16px;
  justify-content: center;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid var(--color-hairline-soft);
}
.legend-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--color-muted-soft);
}

/* Stats bar */
.cal-stats {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 8px;
  font-size: 11px;
  color: var(--color-muted-soft);
}
.stats-sep { color: var(--color-hairline); }
.stats-rate { color: var(--color-brand-ochre); font-weight: 600; }

/* Streak connector */
.cal-cell.streak::before {
  content: '';
  position: absolute;
  left: -50%;
  top: 50%;
  width: 50%;
  height: 2px;
  background: var(--color-brand-ochre);
  opacity: 0.5;
  transform: translateY(-50%);
  pointer-events: none;
}
</style>
