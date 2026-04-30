<template>
  <div class="chores-page">
    <div class="header">
      <span class="date-label">{{ todayLabel }}</span>
    </div>

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>

    <div v-if="error" class="error-msg">{{ error }}</div>

    <div v-else-if="!loading && chores.length === 0" class="empty">
      <p>{{ t('chore.noChoresTitle') }}</p>
    </div>

    <div v-else class="chore-list">
      <div
        v-for="chore in chores"
        :key="chore.id"
        class="chore-card"
        :class="chore.status"
      >
        <span class="chore-emoji">{{ chore.chore_emoji || '📋' }}</span>
        <div class="chore-info">
          <p class="chore-name">{{ chore.chore_name }}</p>
          <p class="chore-reward">
            +{{ chore.coin_reward }} ⭐
            <span v-if="chore.streak_count > 1" class="streak-badge">🔥{{ chore.streak_count }}</span>
          </p>
        </div>
        <div class="chore-action">
          <button
            v-if="chore.status === 'available'"
            class="btn-complete"
            :disabled="submittingId === chore.id"
            @click="complete(chore.id)"
          >{{ t('chore.complete') }}</button>
          <span v-else-if="chore.status === 'pending_approval'" class="status-badge pending">{{ t('chore.pendingApproval') }}</span>
          <span v-else-if="chore.status === 'approved'" class="status-badge approved">{{ t('chore.approved') }}</span>
          <span v-else-if="chore.status === 'rejected'" class="status-badge rejected">{{ t('chore.rejected') }}</span>
        </div>
      </div>
    </div>

    <MilestoneCelebration
      :visible="celebrationVisible"
      :milestone-type="celebrationMilestone"
      @dismiss="dismissCelebration"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { getMyChores, markChoreComplete, type ChoreInstance } from '@/api/chores'
import { getMyMilestones } from '@/api/milestones'
import MilestoneCelebration from '@/components/MilestoneCelebration.vue'

const { t } = useI18n()

const chores = ref<ChoreInstance[]>([])
const loading = ref(true)
const error = ref('')
const submittingId = ref<string | null>(null)
const celebrationVisible = ref(false)
const celebrationMilestone = ref('')
const milestoneQueue = ref<{ id: string; milestone_type: string }[]>([])

// Use local date (not UTC) to avoid wrong date for users east of UTC
const now = new Date()
const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
const todayLabel = now.toLocaleDateString('zh-CN', { month: 'long', day: 'numeric', weekday: 'short' })

const SEEN_KEY = 'seen_milestones'

function getSeenIds(): Set<string> {
  try {
    return new Set(JSON.parse(localStorage.getItem(SEEN_KEY) || '[]'))
  } catch {
    return new Set()
  }
}

function markSeen(id: string) {
  const seen = getSeenIds()
  seen.add(id)
  // Prune to last 200 entries to prevent unbounded localStorage growth
  const pruned = [...seen].slice(-200)
  localStorage.setItem(SEEN_KEY, JSON.stringify(pruned))
}

async function checkNewMilestones() {
  try {
    const milestones = await getMyMilestones()
    const seen = getSeenIds()
    const unseen = milestones.filter(m => !seen.has(m.id))
    if (unseen.length > 0) {
      milestoneQueue.value = unseen.map(m => ({ id: m.id, milestone_type: m.milestone_type }))
      showNextMilestone()
    }
  } catch {
    // Milestone check failure is non-blocking
  }
}

function showNextMilestone() {
  if (milestoneQueue.value.length === 0) return
  celebrationMilestone.value = milestoneQueue.value[0].milestone_type
  celebrationVisible.value = true
}

function dismissCelebration() {
  if (!celebrationVisible.value) return  // guard against rapid double-tap
  celebrationVisible.value = false
  // Mark current as seen only after user dismisses
  if (milestoneQueue.value.length > 0) {
    markSeen(milestoneQueue.value[0].id)
    milestoneQueue.value = milestoneQueue.value.slice(1)
  }
  // Show next queued milestone after a short delay
  if (milestoneQueue.value.length > 0) {
    setTimeout(showNextMilestone, 300)
  }
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    chores.value = await getMyChores(today)
  } catch {
    error.value = t('toast.loadFailed')
  } finally {
    loading.value = false
  }
}

async function complete(instanceId: string) {
  submittingId.value = instanceId
  try {
    const updated = await markChoreComplete(instanceId)
    const idx = chores.value.findIndex(c => c.id === instanceId)
    if (idx !== -1) chores.value[idx] = updated
  } catch {
    error.value = t('toast.submitFailed')
  } finally {
    submittingId.value = null
  }
}

onMounted(async () => {
  await load()
  await checkNewMilestones()
})
</script>

<style scoped>
.chores-page {
  padding: 16px;
  background: #FFF9E6;
  min-height: 100vh;
}
.header {
  text-align: center;
  margin-bottom: 16px;
}
.date-label {
  font-size: 14px;
  color: #999;
}
.loading, .empty {
  text-align: center;
  margin-top: 60px;
  color: #999;
  font-size: 16px;
}
.chore-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.chore-card {
  display: flex;
  align-items: center;
  background: #fff;
  border-radius: 12px;
  padding: 14px 16px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
  gap: 12px;
}
.chore-card.approved { opacity: 0.6; }
.chore-card.rejected { opacity: 0.5; }
.chore-emoji { font-size: 28px; }
.chore-info { flex: 1; }
.chore-name { font-size: 16px; font-weight: 600; color: #333; margin: 0; }
.chore-reward { font-size: 13px; color: #f5a623; margin: 2px 0 0; }
.streak-badge {
  display: inline-block;
  margin-left: 6px;
  font-size: 12px;
  background: #fff3e0;
  color: #e65100;
  border-radius: 10px;
  padding: 1px 6px;
  font-weight: 700;
}
.btn-complete {
  background: #f5a623;
  color: #fff;
  border: none;
  border-radius: 20px;
  padding: 8px 18px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
}
.status-badge {
  font-size: 13px;
  padding: 4px 10px;
  border-radius: 12px;
  white-space: nowrap;
}
.status-badge.pending { background: #fff3cd; color: #856404; }
.status-badge.approved { background: #d4edda; color: #155724; }
.status-badge.rejected { background: #f8d7da; color: #721c24; }
.btn-complete:disabled { opacity: 0.5; cursor: not-allowed; }
.error-msg { background: #f8d7da; color: #721c24; border-radius: 8px; padding: 10px 14px; margin-bottom: 12px; font-size: 14px; }
</style>
