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
      >
        <template #title>
          <div class="child-tab-title">
            <UserAvatar
              :avatar-url="child.avatar_url ?? null"
              :avatar-color="child.avatar_color || '#FF6B6B'"
              :display-name="child.display_name || '?'"
              :size="24"
            />
            <span class="child-tab-name">{{ child.display_name }}</span>
          </div>
        </template>
      </van-tab>
    </van-tabs>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ReportChild } from '@/api/literacy'
import UserAvatar from '@/components/common/UserAvatar.vue'

const props = defineProps<{
  children: ReportChild[]
  selectedChildId: string
}>()

const emit = defineEmits<{
  'update:selectedChildId': [childId: string
]
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

.child-tab-title {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 2px;
}

.child-tab-name {
  font-size: 12px;
  font-weight: 600;
  line-height: 1.2;
  white-space: nowrap;
}
</style>
