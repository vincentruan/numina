<template>
  <div :class="[baseClass, isDimmed ? nodeClasses.dimmed : '']">
    <div class="flow-node__icon flow-effective__icon">
      <van-icon name="checked" />
    </div>
    <div class="flow-node__label">{{ t('manifesto.flow.effective') }}</div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { NodeProps } from '@vue-flow/core'
import { nodeClasses, NODE_WIDTH } from './flowNodeStyles'

const { t } = useI18n()

const props = defineProps<NodeProps>()

const baseClass = computed(() => nodeClasses.effective)
const isDimmed = computed<boolean>(() => props.data?.dimmed === true)
</script>

<style scoped>
.flow-node--effective {
  width: v-bind(NODE_WIDTH);
  padding: 12px 16px;
  border-radius: 12px;
  background: rgba(25, 173, 77, 0.06);
  border: 1.5px solid var(--color-success, #19ad4d);
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
  font-weight: 500;
  color: var(--color-success, #19ad4d);
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
