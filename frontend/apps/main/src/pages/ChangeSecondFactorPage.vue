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

    <!-- PIN input area -->
    <div class="pin-section">
      <p class="pin-step-label">{{ stepLabel }}</p>

      <div class="pin-display" :class="{ shake: shaking }">
        <span
          v-for="i in 6"
          :key="i"
          class="pin-slot"
          :class="{ filled: currentInput.length >= i }"
        ></span>
      </div>

      <p v-if="errorMsg" class="pin-error">{{ errorMsg }}</p>

      <div class="numpad">
        <button
          v-for="n in [1,2,3,4,5,6,7,8,9,t('secondFactor.numpadClear'),0,t('secondFactor.numpadDelete')]"
          :key="n"
          class="numpad-btn"
          :class="{
            'numpad-action': n === t('secondFactor.numpadClear') || n === t('secondFactor.numpadDelete'),
            flash: flashKey === n,
          }"
          :disabled="saving"
          @click="onNumpadPress(n)"
        >
          {{ n }}
        </button>
      </div>

      <van-button
        round
        block
        type="primary"
        :loading="saving"
        :disabled="currentInput.length < 6"
        class="confirm-btn"
        @click="onConfirm"
      >
        {{ confirmBtnLabel }}
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

// step: 'old' | 'new' | 'confirm'
// 'old' only shown when hasPinEnabled
const step = ref<'old' | 'new' | 'confirm'>(hasPinEnabled.value ? 'old' : 'new')

const oldPin = ref('')
const newPin = ref('')
const confirmPin = ref('')
const saving = ref(false)
const shaking = ref(false)
const errorMsg = ref('')
const flashKey = ref<number | string | null>(null)

const currentInput = computed(() => {
  if (step.value === 'old') return oldPin.value
  if (step.value === 'new') return newPin.value
  return confirmPin.value
})

const stepLabel = computed(() => {
  if (step.value === 'old') return t('secondFactor.currentPinPlaceholder')
  if (step.value === 'new') return t('secondFactor.newPinPlaceholder')
  return t('secondFactor.confirmPinPlaceholder')
})

const confirmBtnLabel = computed(() => {
  if (step.value === 'confirm') return hasPinEnabled.value ? t('secondFactor.changePin') : t('secondFactor.enablePin')
  return t('common.next')
})

function onNumpadPress(key: number | string) {
  flashKey.value = key
  setTimeout(() => { flashKey.value = null }, 150)
  errorMsg.value = ''

  if (key === t('secondFactor.numpadDelete') || key === '⌫') {
    if (step.value === 'old') oldPin.value = oldPin.value.slice(0, -1)
    else if (step.value === 'new') newPin.value = newPin.value.slice(0, -1)
    else confirmPin.value = confirmPin.value.slice(0, -1)
    return
  }
  if (key === t('secondFactor.numpadClear')) {
    if (step.value === 'old') oldPin.value = ''
    else if (step.value === 'new') newPin.value = ''
    else confirmPin.value = ''
    return
  }
  if (typeof key === 'number' && currentInput.value.length < 6) {
    if (step.value === 'old') oldPin.value += String(key)
    else if (step.value === 'new') newPin.value += String(key)
    else confirmPin.value += String(key)
  }
}

function triggerShake() {
  shaking.value = true
  setTimeout(() => { shaking.value = false }, 500)
}

async function onConfirm() {
  if (currentInput.value.length < 6) return

  if (step.value === 'old') {
    step.value = 'new'
    return
  }

  if (step.value === 'new') {
    step.value = 'confirm'
    return
  }

  // step === 'confirm'
  if (newPin.value !== confirmPin.value) {
    errorMsg.value = t('toast.pinMismatch')
    triggerShake()
    confirmPin.value = ''
    return
  }

  saving.value = true
  try {
    const wasEnabled = hasPinEnabled.value
    if (wasEnabled) {
      await http.post('/auth/pin/change', {
        old_pin: oldPin.value,
        new_pin: newPin.value,
      })
      showToast({ type: 'success', message: t('toast.pinChanged') })
    } else {
      await http.post('/auth/pin/setup', { pin: newPin.value })
      showToast({ type: 'success', message: t('toast.pinEnabled') })
    }
    await authStore.fetchMe()
    // Reset
    oldPin.value = ''
    newPin.value = ''
    confirmPin.value = ''
    step.value = wasEnabled ? 'old' : 'new'
  } catch (e: unknown) {
    const err = e as { response?: { data?: { code?: string } } }
    const code = err.response?.data?.code
    if (code === 'AUTH_INVALID_CREDENTIALS' || code === 'AUTH_PASSWORD_INCORRECT') {
      errorMsg.value = t('toast.pinCurrentIncorrect')
      triggerShake()
      // Go back to old PIN step
      oldPin.value = ''
      newPin.value = ''
      confirmPin.value = ''
      step.value = 'old'
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
    step.value = 'new'
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

.pin-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 24px 16px 16px;
}

.pin-step-label {
  font-size: 15px;
  color: var(--van-text-color-2);
  margin: 0 0 20px;
}

.pin-display {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
}

.pin-slot {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  border: 2px solid var(--van-gray-5);
  background: transparent;
  transition: background 0.15s;
}

.pin-slot.filled {
  background: var(--van-primary-color);
  border-color: var(--van-primary-color);
}

.pin-display.shake {
  animation: shake 0.4s ease;
}

@keyframes shake {
  0%, 100% { transform: translateX(0); }
  20% { transform: translateX(-6px); }
  40% { transform: translateX(6px); }
  60% { transform: translateX(-4px); }
  80% { transform: translateX(4px); }
}

.pin-error {
  font-size: 13px;
  color: var(--van-danger-color);
  margin: 4px 0 8px;
}

.numpad {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  width: 100%;
  max-width: 320px;
  margin: 12px 0 20px;
}

.numpad-btn {
  height: 56px;
  border-radius: 8px;
  border: none;
  background: var(--van-white);
  font-size: 20px;
  font-weight: 500;
  color: var(--van-text-color);
  cursor: pointer;
  box-shadow: 0 1px 4px rgba(1, 1, 32, 0.08);
  transition: background 0.1s, transform 0.1s;
  -webkit-tap-highlight-color: transparent;
}

.numpad-btn:active {
  background: var(--van-gray-2);
  transform: scale(0.96);
}

.numpad-btn.numpad-action {
  font-size: 15px;
  color: var(--van-text-color-2);
}

.numpad-btn.flash {
  background: var(--van-primary-color);
  color: white;
}

.numpad-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.confirm-btn {
  width: 100%;
  max-width: 320px;
}

.danger-cell :deep(.van-cell__title) {
  color: var(--van-danger-color);
}
</style>
