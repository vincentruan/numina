<template>
  <div :class="[nodeClasses.signing, isActive ? nodeClasses.signingActive : '', isDimmed ? nodeClasses.dimmed : '']">
    <div class="flow-signing__header">
      <van-icon name="edit" />
      <span class="flow-signing__title">{{ t('manifesto.flow.signing', { n: round }) }}</span>
    </div>
    <div class="flow-signing__progress">
      {{ t('manifesto.flow.progress', { signed: progress.signed, total: progress.total }) }}
    </div>
    <MemberStatusList :members="memberStates" />
    <div v-if="deadline" class="flow-signing__deadline" :class="{ 'flow-signing__deadline--expired': deadlineExpired }">
      <van-icon name="clock-o" />
      <span v-if="deadlineExpired">{{ t('manifesto.flow.deadlineExpired') }}</span>
      <span v-else>{{ t('manifesto.flow.deadline') }}: {{ deadline }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { NodeProps } from '@vue-flow/core'
import { nodeClasses, NODE_WIDTH } from './flowNodeStyles'
import MemberStatusList from './MemberStatusList.vue'
import type { FlowMemberState, FlowSigningProgress } from '@/types/manifesto'

const { t } = useI18n()

const props = defineProps<NodeProps>()

const memberStates = computed<FlowMemberState[]>(() => props.data?.memberStates ?? [])
const progress = computed<FlowSigningProgress>(() => props.data?.progress ?? { signed: 0, total: 0 })
const round = computed<number>(() => props.data?.round ?? 1)
const deadline = computed<string | null>(() => props.data?.deadline ?? null)
const deadlineExpired = computed<boolean>(() => props.data?.deadlineExpired === true)
const isActive = computed<boolean>(() => props.data?.isActive === true)
const isDimmed = computed<boolean>(() => props.data?.dimmed === true)
</script>

<style scoped>
.flow-node--signing {
  width: v-bind(NODE_WIDTH);
  padding: 14px 16px;
  border-radius: 14px;
  background: var(--card-bg, #f5f5ff);
  border: 1.5px solid var(--card-bg, #e0e0f0);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.flow-node--active {
  border-color: var(--van-primary-color, #646cff);
  box-shadow: 0 0 0 2px rgba(100, 108, 255, 0.15), 0 4px 12px rgba(0, 0, 0, 0.08);
  animation: flow-pulse 2.5s ease-in-out infinite;
}

.flow-node--dimmed {
  opacity: 0.5;
}

@keyframes flow-pulse {
  0%, 100% { box-shadow: 0 0 0 2px rgba(100, 108, 255, 0.15), 0 4px 12px rgba(0, 0, 0, 0.08); }
  50% { box-shadow: 0 0 0 4px rgba(100, 108, 255, 0.25), 0 4px 16px rgba(0, 0, 0, 0.12); }
}

@media (prefers-reduced-motion: reduce) {
  .flow-node--active {
    animation: none;
  }
}

.flow-signing__header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary, #0a0a0a);
}

.flow-signing__progress {
  font-size: 13px;
  color: var(--text-secondary, #616161);
}

.flow-signing__deadline {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--text-secondary, #616161);
  padding-top: 4px;
  border-top: 1px solid rgba(0, 0, 0, 0.06);
}

.flow-signing__deadline--expired {
  color: var(--color-error, #ee0a24);
}
</style>
