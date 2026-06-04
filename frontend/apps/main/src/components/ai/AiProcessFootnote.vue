<template>
  <div class="ai-process-footnote">
    <!-- Collapsed header row -->
    <div
      class="footnote-header"
      role="button"
      :aria-expanded="expanded"
      :aria-label="headerLabel"
      tabindex="0"
      @click="onToggle"
      @keydown.enter="onToggle"
      @keydown.space.prevent="onToggle"
    >
      <van-icon name="description" class="footnote-icon" />
      <span class="footnote-text">{{ headerLabel }}</span>
      <van-icon :name="expanded ? 'arrow-up' : 'arrow-down'" class="footnote-chevron" />
    </div>

    <!-- Expanded body: AiProcessBlock -->
    <Transition name="footnote-body">
      <div v-if="expanded" class="footnote-body">
        <AiProcessBlock
          :status="status"
          :elapsed-ms="elapsedMs"
          :steps="steps"
          :default-expanded="true"
          :phase="phase"
        />
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import AiProcessBlock from './AiProcessBlock.vue'
import type { ProcessStep } from '@/types/agent-stream'

const props = withDefaults(
  defineProps<{
    stepCount: number
    expanded?: boolean
    status?: 'running' | 'done' | 'error'
    elapsedMs?: number
    steps?: ProcessStep[]
    phase?: 'connecting' | 'thinking' | 'answering' | 'done' | 'error'
  }>(),
  {
    expanded: false,
    status: 'done',
    elapsedMs: 0,
    steps: () => [],
    phase: 'done',
  }
)

const emit = defineEmits<{
  (e: 'toggle', expanded: boolean): void
}>()

const { t } = useI18n()

const headerLabel = computed(() => {
  return t('aiProcess.viewProcess', { count: props.stepCount })
})

function onToggle() {
  emit('toggle', !props.expanded)
}
</script>

<style scoped>
.ai-process-footnote {
  margin-top: 8px;
  border-radius: 4px;
  background: var(--bg-secondary);
  border: 1px solid var(--separator);
  overflow: hidden;
}

.footnote-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  cursor: pointer;
  user-select: none;
  transition: background 0.2s ease;
}

.footnote-header:hover {
  background: var(--card-bg);
}

.footnote-header:focus-visible {
  outline: 2px solid var(--van-primary-color);
  outline-offset: 2px;
}

.footnote-icon {
  font-size: 14px;
  color: var(--text-secondary);
}

.footnote-text {
  flex: 1;
  font-size: 12px;
  color: var(--text-secondary);
  white-space: nowrap;
}

.footnote-chevron {
  font-size: 14px;
  color: var(--text-secondary);
  transition: transform 0.2s ease;
}

.footnote-body {
  border-top: 1px solid var(--separator);
  padding: 8px 12px;
}

/* Expand/collapse transition */
.footnote-body-enter-active,
.footnote-body-leave-active {
  transition: max-height 0.3s ease, opacity 0.2s ease;
  overflow: hidden;
}

.footnote-body-enter-from,
.footnote-body-leave-to {
  max-height: 0;
  opacity: 0;
}

.footnote-body-enter-to,
.footnote-body-leave-from {
  max-height: 800px;
  opacity: 1;
}

/* Mobile responsive */
@media (max-width: 768px) {
  .footnote-header {
    padding: 6px 10px;
    gap: 4px;
  }

  .footnote-icon,
  .footnote-chevron {
    font-size: 12px;
  }

  .footnote-text {
    font-size: 11px;
  }

  .footnote-body {
    padding: 6px 10px;
  }
}
</style>