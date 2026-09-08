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

const edgeStyle = computed(() => ({
  stroke: 'var(--text-secondary, #c0c0c0)',
  strokeWidth: 1.5,
  opacity: 0.5,
  markerEnd: 'url(#arrow-muted)',
}))
</script>
