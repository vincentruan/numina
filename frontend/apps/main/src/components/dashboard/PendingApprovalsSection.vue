<template>
  <div v-if="choreStore.pendingCount > 0" class="pending-approvals-section">
    <!-- Collapse Toggle -->
    <div class="approval-toggle" @click="isExpanded = !isExpanded">
      <span class="toggle-label">待审批家务</span>
      <span class="toggle-count">{{ choreStore.pendingCount }}</span>
      <van-icon :name="isExpanded ? 'arrow-up' : 'arrow-down'" class="toggle-icon" />
    </div>

    <!-- Card List -->
    <div v-if="isExpanded" class="approval-list">
      <div
        v-for="item in choreStore.pendingApprovals"
        :key="item.id"
        class="approval-card"
      >
        <!-- Avatar + Info -->
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
            <span class="child-name">{{ item.child_display_name || '未知' }}</span>
            <span class="separator">·</span>
            <span class="reward">+{{ item.coin_reward }}⭐</span>
            <span class="separator">·</span>
            <span class="time">{{ formatRelativeTime(item.submitted_at) }}</span>
          </div>
        </div>

        <!-- Action Buttons -->
        <div class="card-actions">
          <van-button
            size="mini"
            type="success"
            plain
            :disabled="actioningId === item.id"
            :loading="actioningId === item.id"
            @click="onApprove(item.id)"
          >
            批准
          </van-button>
          <van-button
            size="mini"
            type="warning"
            plain
            :disabled="actioningId === item.id"
            @click="onReject(item.id, true)"
          >
            退回
          </van-button>
          <van-button
            size="mini"
            type="danger"
            plain
            :disabled="actioningId === item.id"
            @click="onReject(item.id, false)"
          >
            拒绝
          </van-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useChoreStore } from '@/stores/chore'

const choreStore = useChoreStore()
const isExpanded = ref(false)
const actioningId = ref<string | null>(null)

function formatRelativeTime(isoStr: string | null): string {
  if (!isoStr) return ''
  const t = new Date(isoStr).getTime()
  if (Number.isNaN(t)) return ''
  const diff = Date.now() - t
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return '刚刚'
  if (mins < 60) return `${mins}分钟前`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}小时前`
  const days = Math.floor(hours / 24)
  if (days < 7) return `${days}天前`
  const d = new Date(isoStr)
  return `${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

async function onApprove(id: string) {
  actioningId.value = id
  try {
    await choreStore.approvePendingChore(id)
  } finally {
    actioningId.value = null
  }
}

async function onReject(id: string, returnToRedo: boolean) {
  actioningId.value = id
  try {
    await choreStore.rejectPendingChore(id, returnToRedo)
  } finally {
    actioningId.value = null
  }
}
</script>

<style scoped>
.pending-approvals-section {
  margin: 12px 16px 0;
  border-radius: 12px;
  overflow: hidden;
  background: var(--van-background-2, #fff);
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}

.approval-toggle {
  display: flex;
  align-items: center;
  padding: 12px 16px;
  cursor: pointer;
  user-select: none;
}

.toggle-label {
  font-size: 14px;
  font-weight: 600;
  color: var(--van-text-color, #323233);
  flex: 1;
}

.toggle-count {
  font-size: 12px;
  font-weight: 600;
  color: #fff;
  background: var(--van-danger-color, #ee0a24);
  border-radius: 10px;
  padding: 1px 7px;
  margin-right: 8px;
  min-width: 20px;
  text-align: center;
}

.toggle-icon {
  color: var(--van-text-color-2, #969799);
  font-size: 14px;
}

.approval-list {
  border-top: 1px solid var(--van-border-color, #ebedf0);
}

.approval-card {
  display: flex;
  align-items: center;
  padding: 12px 16px;
  gap: 12px;
  border-bottom: 1px solid var(--van-border-color, #ebedf0);
}

.approval-card:last-child {
  border-bottom: none;
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
  flex-direction: column;
  gap: 4px;
  flex-shrink: 0;
}
</style>
