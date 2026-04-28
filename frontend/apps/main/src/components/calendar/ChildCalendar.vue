<template>
  <div class="child-calendar">
    <!-- Month navigation -->
    <div class="cal-header">
      <button class="nav-btn" @click="prevMonth">‹</button>
      <span class="cal-title">{{ year }}年{{ month }}月</span>
      <button class="nav-btn" @click="nextMonth">›</button>
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
      <span class="legend-item"><span class="dot dot-chore" />打卡</span>
      <span class="legend-item"><span class="dot dot-wish" />心愿</span>
      <span class="legend-item"><span class="dot dot-milestone" />成就</span>
    </div>

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
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
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

function heatColor(day: CalendarDaySummary): string {
  const total = dayTotal(day)
  if (total === 0) return '#ffffff'
  if (total === 1) return '#fff3e0'
  if (total <= 3) return '#ffe0b2'
  if (total <= 6) return '#ffb74d'
  return '#f5a623'
}

function isDark(day: CalendarDaySummary): boolean {
  return dayTotal(day) >= 4
}

const router = useRouter()

const today = new Date()
const todayStr = today.toISOString().slice(0, 10)

const year = ref(today.getFullYear())
const month = ref(today.getMonth() + 1)
const days = ref<CalendarDaySummary[]>([])
const loading = ref(false)

const weekdays = ['日', '一', '二', '三', '四', '五', '六']

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
    days.value = res.days
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
  background: #fff;
  border-radius: 12px;
  padding: 12px;
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
  color: #1a1a1a;
}
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
.nav-btn:active {
  background: #e8e8e8;
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
  color: #999;
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
  background: #f5a623;
  color: #fff;
  border-radius: 50%;
  width: 26px;
  height: 26px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.cal-cell.future {
  opacity: 0.35;
  pointer-events: none;
}

.day-num {
  font-size: 13px;
  color: #1a1a1a;
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
.dot-chore { background: #4caf50; }
.dot-wish  { background: #f5a623; }
.dot-milestone { background: #9c27b0; }

/* 深色背景时圆点加白描边 */
.dot-dark .dot {
  box-shadow: 0 0 0 1px #fff;
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

.dot-count-chore    { color: #2e7d32; }
.dot-count-wish     { color: #e65100; }
.dot-count-milestone { color: #6a1b9a; }

.dot-dark .dot-count {
  color: #fff;
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
  border-top: 1px solid #f0f0f0;
}
.legend-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: #888;
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
  color: #aaa;
}
.stats-sep { color: #ddd; }
.stats-rate { color: #f5a623; font-weight: 600; }

/* Streak connector */
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
</style>
