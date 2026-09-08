<template>
  <div :class="[baseClass, isDimmed ? nodeClasses.dimmed : '']">
    <div class="flow-node__icon">
      <van-icon name="replay" />
    </div>
    <div class="flow-node__label">{{ t('manifesto.flow.modifying') }}</div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { NodeProps } from '@vue-flow/core'
import { nodeClasses, NODE_WIDTH } from './flowNodeStyles'

const { t } = useI18n()

const props = defineProps<NodeProps>()

const baseClass = computed(() => nodeClasses.modifying)
const isDimmed = computed<boolean>(() => props.data?.dimmed === true)
</script>

<style scoped>
.flow-node--modifying {
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

.flow-node__label {
  white-space: nowrap;
}
</style>
