<template>
  <div class="badge-wall">
    <BadgeDimension
      v-for="dim in dimensions"
      :key="dim.dimension"
      :dimension="dim.dimension"
      :current-badge="dim.current_badge"
      :history="dim.history"
      :next-badge="dim.next_badge"
    />
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'BadgeWall' })

import BadgeDimension from './BadgeDimension.vue'
import type { BadgeDimensionData } from '@/api/literacy'

defineProps<{
  dimensions: BadgeDimensionData[]
}>()
</script>

<style scoped>
.badge-wall {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
}
</style>
