<template>
  <div class="change-password-page">
    <PageHeader title="账户密码" />

    <!-- Change password -->
    <van-cell-group inset title="修改密码" class="section">
      <van-field
        v-model="form.oldPassword"
        :type="showOld ? 'text' : 'password'"
        label="当前密码"
        placeholder="请输入当前密码"
        autocomplete="current-password"
      >
        <template #right-icon>
          <van-icon :name="showOld ? 'eye-o' : 'closed-eye'" @click="showOld = !showOld" />
        </template>
      </van-field>
      <van-field
        v-model="form.newPassword"
        :type="showNew ? 'text' : 'password'"
        label="新密码"
        placeholder="至少 8 位，含字母和数字"
        autocomplete="new-password"
      >
        <template #right-icon>
          <van-icon :name="showNew ? 'eye-o' : 'closed-eye'" @click="showNew = !showNew" />
        </template>
      </van-field>
      <van-field
        v-model="form.confirmPassword"
        :type="showConfirm ? 'text' : 'password'"
        label="确认新密码"
        placeholder="再次输入新密码"
        autocomplete="new-password"
      >
        <template #right-icon>
          <van-icon :name="showConfirm ? 'eye-o' : 'closed-eye'" @click="showConfirm = !showConfirm" />
        </template>
      </van-field>
    </van-cell-group>

    <div class="action-area">
      <van-button
        round
        block
        type="primary"
        :loading="changingPassword"
        :disabled="!canChangePassword"
        @click="onChangePassword"
      >
        确认修改
      </van-button>
    </div>

    <!-- Reset password via notification -->
    <van-cell-group inset title="忘记密码" class="section">
      <van-cell
        title="通过通知渠道重置密码"
        label="系统将生成临时密码并发送到已配置的通知渠道"
        is-link
        @click="onResetPassword"
      />
    </van-cell-group>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { showToast, showConfirmDialog } from 'vant'
import http from '@/api/index'
import PageHeader from '@/components/common/PageHeader.vue'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const form = ref({ oldPassword: '', newPassword: '', confirmPassword: '' })
const showOld = ref(false)
const showNew = ref(false)
const showConfirm = ref(false)
const changingPassword = ref(false)
const resettingPassword = ref(false)

const canChangePassword = computed(() =>
  form.value.oldPassword.length > 0 &&
  form.value.newPassword.length >= 8 &&
  form.value.newPassword === form.value.confirmPassword
)

async function onChangePassword() {
  if (form.value.newPassword !== form.value.confirmPassword) {
    showToast({ type: 'fail', message: '两次输入的密码不一致' })
    return
  }
  try {
    await showConfirmDialog({ message: '修改密码后需要重新登录，确认继续？' })
  } catch {
    return
  }
  changingPassword.value = true
  try {
    await http.post('/auth/me/password', {
      old_password: form.value.oldPassword,
      new_password: form.value.newPassword,
    })
    showToast({ type: 'success', message: '密码已修改，请重新登录' })
    authStore.logout({ onLogout: () => router.push('/login') })
  } catch (e: unknown) {
    const err = e as { response?: { data?: { code?: string; message?: string } } }
    const code = err.response?.data?.code
    if (code === 'AUTH_PASSWORD_INCORRECT') {
      showToast({ type: 'fail', message: '当前密码错误' })
    } else {
      showToast({ type: 'fail', message: err.response?.data?.message || '修改失败，请重试' })
    }
  } finally {
    changingPassword.value = false
  }
}

async function onResetPassword() {
  try {
    await showConfirmDialog({
      message: '系统将生成临时密码并通过通知渠道发送，当前密码将失效，确认继续？',
    })
  } catch {
    return
  }
  resettingPassword.value = true
  try {
    await http.post('/auth/me/password/reset')
    showToast({ type: 'success', message: '临时密码已发送，请重新登录' })
    authStore.logout({ onLogout: () => router.push('/login') })
  } catch (e: unknown) {
    const err = e as { response?: { data?: { code?: string; message?: string } } }
    const code = err.response?.data?.code
    if (code === 'NOTIFICATION_NO_CHANNEL') {
      showToast({ type: 'fail', message: '未配置通知渠道，请先在设置中添加通知渠道' })
    } else {
      showToast({ type: 'fail', message: err.response?.data?.message || '重置失败，请重试' })
    }
  } finally {
    resettingPassword.value = false
  }
}
</script>

<style scoped>
.change-password-page {
  min-height: 100vh;
  background: var(--van-background);
}

.section {
  margin-top: 12px;
}

.action-area {
  padding: 16px;
}
</style>
