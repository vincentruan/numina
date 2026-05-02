<template>
  <div class="change-second-factor-page">
    <PageHeader :title="t('secondFactor.title')" />

    <!-- Current status -->
    <van-cell-group inset :title="t('secondFactor.currentStatus')" class="section">
      <van-cell
        :title="t('secondFactor.digitalPin')"
        :label="hasPinEnabled ? t('secondFactor.pinEnabledLabel') : t('secondFactor.pinDisabledLabel')"
      >
        <template #right-icon>
          <van-tag :type="hasPinEnabled ? 'success' : 'default'">
            {{ hasPinEnabled ? t('secondFactor.statusEnabled') : t('secondFactor.statusNotSet') }}
          </van-tag>
        </template>
      </van-cell>
    </van-cell-group>

    <!-- Setup / Change PIN -->
    <van-cell-group inset :title="hasPinEnabled ? t('secondFactor.changePin') : t('secondFactor.setupPin')" class="section">
      <template v-if="hasPinEnabled">
        <van-field
          v-model="form.oldPin"
          type="password"
          :label="t('secondFactor.currentPinLabel')"
          :placeholder="t('secondFactor.currentPinPlaceholder')"
          maxlength="6"
          inputmode="numeric"
        />
      </template>
      <van-field
        v-model="form.newPin"
        type="password"
        :label="t('secondFactor.newPinLabel')"
        :placeholder="t('secondFactor.newPinPlaceholder')"
        maxlength="6"
        inputmode="numeric"
      />
      <van-field
        v-model="form.confirmPin"
        type="password"
        :label="t('secondFactor.confirmPinLabel')"
        :placeholder="t('secondFactor.confirmPinPlaceholder')"
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
        {{ hasPinEnabled ? t('secondFactor.changePin') : t('secondFactor.enablePin') }}
      </van-button>
    </div>

    <!-- Disable PIN -->
    <van-cell-group v-if="hasPinEnabled" inset :title="t('secondFactor.dangerZone')" class="section">
      <van-cell
        :title="t('secondFactor.disableTitle')"
        :label="t('secondFactor.disableLabel')"
        is-link
        class="danger-cell"
        @click="onDisablePin"
      />
    </van-cell-group>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { showToast, showConfirmDialog } from 'vant'
import http from '@/api/index'
import PageHeader from '@/components/common/PageHeader.vue'
import { useAuthStore } from '@/stores/auth'

const { t } = useI18n()
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
    showToast({ type: 'fail', message: t('toast.pinMismatch') })
    return
  }
  saving.value = true
  try {
    if (hasPinEnabled.value) {
      await http.post('/auth/pin/change', {
        old_pin: form.value.oldPin,
        new_pin: form.value.newPin,
      })
      showToast({ type: 'success', message: t('toast.pinChanged') })
    } else {
      await http.post('/auth/pin/setup', { pin: form.value.newPin })
      showToast({ type: 'success', message: t('toast.pinEnabled') })
      await authStore.fetchMe()
    }
    form.value = { oldPin: '', newPin: '', confirmPin: '' }
  } catch (e: unknown) {
    const err = e as { response?: { data?: { code?: string; message?: string } } }
    const code = err.response?.data?.code
    if (code === 'AUTH_INVALID_CREDENTIALS' || code === 'AUTH_PASSWORD_INCORRECT') {
      showToast({ type: 'fail', message: t('toast.pinCurrentIncorrect') })
    } else {
      showToast({ type: 'fail', message: t('toast.operationFailed2') })
    }
  } finally {
    saving.value = false
  }
}

async function onDisablePin() {
  try {
    await showConfirmDialog({ message: t('toast.pinDisableConfirm') })
  } catch {
    return
  }
  saving.value = true
  try {
    await http.post('/auth/pin/disable')
    showToast({ type: 'success', message: t('toast.pinDisabled') })
    await authStore.fetchMe()
  } catch {
    showToast({ type: 'fail', message: t('toast.operationFailed2') })
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
