<template>
  <BaseEdge :id="id" :path="path" :style="edgeStyle" />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { BaseEdge, getSmoothStepPath, type EdgeProps } from '@vue-flow/core'

const props = defineProps<EdgeProps>()

const path = computed(() => {
  const [edgePath] = getSmoothStepPath({
    sourceX: props.sourceX,
    sourceY: props.sourceY,
    targetX: props.targetX,
    targetY: props.targetY,
    sourcePosition: props.sourcePosition,
    targetPosition: props.targetPosition,
    borderRadius: 8,
  })
  return edgePath
})

const edgeStyle = computed(() => {
  const isError = props.data?.isError === true
  return {
    stroke: isError ? 'var(--color-error, #ee0a24)' : 'var(--van-primary-color, #646cff)',
    strokeWidth: 2,
    strokeDasharray: '8 4',
    animation: 'flow-dash 1.5s linear infinite',
    markerEnd: 'url(#arrow-primary)',
  }
})
</script>

<style>
@keyframes flow-dash {
  to {
    stroke-dashoffset: -24;
  }
}

@media (prefers-reduced-motion: reduce) {
  .vue-flow__edge path {
    animation: none !important;
  }
}
</style>
