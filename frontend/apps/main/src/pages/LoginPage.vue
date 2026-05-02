<template>
  <div class="login-page" role="main" aria-label="登录">
    <!-- Cosmic star background canvas -->
    <canvas
      ref="canvasRef"
      class="cosmic-canvas"
      aria-hidden="true"
    ></canvas>

    <!-- Login content (above canvas) -->
    <div class="login-content">
      <div class="login-header">
        <h1 class="app-title">Numina</h1>
        <p class="app-subtitle">家庭资产可视化管理</p>
      </div>

      <!-- Step 1: username + password -->
      <van-form v-if="step === 1" class="login-form" @submit="onStep1Submit">
        <van-cell-group inset>
          <van-field
            v-model="form.username"
            name="username"
            label="用户名"
            placeholder="请输入用户名"
            :rules="[{ required: true, message: '请输入用户名' }]"
          />
          <div class="password-field-wrapper">
            <van-field
              v-model="form.password"
              :type="showPassword ? 'text' : 'password'"
              name="password"
              label="密码"
              placeholder="请输入密码"
              :rules="[{ required: true, message: '请输入密码' }]"
            >
              <template #right-icon>
                <van-icon :name="showPassword ? 'eye-o' : 'closed-eye'" @click="showPassword = !showPassword" />
              </template>
            </van-field>
          </div>
        </van-cell-group>

        <!-- ALTCHA captcha widget -->
        <AltchaWidget ref="altchaRef" v-model="form.altcha" endpoint="login" />

        <div class="form-actions">
          <van-button round block type="primary" native-type="submit" :loading="loading">
            下一步
          </van-button>
        </div>
      </van-form>

      <!-- Step 2: numeric PIN -->
      <div v-else class="pin-step">
        <p class="pin-hint">请输入数字 PIN 码完成验证</p>

        <div class="pin-display" :class="{ shake: shaking }">
          <span
            v-for="i in 6"
            :key="i"
            class="pin-slot"
            :class="{ filled: pinInput.length >= i }"
          ></span>
        </div>

        <p v-if="pinError" class="pin-error">{{ pinError }}</p>

        <div class="numpad">
          <button
            v-for="n in [1,2,3,4,5,6,7,8,9,'',0,'⌫']"
            :key="n"
            class="numpad-btn"
            :class="{ 'numpad-empty': n === '' }"
            :disabled="n === '' || loading"
            @click="onNumpadPress(n)"
          >
            {{ n }}
          </button>
        </div>

        <van-button
          round
          block
          type="primary"
          :loading="loading"
          :disabled="pinInput.length < 4"
          class="pin-confirm-btn"
          @click="submitPin"
        >确认</van-button>

        <van-button plain size="small" class="back-btn" @click="backToStep1">
          返回重新登录
        </van-button>
      </div>

      <div class="login-links">
        <router-link to="/register">创建家庭</router-link>
        <span class="divider">|</span>
        <router-link to="/join-family">加入家庭</router-link>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { showToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import AltchaWidget from '@/components/common/AltchaWidget.vue'
import { useStarField } from '@/composables/useStarField'

const { t } = useI18n()

const router = useRouter()
const authStore = useAuthStore()
const loading = ref(false)
const altchaRef = ref()
const showPassword = ref(false)

const canvasRef = ref<HTMLCanvasElement | null>(null)
useStarField(canvasRef)

const step = ref<1 | 2>(1)
const tempToken = ref('')
const secondFactorType = ref('')
const pinInput = ref('')
const shaking = ref(false)
const pinError = ref('')

const form = ref({
  username: '',
  password: '',
  altcha: undefined as string | undefined,
})

async function onStep1Submit() {
  loading.value = true
  try {
    const result = await authStore.loginStep1({
      username: form.value.username,
      password: form.value.password,
      altcha: form.value.altcha,
    })

    if (result.second_factor_required && result.temp_token) {
      tempToken.value = result.temp_token
      secondFactorType.value = result.second_factor_type ?? 'numeric_pin'
      step.value = 2
    } else {
      // No second factor — login complete; populate user store before navigating
      await authStore.fetchMe()
      showToast(t('toast.loginSuccess'))
      router.push('/')
    }
  } catch (error: unknown) {
    const axiosError = error as { response?: { status?: number; data?: { code?: string; message?: string; detail?: string } } }
    const code = axiosError.response?.data?.code
    const status = axiosError.response?.status

    if (code?.startsWith('CAPTCHA_') || status === 503) {
      altchaRef.value?.reset()
    }

    const i18nKey = code ? `errors.${code}` : ''
    if (i18nKey && t(i18nKey) !== i18nKey) {
      showToast({ type: 'fail', message: t(i18nKey) })
    } else {
      const fallback = axiosError.response?.data?.message || axiosError.response?.data?.detail || t('toast.loginFailedGeneric')
      showToast({ type: 'fail', message: fallback })
    }
  } finally {
    loading.value = false
  }
}

function onNumpadPress(key: number | string) {
  if (key === '⌫') {
    pinInput.value = pinInput.value.slice(0, -1)
    pinError.value = ''
    return
  }
  if (typeof key === 'number' && pinInput.value.length < 6) {
    pinInput.value += String(key)
  }
}

async function submitPin() {
  loading.value = true
  pinError.value = ''
  try {
    await authStore.loginStep2({
      temp_token: tempToken.value,
      factor_type: secondFactorType.value,
      payload: { pin: pinInput.value },
    })
    showToast(t('toast.loginSuccess'))
    router.push('/')
  } catch (error: unknown) {
    shaking.value = true
    pinInput.value = ''
    setTimeout(() => { shaking.value = false }, 600)

    const axiosError = error as { response?: { data?: { code?: string; message?: string } } }
    const code = axiosError.response?.data?.code
    const i18nKey = code ? `errors.${code}` : ''
    if (i18nKey && t(i18nKey) !== i18nKey) {
      pinError.value = t(i18nKey)
    } else {
      pinError.value = axiosError.response?.data?.message || t('toast.loginFailedGeneric')
    }
  } finally {
    loading.value = false
  }
}

function backToStep1() {
  step.value = 1
  pinInput.value = ''
  pinError.value = ''
  tempToken.value = ''
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  background: linear-gradient(160deg, #010120 0%, #000010 100%);
  display: flex;
  flex-direction: column;
  align-items: center;
  padding-top: min(15vh, 60px);
  position: relative;
  overflow: hidden;
}

.cosmic-canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  z-index: 0;
  pointer-events: none;
}

.login-content {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
}

.login-header {
  text-align: center;
  margin-bottom: 40px;
}

.app-title {
  font-size: 36px;
  font-weight: 500;
  color: #fff;
  margin: 0;
  letter-spacing: -0.02em;
}

.app-subtitle {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.8);
  margin-top: 8px;
}

