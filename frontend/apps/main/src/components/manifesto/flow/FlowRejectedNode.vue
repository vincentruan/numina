<template>
  <div :class="[baseClass, isDimmed ? nodeClasses.dimmed : '']">
    <div class="flow-rejected__header">
      <van-icon name="close" />
      <span>{{ t('manifesto.flow.rejected') }}</span>
    </div>
    <div v-if="rejections.length" class="flow-rejected__list">
      <div v-for="rej in rejections" :key="rej.userId" class="flow-rejected__item">
        <span class="flow-rejected__name">{{ rej.displayName }}</span>
        <span v-if="rej.rejectionReason" class="flow-rejected__reason">: {{ rej.rejectionReason }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { NodeProps } from '@vue-flow/core'
import { nodeClasses, NODE_WIDTH } from './flowNodeStyles'
import type { FlowMemberState } from '@/types/manifesto'

const { t } = useI18n()

const props = defineProps<NodeProps>()

const rejections = computed<FlowMemberState[]>(() =>
  (props.data?.memberStates ?? []).filter((m: FlowMemberState) => m.status === 'rejected'),
)
const baseClass = computed(() => nodeClasses.rejected)
const isDimmed = computed<boolean>(() => props.data?.dimmed === true)
</script>

<style scoped>
.flow-node--rejected {
  width: v-bind(NODE_WIDTH);
  padding: 12px 16px;
  border-radius: 12px;
  background: color-mix(in srgb, var(--color-error, #ee0a24) 6%, transparent);
  border: 1.5px solid var(--color-error, #ee0a24);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.flow-node--dimmed {
  opacity: 0.5;
}

.flow-rejected__header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-error, #ee0a24);
}

.flow-rejected__list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.flow-rejected__item {
  font-size: 13px;
  color: var(--text-primary, #0a0a0a);
}

.flow-rejected__name {
  font-weight: 500;
}

.flow-rejected__reason {
  color: var(--text-secondary, #616161);
}
</style>
