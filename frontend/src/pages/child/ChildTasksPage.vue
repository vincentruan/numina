<template>
  <div class="chores-page">
    <div class="header">
      <span class="date-label">{{ todayLabel }}</span>
    </div>

    <div v-if="loading" class="loading">加载中...</div>

    <div v-if="error" class="error-msg">{{ error }}</div>

    <div v-else-if="!loading && chores.length === 0" class="empty">
      <p>今天没有家务 🎉</p>
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
          <p class="chore-reward">+{{ chore.coin_reward }} ⭐</p>
        </div>
        <div class="chore-action">
          <button
            v-if="chore.status === 'available'"
            class="btn-complete"
            :disabled="submittingId === chore.id"
            @click="complete(chore.id)"
          >完成</button>
          <span v-else-if="chore.status === 'pending_approval'" class="status-badge pending">审批中</span>
          <span v-else-if="chore.status === 'approved'" class="status-badge approved">✅ 已获得</span>
          <span v-else-if="chore.status === 'rejected'" class="status-badge rejected">❌ 被拒绝</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getMyChores, markChoreComplete, type ChoreInstance } from '@/api/chores'

const chores = ref<ChoreInstance[]>([])
const loading = ref(true)
const error = ref('')
const submittingId = ref<string | null>(null)
// Use local date (not UTC) to avoid wrong date for users east of UTC
const now = new Date()
const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
const todayLabel = now.toLocaleDateString('zh-CN', { month: 'long', day: 'numeric', weekday: 'short' })

async function load() {
  loading.value = true
  error.value = ''
  try {
    chores.value = await getMyChores(today)
  } catch {
    error.value = '加载失败，请刷新重试'
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
    error.value = '提交失败，请重试'
  } finally {
    submittingId.value = null
  }
}

onMounted(load)
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

