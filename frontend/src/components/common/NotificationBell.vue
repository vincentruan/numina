<template>
  <div class="notification-bell" @click="togglePanel">
    <van-badge :content="unreadCount > 0 ? unreadCount : ''" :max="99">
      <van-icon name="bell" size="20" />
    </van-badge>

    <van-popup
      v-model:show="panelVisible"
      position="top"
      :style="{ maxHeight: '70vh', width: '100%' }"
      :overlay="true"
      @click-overlay="panelVisible = false"
    >
      <div class="notification-panel">
        <div class="notification-header">
          <span class="notification-title">通知</span>
          <van-button
            v-if="notifications.length > 0"
            size="mini"
            plain
            type="primary"
            @click.stop="handleMarkAllRead"
          >全部已读</van-button>
        </div>

        <div v-if="notifications.length === 0" class="notification-empty">
          <van-icon name="bell-o" size="40" color="#ccc" />
          <p>暂无通知</p>
        </div>

        <div v-else class="notification-list">
          <div
            v-for="item in notifications"
            :key="item.id"
            class="notification-item"
            :class="{ unread: !item.read }"
          >
            <div class="notification-item-title">{{ item.title }}</div>
            <div class="notification-item-message">{{ item.message }}</div>
            <div class="notification-item-time">{{ relativeTime(item.timestamp) }}</div>
          </div>
        </div>

        <div v-if="notifications.length > 0" class="notification-footer">
          <van-button size="small" plain @click.stop="handleClearAll">清空通知</van-button>
        </div>
      </div>
    </van-popup>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useNotificationStore } from '@/stores/notification'
import { storeToRefs } from 'pinia'

const notificationStore = useNotificationStore()
const { notifications, unreadCount } = storeToRefs(notificationStore)

const panelVisible = ref(false)

function togglePanel() {
  panelVisible.value = !panelVisible.value
}

function handleMarkAllRead() {
  notificationStore.markAllRead()
}

function handleClearAll() {
  notificationStore.clearAll()
  panelVisible.value = false
}

function relativeTime(timestamp: number): string {
  const diff = Date.now() - timestamp
  const minutes = Math.floor(diff / 60_000)
  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes}分钟前`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}小时前`
  const days = Math.floor(hours / 24)
  return `${days}天前`
}
</script>

<style scoped>
.notification-bell {
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.notification-panel {
  display: flex;
  flex-direction: column;
  max-height: 70vh;
}

.notification-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--van-border-color, #ebedf0);
  flex-shrink: 0;
}

.notification-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--van-text-color, #323233);
}

.notification-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 16px;
  color: #999;
  font-size: 14px;
  gap: 8px;
}

.notification-list {
  overflow-y: auto;
  flex: 1;
}

.notification-item {
  padding: 12px 16px;
  border-bottom: 1px solid var(--van-border-color, #ebedf0);
  position: relative;
}

.notification-item.unread::before {
  content: '';
  position: absolute;
  left: 6px;
  top: 50%;
  transform: translateY(-50%);
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--van-primary-color, #1989fa);
}

.notification-item.unread {
  padding-left: 20px;
}

.notification-item-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--van-text-color, #323233);
  margin-bottom: 4px;
}

.notification-item-message {
  font-size: 13px;
  color: var(--van-text-color-2, #969799);
  line-height: 1.4;
}

.notification-item-time {
  font-size: 12px;
  color: var(--van-text-color-3, #c8c9cc);
  margin-top: 4px;
}

.notification-footer {
  padding: 10px 16px;
  border-top: 1px solid var(--van-border-color, #ebedf0);
  display: flex;
  justify-content: center;
  flex-shrink: 0;
}
</style>
