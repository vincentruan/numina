<template>
  <g class="topic-constellation">
    <!-- Prerequisite edges as connecting lines (R9) — drawn under the nodes -->
    <path
      v-for="(edge, i) in edgePaths"
      :key="`edge-${i}`"
      class="topic-constellation__edge"
      :d="edge.path"
    />
    <!-- Topic nodes (R9, R10 — isolated nodes remain as points) -->
    <g
      v-for="node in nodesWithPositions"
      :key="node.id"
      class="topic-constellation__node"
      :class="[
        `topic-constellation__node--${masteryStatus({ mastery_level: node.masteryLevel })}`,
        { 'topic-constellation__node--isolated': !node.connected },
      ]"
      :transform="`translate(${node.x * viewWidth}, ${node.y * viewHeight})`"
      :tabindex="0"
      role="button"
      :aria-label="node.displayName"
      @click="$emit('selectTopic', { id: node.id })"
      @keydown.enter="$emit('selectTopic', { id: node.id })"
    >
      <circle class="topic-constellation__star" r="11" />
      <text
        class="topic-constellation__label"
        y="24"
        text-anchor="middle"
      >{{ node.displayName }}</text>
    </g>
  </g>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { layoutConstellation } from '@/utils/constellationLayout'
import { masteryStatus } from '@/utils/masteryStatus'

export interface ConstellationTopic {
  id: string
  displayName: string
  masteryLevel: string
}

export interface ConstellationEdge {
  topic_id: string
  prerequisite_id: string
  strength: string | null
}

const props = defineProps<{
  topics: ConstellationTopic[]
  edges: ConstellationEdge[]
  viewWidth: number
  viewHeight: number
}>()

defineEmits<{
  selectTopic: [payload: { id: string }]
}>()

const layout = computed(() =>
  layoutConstellation(
    props.topics.map((t) => t.id),
    props.edges.map((e) => ({ from: e.prerequisite_id, to: e.topic_id })),
  ),
)

const nodesWithPositions = computed(() => {
  const byId = new Map(layout.value.nodes.map((n) => [n.id, n]))
  return props.topics.map((t) => {
    const pos = byId.get(t.id) ?? { x: 0.5, y: 0.9, connected: false }
    return { ...t, x: pos.x, y: pos.y, connected: pos.connected }
  })
})

const edgePaths = computed(() => {
  const nodes = new Map(layout.value.nodes.map((n) => [n.id, n]))
  return layout.value.edges
    .map((e) => {
      const from = nodes.get(e.from)
      const to = nodes.get(e.to)
      if (!from || !to) return null
      const x1 = from.x * props.viewWidth
      const y1 = from.y * props.viewHeight
      const x2 = to.x * props.viewWidth
      const y2 = to.y * props.viewHeight
      const midX = (x1 + x2) / 2
      return {
        from: e.from,
        to: e.to,
        path: `M ${x1} ${y1} C ${midX} ${y1}, ${midX} ${y2}, ${x2} ${y2}`,
      }
    })
    .filter((p): p is { from: string; to: string; path: string } => p !== null)
})

</script>

<style scoped>
.topic-constellation__edge {
  fill: none;
  stroke: var(--constellation-edge-color);
  stroke-width: 1.5;
  stroke-dasharray: 4 3;
  pointer-events: none;
}

.topic-constellation__node {
  cursor: pointer;
  outline: none;
}

.topic-constellation__star {
  fill: var(--color-brand-lavender, #b8a4ed);
  stroke: var(--color-brand-lavender, #b8a4ed);
  stroke-width: 2;
  transition: fill 0.2s ease;
}

.topic-constellation__node--mastered .topic-constellation__star {
  fill: var(--color-brand-ochre, #e8b94a);
  stroke: var(--color-brand-ochre);
}

.topic-constellation__node--learning .topic-constellation__star {
  fill: var(--color-primary, #0a0a0a);
  stroke: var(--color-primary, #0a0a0a);
}

.topic-constellation__node--locked .topic-constellation__star {
  fill: var(--color-body, #3a3a3a);
  stroke: var(--color-body);
  opacity: 0.75;
}

.topic-constellation__node--isolated .topic-constellation__star {
  stroke-dasharray: 2 2;
}

.topic-constellation__node:focus-visible .topic-constellation__star {
  stroke: var(--color-primary, #0a0a0a);
  stroke-width: 2.5;
}

.topic-constellation__label {
  font-family: Inter, sans-serif;
  font-size: 9px;
  fill: var(--color-ink, #0a0a0a);
  paint-order: stroke;
  stroke: var(--constellation-label-outline);
  stroke-width: 2px;
  pointer-events: none;
}
</style>
