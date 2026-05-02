<template>
  <div class="change-second-factor-page">
    <PageHeader title="二阶段验证" />

    <!-- Current status -->
    <van-cell-group inset title="当前状态" class="section">
      <van-cell
        title="数字 PIN"
        :value="hasPinEnabled ? '已启用' : '未设置'"
        :label="hasPinEnabled ? '登录时需要输入 6 位数字 PIN' : '设置后登录时需要输入 PIN 验证身份'"
      >
        <template #right-icon>
          <van-tag :type="hasPinEnabled ? 'success' : 'default'">
            {{ hasPinEnabled ? '已启用' : '未设置' }}
          </van-tag>
        </template>
      </van-cell>
    </van-cell-group>

    <!-- Setup / Change PIN -->
    <van-cell-group inset :title="hasPinEnabled ? '修改 PIN' : '设置 PIN'" class="section">
      <template v-if="hasPinEnabled">
        <van-field
          v-model="form.oldPin"
          type="password"
          label="当前 PIN"
          placeholder="请输入当前 6 位 PIN"
          maxlength="6"
          inputmode="numeric"
        />
      </template>
      <van-field
        v-model="form.newPin"
        type="password"
        label="新 PIN"
        placeholder="请输入 6 位数字"
        maxlength="6"
        inputmode="numeric"
      />
      <van-field
        v-model="form.confirmPin"
        type="password"
        label="确认 PIN"
        placeholder="再次输入 6 位数字"
        maxlength="6"
        inputmode="numeric"
      />
    </van-cell-group>

    <div class="action-area">
      <van-button
        round
        block
        type="primary"
        :loading="saving"
        :disabled="!canSave"
        @click="onSave"
      >
        {{ hasPinEnabled ? '修改 PIN' : '启用 PIN' }}
      </van-button>
    </div>

    <!-- Disable PIN -->
    <van-cell-group v-if="hasPinEnabled" inset title="危险操作" class="section">
      <van-cell
        title="禁用二阶段验证"
        label="禁用后登录将不再需要 PIN 验证"
        is-link
        class="danger-cell"
        @click="onDisablePin"
      />
    </van-cell-group>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { showToast, showConfirmDialog } from 'vant'
import http from '@/api/index'
import PageHeader from '@/components/common/PageHeader.vue'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()

const hasPinEnabled = computed(() => authStore.user?.second_factor_enabled === true)

const form = ref({ oldPin: '', newPin: '', confirmPin: '' })
const saving = ref(false)

const canSave = computed(() => {
  const { oldPin, newPin, confirmPin } = form.value
  if (newPin.length !== 6 || !/^\d{6}$/.test(newPin)) return false
  if (newPin !== confirmPin) return false
  if (hasPinEnabled.value && oldPin.length !== 6) return false
  return true
})

async function onSave() {
  if (form.value.newPin !== form.value.confirmPin) {
    showToast({ type: 'fail', message: '两次输入的 PIN 不一致' })
    return
  }
  saving.value = true
  try {
    if (hasPinEnabled.value) {
      await http.post('/auth/pin/change', {
        old_pin: form.value.oldPin,
        new_pin: form.value.newPin,
      })
      showToast({ type: 'success', message: 'PIN 已修改' })
    } else {
      await http.post('/auth/pin/setup', { pin: form.value.newPin })
      showToast({ type: 'success', message: 'PIN 已启用' })
      await authStore.fetchMe()
    }
    form.value = { oldPin: '', newPin: '', confirmPin: '' }
  } catch (e: unknown) {
    const err = e as { response?: { data?: { code?: string; message?: string } } }
    const code = err.response?.data?.code
    if (code === 'AUTH_INVALID_CREDENTIALS' || code === 'AUTH_PASSWORD_INCORRECT') {
      showToast({ type: 'fail', message: '当前 PIN 错误' })
    } else {
      showToast({ type: 'fail', message: err.response?.data?.message || '操作失败，请重试' })
    }
  } finally {
    saving.value = false
  }
}

async function onDisablePin() {
  try {
    await showConfirmDialog({ message: '禁用后登录将不再需要 PIN 验证，确认继续？' })
  } catch {
    return
  }
  saving.value = true
  try {
    await http.post('/auth/pin/disable')
    showToast({ type: 'success', message: '二阶段验证已禁用' })
    await authStore.fetchMe()
  } catch (e: unknown) {
    const err = e as { response?: { data?: { message?: string } } }
    showToast({ type: 'fail', message: err.response?.data?.message || '操作失败，请重试' })
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.change-second-factor-page {
  min-height: 100vh;
  background: var(--van-background);
}

.section {
  margin-top: 12px;
}

.action-area {
  padding: 16px;
}

.danger-cell :deep(.van-cell__title) {
  color: var(--van-danger-color);
}
</style>
