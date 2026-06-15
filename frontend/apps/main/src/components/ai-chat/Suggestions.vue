<script setup lang="ts">
/**
 * DeerFlow Suggestions 组件
 *
 * 参考: frontend/src/components/ai-elements/suggestion.tsx
 *
 * 功能:
 * - 横向滚动的建议按钮列表
 * - Stagger 动画（依次淡入）
 * - Loading 状态
 * - 关闭按钮
 */
import { Button } from 'vant'
import { useI18n } from 'vue-i18n'
import SuggestionChip from './SuggestionChip.vue'
import IIcon from '@/components/IIcon.vue'

const { t } = useI18n()

defineProps<{
  suggestions: string[]
  loading?: boolean
  hidden?: boolean
}>()

const emit = defineEmits<{
  select: [suggestion: string]
  hide: []
}>()

// Stagger 动画延迟
const STAGGER_DELAY_MS = 60
const STAGGER_DELAY_MS_OFFSET = 250

function getAnimationDelay(index: number): string {
  return `${STAGGER_DELAY_MS_OFFSET + index * STAGGER_DELAY_MS}ms`
}
</script>

<template>
  <div v-if="!hidden && (loading || suggestions.length > 0)" class="suggestions-wrapper">
    <!-- Loading 状态 -->
    <div v-if="loading" class="suggestions-loading">
      <span class="loading-text">{{ t('aiChat.generatingSuggestions') }}</span>
    </div>

    <!-- 建议列表 -->
    <div v-else class="suggestions-list">
      <SuggestionChip
        v-for="(suggestion, index) in suggestions"
        :key="suggestion"
        :text="suggestion"
        :animation-delay="getAnimationDelay(index)"
        @click="emit('select', suggestion)"
      />
      <!-- 关闭按钮 -->
      <Button class="close-btn" size="small" plain @click="emit('hide')">
        <IIcon icon="x" />
      </Button>
    </div>
  </div>
</template>

<style scoped>
.suggestions-wrapper {
  display: flex;
  justify-content: center;
  padding: 8px 16px;
}

.suggestions-loading {
  display: flex;
  align-items: center;
  padding: 8px 16px;
  background: var(--card-bg);
  border-radius: 20px;
  font-size: 12px;
  color: var(--text-secondary);
}

.suggestions-list {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 8px;
  max-width: 100%;
}

.close-btn {
  border-radius: 20px;
  padding: 4px 8px;
}

/* 375px */
@media (max-width: 375px) {
  .suggestions-list {
    gap: 6px;
  }
}
</style>