<template>
  <div class="chores-page">
    <!-- Date hero band — pink feature card -->
    <div class="date-hero">
      <p class="date-label">{{ todayLabel }}</p>
    </div>

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>

    <div v-else-if="error" class="error-msg">{{ error }}</div>

    <div v-else-if="chores.length === 0" class="empty">
      <p>{{ t('chore.noChoresTitle') }}</p>
    </div>

    <div v-else class="chore-list">
      <div
        v-for="chore in chores"
        :key="chore.id"
        class="chore-card"
        :class="chore.status"
        @click="chore.status === 'available' && !submittingId.value ? complete(chore.id) : undefined"
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
            @click.stop="complete(chore.id)"
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
    // non-blocking
  }
}

function showNextMilestone() {
  if (milestoneQueue.value.length === 0) return
  celebrationMilestone.value = milestoneQueue.value[0].milestone_type
  celebrationVisible.value = true
}

function dismissCelebration() {
  if (!celebrationVisible.value) return
  celebrationVisible.value = false
  if (milestoneQueue.value.length > 0) {
    markSeen(milestoneQueue.value[0].id)
    milestoneQueue.value = milestoneQueue.value.slice(1)
  }
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
/* ── Canvas ── */
.chores-page {
  padding: var(--space-md);
  background: var(--color-canvas);
  min-height: 100vh;
}

/* ── Date hero — pink feature card ── */
.date-hero {
  background: var(--color-brand-pink);
  border-radius: var(--radius-xl);
  padding: 20px 20px;
  text-align: center;
  margin-bottom: var(--space-lg);
}
[data-theme="dark"] .date-hero .date-label { color: var(--color-on-feature-pink); }
.date-label {
  font-family: Inter, sans-serif;
  font-size: 16px;
  font-weight: 600;
  color: var(--color-on-primary);
  margin: 0;
  letter-spacing: 0.3px;
}

.loading, .empty {
  text-align: center;
  margin-top: 60px;
  color: var(--color-muted-soft);
  font-size: 16px;
  font-family: Inter, sans-serif;
}

/* ── Chore list ── */
.chore-list { display: flex; flex-direction: column; gap: 12px; }

.chore-card {
  display: flex;
  align-items: center;
  background: var(--color-surface-soft);
  border-radius: var(--radius-lg);
  padding: 16px;
  gap: 12px;
  border: 1px solid var(--color-hairline);
  transition: transform 0.1s;
  min-height: 64px;
}
.chore-card.available { cursor: pointer; }
.chore-card.available:active { transform: scale(0.98); }
.chore-card.approved { opacity: 0.55; }
.chore-card.rejected { opacity: 0.45; }

.chore-emoji { font-size: 28px; }

.chore-info { flex: 1; }
.chore-name {
  font-family: Inter, sans-serif;
  font-size: 16px;
  font-weight: 600;
  color: var(--color-ink);
  margin: 0;
}
.chore-reward {
  font-family: Inter, sans-serif;
  font-size: 13px;
  color: var(--color-brand-ochre);
  margin: 4px 0 0;
  font-weight: 500;
}

.streak-badge {
  display: inline-block;
  margin-left: 6px;
  font-size: 12px;
  background: var(--color-brand-peach);
  color: var(--color-ink);
  border-radius: var(--radius-pill);
  padding: 1px 8px;
  font-weight: 600;
}

/* ── Complete button — pink brand CTA ── */
.btn-complete {
  background: var(--color-brand-pink);
  color: var(--color-on-dark);
  border: none;
  border-radius: var(--radius-md);
  padding: 0 18px;
  font-family: Inter, sans-serif;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  height: 44px;
  white-space: nowrap;
  transition: opacity 0.15s, transform 0.1s;
}
.btn-complete:disabled { opacity: 0.4; cursor: not-allowed; }
.btn-complete:active:not(:disabled) { transform: scale(0.96); }

/* ── Status badges ── */
.status-badge {
  font-family: Inter, sans-serif;
  font-size: 13px;
  padding: 4px 12px;
  border-radius: var(--radius-pill);
  white-space: nowrap;
  font-weight: 500;
}
.status-badge.pending  { background: var(--color-brand-peach); color: var(--color-ink); }
.status-badge.approved { background: var(--color-brand-mint); color: var(--color-ink); }
.status-badge.rejected { background: var(--color-brand-coral); color: var(--color-on-dark); }

.error-msg {
  background: var(--color-brand-coral);
  color: var(--color-on-dark);
  border-radius: var(--radius-md);
  padding: 10px 14px;
  margin-bottom: 12px;
  font-family: Inter, sans-serif;
  font-size: 14px;
}
</style>
