<template>
  <div class="settings-page">
    <PageHeader title="设置" />

    <van-cell-group inset>
      <van-cell title="分类管理" icon="apps-o" is-link to="/settings/categories" />
      <van-cell title="标签管理" icon="label-o" is-link to="/settings/tags" />
    </van-cell-group>

    <van-cell-group inset class="section">
      <van-cell title="当前用户" :value="authStore.user?.display_name" />
      <van-cell title="用户名" :value="authStore.user?.username" />
      <van-cell title="角色" :value="authStore.user?.role === 'owner' ? '管理员' : '成员'" />
    </van-cell-group>

    <div class="actions">
      <van-button block type="danger" plain @click="onLogout">
        退出登录
      </van-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { showConfirmDialog } from 'vant'
import { useAuthStore } from '@/stores/auth'
import PageHeader from '@/components/common/PageHeader.vue'

const authStore = useAuthStore()

async function onLogout() {
  try {
    await showConfirmDialog({ title: '确认', message: '确定要退出登录吗？' })
    authStore.logout()
  } catch {
    // cancelled
  }
}
</script>

<style scoped>
.settings-page {
  background: #f7f8fa;
  min-height: 100vh;
}
.section {
  margin-top: 12px;
}
.actions {
  padding: 24px 16px;
}
</style>
