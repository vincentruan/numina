<template>
  <div class="child-layout">
    <router-view />
    <ChildTabBar />
  </div>
</template>

<script setup lang="ts">
import ChildTabBar from '@/components/ChildTabBar.vue'
</script>

<style scoped>
.child-layout {
  min-height: 100vh;
  padding-bottom: calc(50px + env(safe-area-inset-bottom));
  background: var(--color-canvas);
}
</style>
