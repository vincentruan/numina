<template>
  <div :class="[baseClass, isDimmed ? nodeClasses.dimmed : '']">
    <div class="flow-node__icon">
      <van-icon name="clock-o" />
    </div>
    <div class="flow-pending__content">
      <div class="flow-node__label">{{ t('manifesto.flow.pendingEffective') }}</div>
      <div v-if="deadline" class="flow-pending__deadline" :class="{ 'flow-pending__deadline--expired': deadlineExpired }">
        <span v-if="deadlineExpired">{{ t('manifesto.flow.deadlineExpired') }}</span>
        <span v-else>{{ t('manifesto.flow.deadline') }}: {{ deadline }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { NodeProps } from '@vue-flow/core'
import { nodeClasses, NODE_WIDTH } from './flowNodeStyles'

const { t } = useI18n()

const props = defineProps<NodeProps>()

const baseClass = 'flow-node--pending'
const isDimmed = computed<boolean>(() => props.data?.dimmed === true)
const deadline = computed<string | null>(() => props.data?.deadline ?? null)
const deadlineExpired = computed<boolean>(() => props.data?.deadlineExpired === true)
</script>

<style scoped>
.flow-node--pending {
  width: v-bind(NODE_WIDTH);
  padding: 12px 16px;
  border-radius: 12px;
  background: var(--card-bg, #f5f5ff);
  border: 1.5px dashed var(--text-secondary, #616161);
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
  color: var(--text-secondary, #616161);
}

.flow-node--dimmed {
  opacity: 0.5;
}

.flow-node__icon {
  font-size: 18px;
  flex-shrink: 0;
}

.flow-pending__content {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.flow-node__label {
  font-weight: 500;
}

.flow-pending__deadline {
  font-size: 12px;
}

.flow-pending__deadline--expired {
  color: var(--color-error, #ee0a24);
}
</style>