.login-form {
  width: 100%;
  max-width: 400px;
}

.form-actions {
  padding: 24px 16px 0;
}

.form-actions :deep(.van-button--primary) {
  --van-button-primary-background: var(--color-action-primary);
  --van-button-primary-border-color: var(--color-action-primary);
}

.login-links {
  margin-top: 20px;
  text-align: center;
}

.login-links a {
  color: rgba(255, 255, 255, 0.9);
  text-decoration: none;
  font-size: 14px;
}

.divider {
  color: rgba(255, 255, 255, 0.5);
  margin: 0 12px;
}

.password-field-wrapper :deep(.van-field__right-icon) {
  cursor: pointer;
  color: var(--van-field-right-icon-color);
}

/* PIN step */
.pin-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
  max-width: 360px;
  padding: 0 16px;
}

.pin-hint {
  color: rgba(255, 255, 255, 0.9);
  font-size: 16px;
  margin: 0 0 24px;
}

.pin-display {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
}

.pin-slot {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  border: 2px solid rgba(255, 255, 255, 0.7);
  background: transparent;
  transition: background 0.15s;
}

.pin-slot.filled {
  background: #fff;
  border-color: #fff;
}

@keyframes shake {
  0%, 100% { transform: translateX(0); }
  20% { transform: translateX(-8px); }
  40% { transform: translateX(8px); }
  60% { transform: translateX(-6px); }
  80% { transform: translateX(6px); }
}

.shake {
  animation: shake 0.5s ease;
}

.pin-error {
  color: #ffcdd2;
  font-size: 14px;
  margin: 0 0 16px;
}

.numpad {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  width: 100%;
  max-width: 280px;
  margin-bottom: 20px;
}

.numpad-btn {
  height: 60px;
  border: none;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.12);
  color: #fff;
  font-size: 22px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s, transform 0.1s;
}

.numpad-btn:active {
  background: rgba(255, 255, 255, 0.35);
  transform: scale(0.94);
}

.numpad-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.numpad-empty {
  background: transparent !important;
  cursor: default !important;
}

.back-btn {
  color: rgba(255, 255, 255, 0.8);
  border-color: rgba(255, 255, 255, 0.4);
}

.pin-confirm-btn {
  max-width: 280px;
  margin-bottom: 16px;
}
</style>
