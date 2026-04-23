<template>
  <div class="approvals-page">
    <div class="page-header">
      <h2>家务审批</h2>
    </div>

    <div v-if="toastMsg" class="bonus-toast">{{ toastMsg }}</div>

    <div v-if="loading" class="loading">加载中...</div>

    <div v-if="error" class="error-msg">{{ error }}</div>

    <div v-else-if="!loading && pending.length === 0" class="empty">
      <p>暂无待审批家务 ✅</p>
    </div>

    <div v-else class="approval-list">
      <div v-for="item in pending" :key="item.id" class="approval-card">
        <div class="card-top">
          <span class="chore-emoji">{{ item.chore_emoji || '📋' }}</span>
          <div class="chore-info">
            <p class="chore-name">{{ item.chore_name }}</p>
            <p class="chore-reward">+{{ item.coin_reward }} ⭐</p>
          </div>
        </div>
        <div class="card-actions">
          <button class="btn-approve" :disabled="actioningId === item.id" @click="approve(item.id)">批准</button>
          <button class="btn-redo" :disabled="actioningId === item.id" @click="reject(item.id, true)">退回重做</button>
          <button class="btn-reject" :disabled="actioningId === item.id" @click="reject(item.id, false)">拒绝</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getPendingApprovals, approveChore, rejectChore, type PendingApprovalInstance } from '@/api/chores'

const pending = ref<PendingApprovalInstance[]>([])
const loading = ref(true)
const error = ref('')
const actioningId = ref<string | null>(null)
const toastMsg = ref('')
let toastTimer: ReturnType<typeof setTimeout> | null = null

function showToast(msg: string) {
  toastMsg.value = msg
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { toastMsg.value = '' }, 3000)
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    pending.value = await getPendingApprovals()
  } catch {
    error.value = '加载失败，请刷新重试'
  } finally {
    loading.value = false
  }
}

async function approve(instanceId: string) {
  actioningId.value = instanceId
  try {
    const result = await approveChore(instanceId)
    pending.value = pending.value.filter(i => i.id !== instanceId)
    if (result.streak_bonus > 0) {
      const multiplier = result.streak_count >= 14 ? '2x' : result.streak_count >= 7 ? '1.5x' : `${(result.streak_bonus / result.coin_reward + 1).toFixed(1)}x`
      showToast(t('toast.streakReward', { days: result.streak_count, bonus: result.streak_bonus }))
    }
  } catch {
    error.value = t('toast.operationFailed2')
  } finally {
    actioningId.value = null
  }
}

async function reject(instanceId: string, returnToRedo: boolean) {
  actioningId.value = instanceId
  try {
    await rejectChore(instanceId, returnToRedo)
    pending.value = pending.value.filter(i => i.id !== instanceId)
  } catch {
    error.value = t('toast.operationFailed2')
  } finally {
    actioningId.value = null
  }
}

onMounted(load)
</script>

<style scoped>
.approvals-page {
  padding: 16px;
  background: #f8f9fa;
  min-height: 100vh;
}
.page-header {
  margin-bottom: 16px;
}
.page-header h2 {
  font-size: 20px;
  font-weight: bold;
  color: #333;
  margin: 0;
}
.loading, .empty {
  text-align: center;
  margin-top: 60px;
  color: #999;
  font-size: 16px;
}
.approval-list { display: flex; flex-direction: column; gap: 12px; }
.approval-card {
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}
.card-top {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}
.chore-emoji { font-size: 28px; }
.chore-info { flex: 1; }
.chore-name { font-size: 16px; font-weight: 600; color: #333; margin: 0; }
.chore-reward { font-size: 13px; color: #f5a623; margin: 2px 0 0; }
.card-actions {
  display: flex;
  gap: 8px;
}
.card-actions button {
  flex: 1;
  padding: 8px 0;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
}
.btn-approve { background: #28a745; color: #fff; }
.btn-redo { background: #ffc107; color: #333; }
.btn-reject { background: #dc3545; color: #fff; }
.card-actions button:disabled { opacity: 0.5; cursor: not-allowed; }
.error-msg { background: #f8d7da; color: #721c24; border-radius: 8px; padding: 10px 14px; margin-bottom: 12px; font-size: 14px; }
.bonus-toast {
  position: fixed;
  top: 20px;
  left: 50%;
  transform: translateX(-50%);
  background: #ff6d00;
  color: #fff;
  border-radius: 20px;
  padding: 10px 20px;
  font-size: 14px;
  font-weight: 600;
  z-index: 9999;
  box-shadow: 0 4px 12px rgba(0,0,0,0.2);
  white-space: nowrap;
}
</style>
