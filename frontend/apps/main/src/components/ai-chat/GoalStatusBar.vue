<script setup lang="ts">
/**
 * GoalStatusBar — mobile-adapted active-goal status bar for /ai/chat (U5 / D1).
 *
 * DeerFlow parity (`frontend/src/components/workspace/goal-status.tsx`):
 * - TargetIcon + objective (truncated) + continuation chip.
 * - The continuation chip `续跑中 {count}/{max}` renders ONLY when
 *   `continuation_count > 0` (goal-status-helpers.ts:16-25); a raw "0/8"
 *   reads as a mysterious score, so it is hidden until the U4 auto-continuation
 *   loop has actually advanced at least once.
 *
 * Rendered above InputBox (co-located with TodoListBar) when `hasGoal` is true.
 * The goal state comes from `useActiveGoal` (optimistic override reconciled
 * with the server's checkpoint `channel_values["goal"]`).
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { GoalState } from '@/api/ai-chat'
import { getGoalContinuationDisplay } from '@/composables/ai-chat/useActiveGoal'

const props = defineProps<{
  goal: GoalState
}>()

const { t } = useI18n()

const continuation = computed(() => getGoalContinuationDisplay(props.goal))

const continuationLabel = computed(() => {
  if (!continuation.value) return ''
  return t('aiChat.goalContinuing')
    .replace('{count}', String(continuation.value.count))
    .replace('{max}', String(continuation.value.max))
})

const continuationTooltip = computed(() => {
  if (!continuation.value) return ''
  return t('aiChat.goalContinuationTooltip')
    .replace('{count}', String(continuation.value.count))
    .replace('{max}', String(continuation.value.max))
})
</script>

<template>
  <div
    class="goal-status-bar"
    role="status"
    :aria-label="t('aiChat.goalLabel')"
  >
    <span class="goal-status-bar__icon" aria-hidden="true">
      <!-- TargetIcon (lucide) -->
      <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="10" />
        <circle cx="12" cy="12" r="6" />
        <circle cx="12" cy="12" r="2" />
      </svg>
    </span>
    <div class="goal-status-bar__text" :title="props.goal.objective">
      <span class="goal-status-bar__label">{{ t('aiChat.goalLabel') }}</span>
      <span class="goal-status-bar__objective">{{ props.goal.objective }}</span>
    </div>
    <span
      v-if="continuation"
      class="goal-status-bar__chip"
      :title="continuationTooltip"
    >
      <!-- RefreshCwIcon (lucide) -->
      <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M21 12a9 9 0 1 1-2.64-6.36" />
        <path d="M21 3v6h-6" />
      </svg>
      <span class="goal-status-bar__count">{{ continuationLabel }}</span>
    </span>
  </div>
</template>

<style scoped>
.goal-status-bar {
  width: 100%;
  min-height: 40px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  border-top-left-radius: 12px;
  border-top-right-radius: 12px;
  border: 1px solid var(--van-border-color, #ebedf0);
  border-bottom: 0;
  background: var(--van-background-2, #fff);
  box-sizing: border-box;
}

.goal-status-bar__icon {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--van-primary-color, #1989fa);
}

.goal-status-bar__text {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  line-height: 1.4;
}

.goal-status-bar__label {
  flex: 0 0 auto;
  color: var(--van-text-color-2, #969799);
  white-space: nowrap;
}

.goal-status-bar__objective {
  flex: 1 1 auto;
  min-width: 0;
  font-weight: 500;
  color: var(--van-text-color, #323233);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.goal-status-bar__chip {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border-radius: 10px;
  background: var(--color-primary-soft, rgba(99, 102, 241, 0.1));
  color: var(--van-primary-color, #1989fa);
  font-size: 12px;
  line-height: 1.4;
  font-variant-numeric: tabular-nums;
}

.goal-status-bar__count {
  white-space: nowrap;
}

:global([data-theme='dark']) .goal-status-bar {
  background: var(--van-background-2, #1a1a2e);
  border-color: var(--van-border-color, rgba(255, 255, 255, 0.1));
}
</style>
