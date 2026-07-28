<template>
  <div class="child-selector" v-if="children.length > 1">
    <van-tabs
      v-model:active="activeIndex"
      shrink
      @change="onTabChange"
    >
      <van-tab
        v-for="child in children"
        :key="child.child_id"
        :title="child.display_name"
      />
    </van-tabs>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ReportChild } from '@/api/literacy'

const props = defineProps<{
  children: ReportChild[]
  selectedChildId: string
}>()

const emit = defineEmits<{
  'update:selectedChildId': [childId: string]
}>()

const activeIndex = computed({
  get: () => {
    const idx = props.children.findIndex(c => c.child_id === props.selectedChildId)
    return idx >= 0 ? idx : 0
  },
  set: () => { /* managed by van-tabs via v-model */ }
})

function onTabChange(index: number) {
  const child = props.children[index]
  if (child) {
    emit('update:selectedChildId', child.child_id)
  }
}
</script>

<style scoped>
.child-selector {
  padding: 8px 0;
}
</style>
