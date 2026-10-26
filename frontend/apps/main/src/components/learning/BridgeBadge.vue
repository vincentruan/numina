<template>
  <span
    :class="['bridge-badge', { 'bridge-badge--inferred': bridge.source_type === 'inferred' }]"
    @click="$emit('click', bridge)"
  >
    <span class="bridge-badge__icon">{{ bridge.source_type === 'inferred' ? inferredLabel : explicitLabel }}</span>
    <span class="bridge-badge__label">
      {{ subjectLabelFn(t, bridge.to_subject) }} {{ arrowLabel }} {{ domainLabelFn(t, bridge.to_cluster_domain) }}
    </span>
  </span>
</template>

<script setup lang="ts">
defineOptions({ name: 'BridgeBadge' })

import { useI18n } from 'vue-i18n'
import type { BridgeResponse } from '@/api/learning'
import { domainLabel as domainLabelFn, subjectLabel as subjectLabelFn } from '@/utils/domainLabel'

defineProps<{
  bridge: BridgeResponse
  explicitLabel: string
  inferredLabel: string
  arrowLabel: string
}>()

defineEmits<{
  click: [bridge: BridgeResponse]
}>()

const { t } = useI18n()
</script>

<style scoped>
.bridge-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  border: 1px solid var(--van-gray-3, #dee0e3);
  border-radius: 12px;
  background: var(--van-gray-1, #f7f8fa);
  font-size: 12px;
  color: var(--text-secondary);
}

.bridge-badge--inferred {
  border-style: dashed;
  opacity: 0.75;
}

.bridge-badge__icon {
  font-size: 11px;
}
</style>
