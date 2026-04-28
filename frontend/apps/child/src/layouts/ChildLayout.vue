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
      :show-cancel-button="!hasAdminChildView"
      :confirm-button-loading="returning"
      @confirm="handleReturnToAdult"
    >
      <div v-if="!hasAdminChildView" style="padding: 16px">
        <van-field
          v-model="parentPassword"
          type="password"
          placeholder="请输入大人的密码"
          :error-message="returnError"
        />
      </div>
      <div v-else style="padding: 16px; text-align: center">
        确定返回大人模式？
      </div>
    </van-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import ChildTabBar from '@/components/ChildTabBar.vue'
import { useChildAuthStore } from '@numina/auth'
import { clearAuth } from '@numina/auth'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
const childAuthStore = useChildAuthStore()

const showReturnModal = ref(false)
const parentPassword = ref('')
const returnError = ref('')
const returning = ref(false)
const hasAdminChildView = computed(() => localStorage.getItem('admin_child_view') !== null)

async function handleReturnToAdult() {
  if (returning.value) return
  returning.value = true
  const adminChildView = localStorage.getItem('admin_child_view')

  if (adminChildView) {
    // 管理员视角切换 - 直接返回，无需密码验证
    showReturnModal.value = false
    localStorage.removeItem('admin_child_view')
    clearAuth()
    window.location.href = '/'
    return
  }

  // 真实孩子登录 - 需要密码验证（现有流程保持不变）
  returnError.value = ''
  try {
    await childAuthStore.returnToAdult(parentPassword.value)
    clearAuth()
    window.location.href = '/'
  } catch {
    returnError.value = t('errors.wrongPassword')
    returning.value = false
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
