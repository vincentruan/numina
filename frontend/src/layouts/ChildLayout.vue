<template>
  <div class="child-layout">
    <div class="return-adult-btn" @click="showReturnModal = true">
      <van-icon name="arrow-left" /> 大人模式
    </div>
    <router-view />
    <ChildTabBar />

    <van-dialog
      v-model:show="showReturnModal"
      title="返回大人模式"
      show-cancel-button
      @confirm="handleReturnToAdult"
    >
      <div style="padding: 16px">
        <van-field
          v-model="parentPassword"
          type="password"
          placeholder="请输入大人的密码"
          :error-message="returnError"
        />
      </div>
    </van-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import ChildTabBar from '@/components/child/ChildTabBar.vue'
import { useChildAuthStore } from '@/stores/childAuth'
import { clearAuth } from '@/utils/storage'

const childAuthStore = useChildAuthStore()

const showReturnModal = ref(false)
const parentPassword = ref('')
const returnError = ref('')

async function handleReturnToAdult() {
  returnError.value = ''
  try {
    await childAuthStore.returnToAdult(parentPassword.value)
    clearAuth()
    window.location.href = '/'
  } catch {
    returnError.value = '密码错误，请重试'
  }
}
</script>

<style scoped>
.child-layout {
  min-height: 100vh;
  padding-bottom: calc(50px + env(safe-area-inset-bottom));
  background: #FFF9E6;
}

.return-adult-btn {
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
