<template>
  <van-popup
    :show="visible"
    position="bottom"
    round
    :close-on-click-overlay="false"
    class="feedback-popup"
    @close="onClose"
  >
    <div class="feedback-content">
      <h3 class="feedback-title">{{ t('scenario.feedbackTitle') }}</h3>

      <p class="feedback-text">{{ feedbackText }}</p>

      <div v-if="dimensionHint" class="dimension-row">
        <span class="dimension-label">{{ t('scenario.dimension') }}</span>
        <span class="dimension-value">{{ localizedDimension }}</span>
      </div>

      <div v-if="badgesUnlocked.length > 0" class="badges-section">
        <p class="badges-title">{{ t('scenario.badgesUnlocked') }}</p>
        <div class="badges-list">
          <span v-for="badge in badgesUnlocked" :key="badge" class="badge-chip">{{ badge }}</span>
        </div>
      </div>

      <button class="close-btn" @click="onClose">{{ t('scenario.close') }}</button>
    </div>
  </van-popup>
</template>

<script setup lang="ts">
defineOptions({ name: 'ScenarioFeedback' })

import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps<{
  visible: boolean
  feedbackText: string
  dimensionHint: string
  badgesUnlocked: string[]
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()

const { t } = useI18n()

const dimensionKeyMap: Record<string, string> = {
  earning: 'scenario.dimensions.earning',
  choosing: 'scenario.dimensions.choosing',
  waiting: 'scenario.dimensions.waiting',
  caring: 'scenario.dimensions.caring',
}

const localizedDimension = computed(() => {
  const key = dimensionKeyMap[props.dimensionHint]
  return key ? t(key) : props.dimensionHint
})

function onClose() {
  emit('close')
}
</script>

<style scoped>
.feedback-popup {
  max-height: 70vh;
}

.feedback-content {
  padding: 24px 20px 32px;
}

.feedback-title {
  font-family: Inter, sans-serif;
  font-size: 18px;
  font-weight: 600;
  color: var(--color-ink);
  margin: 0 0 12px;
  text-align: center;
}

.feedback-text {
  font-family: Inter, sans-serif;
  font-size: 15px;
  line-height: 1.6;
  color: var(--color-ink);
  margin: 0 0 16px;
}

.dimension-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: rgba(var(--color-brand-ochre-rgb, 200, 150, 50), 0.1);
  border-radius: var(--radius-md);
  margin-bottom: 16px;
}

.dimension-label {
  font-family: Inter, sans-serif;
  font-size: 14px;
  color: var(--color-body);
}

.dimension-value {
  font-family: Inter, sans-serif;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-brand-ochre);
}

.badges-section {
  margin-bottom: 16px;
  text-align: center;
}

.badges-title {
  font-family: Inter, sans-serif;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-brand-ochre);
  margin: 0 0 8px;
}

.badges-list {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 8px;
}

.badge-chip {
  display: inline-block;
  padding: 4px 12px;
  background: var(--color-brand-ochre);
  color: var(--color-on-primary);
  border-radius: var(--radius-md);
  font-family: Inter, sans-serif;
  font-size: 14px;
  font-weight: 600;
}

.close-btn {
  display: block;
  width: 100%;
  padding: 14px;
  background: var(--color-primary);
  color: var(--color-on-primary);
  border: none;
  border-radius: var(--radius-md);
  font-family: Inter, sans-serif;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.15s;
  -webkit-tap-highlight-color: transparent;
}

.close-btn:active {
  transform: scale(0.98);
}
</style>
