<template>
  <div class="child-layout">
    <router-view v-slot="{ Component, route }">
      <Transition name="page-fade" mode="out-in">
        <KeepAlive :include="cachedTabs">
          <component :is="Component" :key="route.path" />
        </KeepAlive>
      </Transition>
    </router-view>
    <ChildTabBar />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import ChildTabBar from '@/components/ChildTabBar.vue'

const cachedTabs = ref<string[]>([
  'ChildHome',
  'ChildTasks',
  'ChildLedger',
  'ChildWishes',
  'ChildTreasures',
])
</script>

<style scoped>
.child-layout {
  min-height: 100vh;
  padding-bottom: calc(50px + env(safe-area-inset-bottom));
  background: var(--color-canvas);
}

.page-fade-enter-active,
.page-fade-leave-active {
  transition: opacity 0.15s ease;
}

.page-fade-enter-from,
.page-fade-leave-to {
  opacity: 0;
}
</style>
