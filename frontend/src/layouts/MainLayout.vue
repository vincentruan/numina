<template>
  <div class="main-layout">
    <div class="switch-child-btn" @click="router.push('/child/select')">
      <van-icon name="friends-o" /> 切换到孩子视角
    </div>
    <router-view />
    <AppTabBar />
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import AppTabBar from '@/components/common/AppTabBar.vue'
import { useFamilyStore } from '@/stores/family'

const router = useRouter()
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

.switch-child-btn {
  position: fixed;
  top: 12px;
  right: 16px;
  z-index: 100;
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  background: rgba(255, 255, 255, 0.9);
  border-radius: 20px;
  font-size: 13px;
  color: #666;
  cursor: pointer;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}
</style>
