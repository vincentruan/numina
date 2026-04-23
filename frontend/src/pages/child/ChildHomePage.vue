<template>
  <div class="home-page">
    <!-- Balance hero -->
    <div class="hero-card">
      <p class="hero-label">我的星星币 ⭐</p>
      <CoinDisplay :amount="balance" :icon-size="32" class="hero-balance" :copper-to-silver="familyStore.coinCopperToSilver" :silver-to-gold="familyStore.coinSilverToGold" />
    </div>

    <!-- Today's chores -->
    <div class="section">
      <p class="section-title">📋 今日任务</p>
      <div v-if="loadingChores" class="hint">加载中...</div>
      <div v-else-if="todayChores.length === 0" class="hint">今天没有任务，好好休息吧！</div>
      <div v-else class="chore-list">
        <div
          v-for="c in todayChores"
          :key="c.id"
          class="chore-card"
          :class="c.status"
        >
          <span class="chore-emoji">{{ c.chore_emoji || '✅' }}</span>
          <div class="chore-info">
            <p class="chore-name">{{ c.chore_name }}</p>
            <p class="chore-reward">+{{ c.coin_reward + c.streak_bonus }} ⭐</p>
          </div>
          <span class="chore-status-badge">{{ statusLabel(c.status) }}</span>
        </div>
      </div>
    </div>

    <!-- Calendar -->
    <div class="section">
      <p class="section-title">📅 我的日历</p>
      <ChildCalendar :fetch-month="fetchChildMonth" day-route="/child/calendar/day" variant="child" />
    </div>

    <!-- Quick links -->
    <div class="quick-links">
      <router-link to="/child/wishes" class="quick-card wishes">
        <span class="quick-icon">🌟</span>
        <span class="quick-label">我的心愿</span>
      </router-link>
      <router-link to="/child/treasures" class="quick-card treasures">
        <span class="quick-icon">🏆</span>
        <span class="quick-label">我的宝贝</span>
      </router-link>
      <router-link to="/child/tasks" class="quick-card tasks">
        <span class="quick-icon">📋</span>
        <span class="quick-label">所有任务</span>
      </router-link>
      <router-link to="/child/ledger" class="quick-card ledger">
        <span class="quick-icon">💰</span>
        <span class="quick-label">星星账本</span>
      </router-link>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getCoinBalance } from '@/api/coins'
import { getMyChores, type ChoreInstance } from '@/api/chores'
import { getChildCalendar } from '@/api/calendar'
import CoinDisplay from '@/components/coins/CoinDisplay.vue'
import ChildCalendar from '@/components/calendar/ChildCalendar.vue'
import { useFamilyStore } from '@/stores/family'

const familyStore = useFamilyStore()
const balance = ref(0)
const todayChores = ref<ChoreInstance[]>([])
const loadingChores = ref(true)

function statusLabel(status: ChoreInstance['status']): string {
  switch (status) {
    case 'available': return '待完成'
    case 'pending_approval': return '待审批'
    case 'approved': return '✅'
    case 'rejected': return '❌'
    default: return ''
  }
}

function todayDate(): string {
  return new Date().toISOString().slice(0, 10)
}

function fetchChildMonth(year: number, month: number) {
  return getChildCalendar(year, month)
}

onMounted(async () => {
  const [bal, chores] = await Promise.all([
    getCoinBalance().catch(() => 0),
    getMyChores(todayDate()).catch(() => [] as ChoreInstance[]),
  ])
  balance.value = bal
  todayChores.value = chores
  loadingChores.value = false
})
</script>

<style scoped>
.home-page {
  padding: 16px;
  background: #fff9e6;
  min-height: 100vh;
}

.hero-card {
  background: linear-gradient(135deg, #f5a623, #f7c948);
  border-radius: 20px;
  padding: 28px 20px;
  text-align: center;
  color: #fff;
  margin-bottom: 20px;
}
.hero-label { font-size: 15px; margin: 0 0 8px; opacity: 0.9; }
.hero-balance { font-size: 40px; font-weight: bold; }

.section { margin-bottom: 20px; }
.section-title { font-size: 16px; font-weight: bold; color: #333; margin: 0 0 10px; }
.hint { font-size: 14px; color: #999; text-align: center; padding: 16px 0; }

.chore-list { display: flex; flex-direction: column; gap: 8px; }
.chore-card {
  display: flex;
  align-items: center;
  background: #fff;
  border-radius: 12px;
  padding: 12px 14px;
  box-shadow: 0 2px 6px rgba(0,0,0,0.05);
  gap: 12px;
}
.chore-card.approved { opacity: 0.6; }
.chore-emoji { font-size: 24px; }
.chore-info { flex: 1; }
.chore-name { font-size: 14px; font-weight: 600; color: #333; margin: 0; }
.chore-reward { font-size: 12px; color: #f5a623; margin: 2px 0 0; }
.chore-status-badge { font-size: 12px; color: #999; white-space: nowrap; }

.quick-links {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.quick-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 20px 12px;
  border-radius: 16px;
  text-decoration: none;
  background: #fff;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
  transition: transform 0.1s;
}
.quick-card:active { transform: scale(0.96); }
.quick-icon { font-size: 32px; }
.quick-label { font-size: 13px; font-weight: 600; color: #333; }
.quick-card.wishes { background: linear-gradient(135deg, #fff9e6, #fef3c7); }
.quick-card.treasures { background: linear-gradient(135deg, #fef3c7, #fde68a); }
.quick-card.tasks { background: linear-gradient(135deg, #e0f2fe, #bae6fd); }
.quick-card.ledger { background: linear-gradient(135deg, #f0fdf4, #dcfce7); }
</style>
