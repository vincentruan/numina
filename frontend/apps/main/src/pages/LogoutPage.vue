<script setup lang="ts">
/**
 * LogoutPage - 登出确认页面
 * 通过 /logout 路由访问，确认后执行登出并跳转到登录页
 */
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { showConfirmDialog } from 'vant'
import { useI18n } from 'vue-i18n'

const router = useRouter()
const authStore = useAuthStore()
const { t } = useI18n()

onMounted(async () => {
  try {
    await showConfirmDialog({
      title: t('common.confirm'),
      message: t('settings.logoutConfirm'),
      confirmButtonText: t('common.confirm'),
      cancelButtonText: t('common.cancel'),
    })
    // 用户确认登出
    authStore.logout({ onLogout: () => router.replace('/login') })
  } catch {
    // 用户取消，返回上一页
    router.back()
  }
})
</script>

<template>
  <div class="logout-page">
    <van-loading type="spinner" size="24px" />
    <p class="logout-text">{{ t('settings.processing') || '处理中...' }}</p>
  </div>
</template>

<style scoped>
.logout-page {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  gap: 16px;
}

.logout-text {
  color: var(--van-text-color-2);
  font-size: 14px;
  margin: 0;
}
</style>
