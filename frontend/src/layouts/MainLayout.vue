<template>
  <div class="main-layout">
    <router-view />
    <AppTabBar />
  </div>
</template>

<script setup lang="ts">
import AppTabBar from '@/components/common/AppTabBar.vue'
</script>

<style scoped>
.main-layout {
  min-height: 100vh;
  padding-bottom: 50px;
  background-color: #f7f8fa;
}
</style>
