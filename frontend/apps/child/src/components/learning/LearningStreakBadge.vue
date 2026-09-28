<template>
  <div v-if="days > 0" class="streak-badge">
    <span class="streak-icon">🔥</span>
    <span class="streak-text">{{ t('learning.stats.streak', { days }) }}</span>
    <span v-if="milestone" class="streak-milestone">{{ milestone }}</span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps<{
  days: number
}>()

const { t } = useI18n()

const milestone = computed(() => {
  if (props.days >= 100) return '👑'
  if (props.days >= 30) return '🏅'
  if (props.days >= 7) return '⭐'
  return ''
})
</script>

<style scoped>
.streak-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  background: linear-gradient(135deg, #fff3e0, #ffe0b2);
  border-radius: 16px;
  font-family: Inter, sans-serif;
  font-size: 13px;
  font-weight: 600;
  color: #e65100;
}

[data-theme="dark"] .streak-badge {
  background: linear-gradient(135deg, #3e2723, #4e342e);
  color: #ffb74d;
}

.streak-icon {
  font-size: 14px;
}

.streak-text {
  line-height: 1;
}

.streak-milestone {
  font-size: 12px;
}
</style>
