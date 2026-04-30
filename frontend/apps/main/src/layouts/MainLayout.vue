<template>
  <div class="main-layout">
    <router-view />
    <AppTabBar />
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import AppTabBar from '@/components/common/AppTabBar.vue'
import { useFamilyStore } from '@/stores/family'

const familyStore = useFamilyStore()

onMounted(() => {
  if (!familyStore.family) {
    familyStore.fetchFamily()
  }
})
</script>

<style scoped>
.main-layout {
  min-height: 100vh;
  padding-bottom: calc(50px + env(safe-area-inset-bottom));
  background-color: var(--bg-secondary);
}
</style>
