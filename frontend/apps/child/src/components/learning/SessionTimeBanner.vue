<template>
  <div v-if="showWarning" class="session-time-banner" :class="{ 'session-time-banner--expired': expired }">
    <div v-if="expired" class="time-expired">
      <span class="time-expired__icon">🌙</span>
      <p class="time-expired__text">{{ t('learning.session.timeExpired', { topics: topicsExplored }) }}</p>
      <button class="time-expired__btn" @click="$emit('endSession')">
        {{ t('learning.session.goHome') }}
      </button>
    </div>
    <div v-else class="time-warning">
      <span class="time-warning__icon">⏰</span>
      <span class="time-warning__text">{{ t('learning.session.timeRemaining', { minutes: remainingMinutes }) }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps<{
  remainingMinutes: number
  expired: boolean
  topicsExplored: number
}>()

defineEmits<{
  endSession: []
}>()

const { t } = useI18n()

const showWarning = computed(() => props.remainingMinutes <= 5 || props.expired)
</script>

<style scoped>
.session-time-banner {
  padding: 10px 16px;
  background: #fff3e0;
  border-radius: var(--radius-md);
  margin-bottom: 12px;
}

[data-theme="dark"] .session-time-banner {
  background: #3e2723;
}

.session-time-banner--expired {
  background: #fce4ec;
}

[data-theme="dark"] .session-time-banner--expired {
  background: #4a1c24;
}

.time-warning {
  display: flex;
  align-items: center;
  gap: 8px;
  font-family: Inter, sans-serif;
  font-size: 13px;
  color: #e65100;
}

[data-theme="dark"] .time-warning {
  color: #ffcc80;
}

.time-expired {
  text-align: center;
}

.time-expired__icon {
  font-size: 24px;
}

.time-expired__text {
  font-family: Inter, sans-serif;
  font-size: 14px;
  color: var(--color-ink);
  margin: 8px 0;
}

.time-expired__btn {
  padding: 8px 20px;
  background: var(--color-primary);
  color: var(--color-canvas);
  border: none;
  border-radius: var(--radius-md);
  font-family: Inter, sans-serif;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
}
</style>
