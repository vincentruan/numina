<template>
  <div v-if="filteredApprovals.length > 0" class="pending-approvals-section">
    <!-- Header -->
    <div class="approval-header" role="button" tabindex="0" :aria-expanded="!collapsed" @click="collapsed = !collapsed" @keydown.enter="collapsed = !collapsed">
      <span class="header-label">{{ t('pendingApprovals.title') }}</span>
      <span class="header-count">{{ filteredApprovals.length }}</span>
      <van-icon :name="collapsed ? 'arrow-down' : 'arrow-up'" size="14" class="collapse-icon" />
    </div>

    <!-- Card List -->
    <div v-if="!collapsed" class="approval-list">
      <div
        v-for="item in filteredApprovals"
        :key="item.id"
        class="approval-card"
      >
        <!-- Avatar + Info -->
        <div class="card-top">
          <div
            class="child-avatar"
            :style="{ backgroundColor: item.child_avatar_color || '#ccc' }"
            aria-hidden="true"
          >
            {{ item.child_display_name?.charAt(0) || '?' }}
          </div>

          <div class="card-info">
            <div class="card-title">
              <span class="chore-emoji">{{ item.chore_emoji || '📋' }}</span>
              {{ item.chore_name }}
            </div>
            <div class="card-meta">
              <span class="child-name">{{ item.child_display_name || t('pendingApprovals.unknown') }}</span>
              <span class="separator">·</span>
              <span class="reward">+{{ item.coin_reward }}⭐</span>
              <span class="separator">·</span>
              <span class="time">{{ formatRelativeTime(item.submitted_at) }}</span>
            </div>
          </div>
        </div>

        <!-- Piano Key Buttons (FamilyPage style) -->
        <div class="card-actions">
          <button
            class="action-btn action-btn--success"
            :disabled="actioningId === item.id"
            @click="onApprove(item.id)"
          >
            <van-icon name="success" size="18" />
            <span v-if="actioningId === item.id && currentAction === 'approve'">{{ t('pendingApprovals.approving') }}</span>
            <span v-else>{{ t('pendingApprovals.approve') }}</span>
          </button>
          <button
            class="action-btn action-btn--warning"
            :disabled="actioningId === item.id"
            @click="onReject(item.id, true)"
          >
            <van-icon name="revoke" size="18" />
            <span v-if="actioningId === item.id && currentAction === 'redo'">{{ t('pendingApprovals.redoing') }}</span>
            <span v-else>{{ t('pendingApprovals.returnRedo') }}</span>
          </button>
          <button
            class="action-btn action-btn--danger"
            :disabled="actioningId === item.id"
            @click="onReject(item.id, false)"
          >
            <van-icon name="cross" size="18" />
            <span v-if="actioningId === item.id && currentAction === 'reject'">{{ t('pendingApprovals.rejecting') }}</span>
            <span v-else>{{ t('pendingApprovals.reject') }}</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useChoreStore } from '@/stores/chore'

const props = defineProps<{
  childId?: string | null
}>()

const { t } = useI18n()
const choreStore = useChoreStore()
const actioningId = ref<string | null>(null)
const currentAction = ref<'approve' | 'redo' | 'reject' | null>(null)
const collapsed = ref(true)

const filteredApprovals = computed(() => {
  if (!props.childId) return choreStore.pendingApprovals
  return choreStore.pendingApprovals.filter(item => item.child_user_id === props.childId)
})

function formatRelativeTime(isoStr: string | null): string {
  if (!isoStr) return ''
  const ts = new Date(isoStr).getTime()
  if (Number.isNaN(ts)) return ''
  const diff = Date.now() - ts
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return t('pendingApprovals.justNow')
  if (mins < 60) return t('pendingApprovals.minutesAgo', { mins })
  const hours = Math.floor(mins / 60)
  if (hours < 24) return t('pendingApprovals.hoursAgo', { hours })
  const days = Math.floor(hours / 24)
  if (days < 7) return t('pendingApprovals.daysAgo', { days })
  const d = new Date(isoStr)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

async function onApprove(id: string) {
  actioningId.value = id
  currentAction.value = 'approve'
  try {
    await choreStore.approvePendingChore(id)
  } finally {
    actioningId.value = null
    currentAction.value = null
  }
}

async function onReject(id: string, returnToRedo: boolean) {
  actioningId.value = id
  currentAction.value = returnToRedo ? 'redo' : 'reject'
  try {
    await choreStore.rejectPendingChore(id, returnToRedo)
  } finally {
    actioningId.value = null
    currentAction.value = null
  }
}
</script>

<style scoped>
.pending-approvals-section {
  margin: 0 16px 12px;
  border-radius: 12px;
  overflow: hidden;
  background: var(--van-background-2, #fff);
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}

.approval-header {
  display: flex;
  align-items: center;
  padding: 12px 16px;
  background: var(--van-background-2, #fff);
  cursor: pointer;
  user-select: none;
}

.collapse-icon {
  color: var(--van-text-color-3, #c8c9cc);
  margin-left: 4px;
}

.header-label {
  font-size: 14px;
  font-weight: 600;
  color: var(--van-text-color, #323233);
  flex: 1;
}

.header-count {
  font-size: 12px;
  font-weight: 600;
  color: #fff;
  background: var(--van-danger-color, #ee0a24);
  border-radius: 10px;
  padding: 1px 7px;
  min-width: 20px;
  text-align: center;
}

.approval-list {
  border-top: 1px solid var(--van-border-color, #ebedf0);
}

.approval-card {
  display: flex;
  flex-direction: column;
  padding: 12px 0;
  border-bottom: 1px solid var(--van-border-color, #ebedf0);
}

.approval-card:last-child {
  border-bottom: none;
}

.card-top {
  display: flex;
  align-items: center;
  padding: 0 16px;
  gap: 12px;
}

.child-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  font-weight: 600;
  color: #fff;
  flex-shrink: 0;
}

.card-info {
  flex: 1;
  min-width: 0;
}

.card-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--van-text-color, #323233);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.chore-emoji {
  margin-right: 4px;
}

.card-meta {
  font-size: 12px;
  color: var(--van-text-color-2, #969799);
  margin-top: 2px;
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
}

.separator {
  opacity: 0.4;
}

.reward {
  color: var(--van-warning-color, #ff976a);
}

.card-actions {
  display: flex;
  border-top: 1px solid rgba(0, 0, 0, 0.06);
  margin-top: 12px;
  overflow: hidden;
}

[data-theme='dark'] .card-actions {
  border-color: rgba(255, 255, 255, 0.08);
}

.action-btn {
  flex: 1;
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 8px 4px;
  border: none;
  background: transparent;
  color: var(--van-text-color-2, #969799);
  font-size: 12px;
  cursor: pointer;
  transition: background 0.15s;
  position: relative;
  min-height: 36px;
}

.action-btn + .action-btn::before {
  content: '';
  position: absolute;
  left: 0;
  top: 20%;
  height: 60%;
  width: 1px;
  background: rgba(0, 0, 0, 0.06);
}

[data-theme='dark'] .action-btn + .action-btn::before {
  background: rgba(255, 255, 255, 0.08);
}

.action-btn:active {
  background: rgba(0, 0, 0, 0.04);
}

.action-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.action-btn--success {
  color: var(--van-success-color, #07c160);
}

.action-btn--warning {
  color: var(--van-warning-color, #ff976a);
}

.action-btn--danger {
  color: var(--van-danger-color, #ee0a24);
}
</style>