<template>
  <!-- Force van-tabs to re-mount when children arrive to avoid Vant's
       registration timing bug. The key changes from 0 to children.length,
       triggering a full re-mount with children already present. -->
  <div class="child-selector" v-show="children.length > 1">
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
import { ref, watch, getCurrentInstance } from 'vue'
import type { ReportChild } from '@/api/literacy'
import UserAvatar from '@/components/common/UserAvatar.vue'

const props = defineProps<{
  children: ReportChild[]
  selectedChildId: string
}>()

const emit = defineEmits<{
  'update:selectedChildId': [childId: string]
}>()

const instance = getCurrentInstance()

/**
 * Use a plain ref (not a computed) for v-model:active.
 * Vant's van-tabs writes to the active binding on internal tab lifecycle
 * events; a no-op computed setter leaves its internal index unsynced,
 * which after several tab switches causes
 * "Cannot destructure property 'title' of 'children[index]' as it is undefined."
 */
const activeIndex = ref(0)

// Watch children and force re-render after they arrive to work around
// Vant's registration timing bug where van-tabs + van-tab mount in the
// same patch and leave the nav as empty comments.
watch(
  () => props.children.length,
  (newLen) => {
    if (newLen > 1) {
      // Defer forceUpdate to next tick to ensure children are rendered first
      setTimeout(() => {
        instance?.proxy?.$forceUpdate()
      }, 0)
    }
  },
  { immediate: true },
)

// Sync activeIndex when props change (child switch from parent, or children array update)
watch(
  [() => props.selectedChildId, () => props.children],
  ([childId, kids]) => {
    const idx = kids.findIndex(c => c.child_id === childId)
    const next = idx >= 0 ? idx : 0
    if (activeIndex.value !== next) {
      activeIndex.value = next
    }
  },
  { immediate: true },
)

function onTabChange(index: number) {
  // Safety: guard against out-of-bounds (defence in depth for van-tabs quirks)
  const child = props.children[index]
  if (child && child.child_id !== props.selectedChildId) {
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
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 60px;
}
</style>
