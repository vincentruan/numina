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
        <!-- Numina SVG logo — cursive script, family+finance motif (shown in step 1 only) -->
        <svg
          v-if="step === 1"
          class="numina-logo"
          viewBox="-10 -15 300 95"
          xmlns="http://www.w3.org/2000/svg"
          aria-label="Numina"
          role="img"
        >
          <defs>
            <linearGradient id="flourishGrad" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stop-color="#bdbbff" stop-opacity="0.7" />
              <stop offset="45%" stop-color="#e8e4ff" stop-opacity="1" />
              <stop offset="100%" stop-color="#ffd6a5" stop-opacity="0.8" />
            </linearGradient>
            <linearGradient id="textGrad" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stop-color="#ffffff" />
              <stop offset="100%" stop-color="rgba(255,255,255,0.85)" />
            </linearGradient>
            <filter id="logoGlow" x="-30%" y="-30%" width="160%" height="160%">
              <feGaussianBlur stdDeviation="2" result="b" />
              <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
            </filter>
            <filter id="logoSoftglow" x="-15%" y="-15%" width="130%" height="130%">
              <feGaussianBlur stdDeviation="1" result="b" />
              <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
            </filter>
          </defs>

          <!-- N: left stem + diagonal + right stem -->
          <path d="M 4,56 C 4,50 4,30 5,18 C 5.5,14 7,12 9,13 C 11,14 13,17 15,22 C 22,36 28,48 31,54 C 32,57 33,58 34,57 C 35,56 36,40 36,18 C 36,14 37,12 39,12"
            fill="none" stroke="url(#textGrad)" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" filter="url(#logoSoftglow)" />
          <path d="M 39,12 C 41,11 44,14 45,20" fill="none" stroke="url(#textGrad)" stroke-width="1.6" stroke-linecap="round" opacity="0.7" />

          <!-- u -->
          <path d="M 45,20 C 45,20 44,46 44,52 C 44,57 46,60 49,59 C 52,58 55,54 57,49 C 58,46 58,20 58,20"
            fill="none" stroke="url(#textGrad)" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" filter="url(#logoSoftglow)" />
          <path d="M 58,20 C 60,19 63,20 64,22" fill="none" stroke="url(#textGrad)" stroke-width="1.6" stroke-linecap="round" opacity="0.7" />

          <!-- m: left stem + two arches -->
          <path d="M 64,22 C 64,22 63,56 63,58" fill="none" stroke="url(#textGrad)" stroke-width="2.4" stroke-linecap="round" filter="url(#logoSoftglow)" />
          <path d="M 63,30 C 65,23 69,19 73,20 C 77,21 79,25 79,30 C 79,30 79,58 79,58" fill="none" stroke="url(#textGrad)" stroke-width="2.4" stroke-linecap="round" filter="url(#logoSoftglow)" />
          <path d="M 79,30 C 81,23 85,19 89,20 C 93,21 95,25 95,30 C 95,30 95,58 95,58" fill="none" stroke="url(#textGrad)" stroke-width="2.4" stroke-linecap="round" filter="url(#logoSoftglow)" />
          <path d="M 95,58 C 97,59 100,58 101,56 C 102,54 102,40 102,30" fill="none" stroke="url(#textGrad)" stroke-width="1.6" stroke-linecap="round" opacity="0.7" />

          <!-- i: stem -->
          <path d="M 102,30 C 102,30 102,56 102,58" fill="none" stroke="url(#textGrad)" stroke-width="2.4" stroke-linecap="round" filter="url(#logoSoftglow)" />
          <!-- i dot → house icon -->
          <g transform="translate(96.5, 14)" filter="url(#logoGlow)">
            <polyline points="5.5,8 0,4 5.5,0 11,4 5.5,8" fill="none" stroke="url(#flourishGrad)" stroke-width="1.5" stroke-linejoin="round" />
            <rect x="1.5" y="8" width="8" height="6" fill="none" stroke="url(#flourishGrad)" stroke-width="1.5" />
            <rect x="3.5" y="10.5" width="4" height="3.5" fill="none" stroke="url(#flourishGrad)" stroke-width="1.2" />
          </g>
          <path d="M 102,58 C 104,59 107,58 108,56 C 109,54 109,40 109,30" fill="none" stroke="url(#textGrad)" stroke-width="1.6" stroke-linecap="round" opacity="0.7" />

          <!-- n: stem + arch -->
          <path d="M 109,30 C 109,30 108,56 108,58" fill="none" stroke="url(#textGrad)" stroke-width="2.4" stroke-linecap="round" filter="url(#logoSoftglow)" />
          <path d="M 108,38 C 110,31 114,27 118,28 C 122,29 124,33 124,38 C 124,38 124,58 124,58" fill="none" stroke="url(#textGrad)" stroke-width="2.4" stroke-linecap="round" filter="url(#logoSoftglow)" />
          <path d="M 124,58 C 126,59 129,58 130,56 C 131,54 131,44 131,38" fill="none" stroke="url(#textGrad)" stroke-width="1.6" stroke-linecap="round" opacity="0.7" />

          <!-- a: bowl + right stem + exit -->
          <path d="M 148,32 C 146,26 142,23 138,24 C 134,25 131,29 131,36 C 131,44 134,56 140,58 C 144,59 148,56 148,52 C 148,48 148,32 148,32"
            fill="none" stroke="url(#textGrad)" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" filter="url(#logoSoftglow)" />
          <path d="M 148,32 C 148,32 148,58 149,60 C 150,62 153,63 156,61" fill="none" stroke="url(#textGrad)" stroke-width="2.4" stroke-linecap="round" filter="url(#logoSoftglow)" />

          <!-- Decorative flourish: sweeping arc from N top, over word, curling back -->
          <path d="M 39,12 C 55,0 90,-4 130,-1 C 170,2 205,-2 225,10 C 240,18 244,34 238,46 C 232,56 220,62 208,58 C 196,54 193,44 198,36 C 201,30 208,27 214,30"
            fill="none" stroke="url(#flourishGrad)" stroke-width="1.6" stroke-linecap="round" opacity="0.85" filter="url(#logoGlow)" />

          <!-- Trend line from a's exit -->
          <path d="M 156,61 C 170,64 190,58 205,50" fill="none" stroke="url(#flourishGrad)" stroke-width="1.3" stroke-linecap="round" opacity="0.65" />

          <!-- Growth arrow at flourish end -->
          <g transform="translate(208, 22)" filter="url(#logoGlow)">
            <polyline points="0,14 5,6 10,14" fill="none" stroke="url(#flourishGrad)" stroke-width="1.5" stroke-linejoin="round" opacity="0.95" />
            <line x1="5" y1="6" x2="5" y2="20" stroke="url(#flourishGrad)" stroke-width="1.5" opacity="0.95" />
          </g>

          <!-- Three dots on flourish arc — family members connected -->
          <circle cx="80" cy="-2" r="2" fill="url(#flourishGrad)" opacity="0.6" filter="url(#logoGlow)" />
          <circle cx="130" cy="-1" r="2" fill="url(#flourishGrad)" opacity="0.6" filter="url(#logoGlow)" />
          <circle cx="178" cy="2" r="2" fill="url(#flourishGrad)" opacity="0.6" filter="url(#logoGlow)" />
        </svg>

        <p v-if="step === 1" class="app-subtitle">家庭资产可视化管理</p>
      </div>

      <!-- Step 1: username + password -->
      <div v-if="step === 1" class="login-form">
        <van-cell-group inset>
          <van-field
            v-model="form.username"
            name="username"
            label="用户名"
            placeholder="请输入用户名"
            autocomplete="username"
          />
          <div class="password-field-wrapper">
            <van-field
              v-model="form.password"
              :type="showPassword ? 'text' : 'password'"
              name="password"
              label="密码"
              placeholder="请输入密码"
              autocomplete="current-password"
              @keyup.enter="onStep1Submit"
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
          <van-button round block type="primary" :loading="loading" @click="onStep1Submit">
            下一步
          </van-button>
        </div>
      </div>

      <!-- Step 2: PIN verification (numeric or emoji based on secondFactorType) -->
      <div v-else class="pin-step">
        <!-- Trusted device card — shown when fast-login path was taken -->
        <TrustedDeviceCard
          v-if="trustedUser"
          :display-name="trustedUser.displayName"
          :avatar-color="trustedUser.avatarColor"
          :loading="loading"
          class="trusted-card"
          @confirm="focusPinHint"
          @switch-account="switchAccount"
        />

        <!-- User identity card — shown when step1 returned display_name/avatar_color -->
        <div v-else-if="step2User" class="pin-user-card">
          <div
            class="pin-avatar"
            :style="{ background: step2User.avatarColor }"
          >{{ step2User.displayName.charAt(0).toUpperCase() }}</div>
          <div class="pin-user-info">
            <p class="pin-display-name">{{ step2User.displayName }}</p>
            <p class="pin-username-sub">{{ form.username }}</p>
          </div>
        </div>
        <p v-else class="pin-username">{{ form.username }}</p>
        <p class="pin-hint">{{ secondFactorType === 'emoji_pin' ? '请输入图形密码完成验证' : '请输入数字 PIN 码完成验证' }}</p>

        <!-- Numeric PIN mode -->
        <div v-if="secondFactorType !== 'emoji_pin'" class="pin-display" :class="{ shake: shaking }">
          <span
            v-for="i in 6"
            :key="i"
            class="pin-slot"
            :class="{ filled: pinInput.length >= i }"
          ></span>
        </div>

        <p v-if="pinError" class="pin-error">{{ pinError }}</p>

        <!-- Numeric keypad -->
        <div v-if="secondFactorType !== 'emoji_pin'" class="numpad">
          <button
            v-for="n in [1,2,3,4,5,6,7,8,9,'清空',0,'⌫']"
            :key="n"
            class="numpad-btn"
            :class="{
              'numpad-action': n === '清空' || n === '⌫',
              flash: flashKey === n,
            }"
            :disabled="loading"
            @click="onNumpadPress(n)"
          >
            {{ n }}
          </button>
        </div>

        <!-- Emoji PIN mode -->
        <div v-else class="emoji-pin-section">
          <div class="emoji-pin-display" :class="{ shake: shaking }">
            <span
              v-for="i in 4"
              :key="i"
              class="emoji-pin-slot"
              :class="{ filled: emojiPin.length >= i }"
            >
              {{ emojiPin[i - 1] || '' }}
            </span>
          </div>

          <div class="emoji-grid">
            <button
              v-for="emoji in EMOJIS"
              :key="emoji"
              class="emoji-btn"
              :disabled="loading || emojiPin.length >= 4"
              :class="{ flash: flashKey === emoji }"
              @click="addEmoji(emoji)"
            >
              {{ emoji }}
            </button>
          </div>

          <div class="emoji-actions">
            <button class="emoji-action-btn" :disabled="loading" @click="deleteEmoji">删除</button>
            <button class="emoji-action-btn" :disabled="loading" @click="clearEmojiPin">清除</button>
          </div>

          <!-- Loading indicator for emoji PIN verification -->
          <div v-if="loading && emojiPin.length === 4" class="emoji-loading">
            <van-loading size="24px" color="#bdbbff" />
            <span>验证中…</span>
          </div>
        </div>

        <van-button
          v-if="secondFactorType !== 'emoji_pin'"
          round
          block
          type="primary"
          :loading="loading"
          :disabled="pinInput.length < 4"
          class="pin-confirm-btn"
          @click="submitPin"
        >确认</van-button>

        <div class="form-actions back-actions">
          <van-button round block type="primary" class="back-btn-primary" :disabled="loading" @click="backToStep1">
            返回重新登录
          </van-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { showToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import AltchaWidget from '@/components/common/AltchaWidget.vue'
import { useStarField } from '@/composables/useStarField'
import { TrustedDeviceCard, getDeviceFingerprint } from '@numina/auth'
import { checkDevice } from '@/api/device'

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
const flashKey = ref<number | string | null>(null)

// Emoji PIN support
const EMOJIS = ['🐱', '🐶', '🐸', '🦊', '🐼', '🐨', '🦁', '🐯', '🌟', '🌈', '🍎', '🎈']
const emojiPin = ref<string[]>([])
const submitting = ref(false)

interface TrustedUser {
  displayName: string
  avatarColor: string
}
const trustedUser = ref<TrustedUser | null>(null)

// User info from step1 response — shown in step2 header
const step2User = ref<{ displayName: string; avatarColor: string } | null>(null)

const form = ref({
  username: '',
  password: '',
  altcha: undefined as string | undefined,
})

onMounted(async () => {
  try {
    const fingerprint = await getDeviceFingerprint()
    const { data } = await checkDevice(fingerprint)
    if (data.trusted && data.temp_token && data.display_name && data.avatar_color) {
      tempToken.value = data.temp_token
      secondFactorType.value = data.second_factor_type ?? 'numeric_pin'
      trustedUser.value = { displayName: data.display_name, avatarColor: data.avatar_color }
      step.value = 2
    }
  } catch {
    // Device check failure is non-fatal — fall through to normal step 1
  }
})

async function onStep1Submit() {
  if (!form.value.username.trim() || !form.value.password) return
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
      if (result.display_name && result.avatar_color) {
        step2User.value = { displayName: result.display_name, avatarColor: result.avatar_color }
      }
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
      showToast(t(i18nKey))
    } else {
      const fallback = axiosError.response?.data?.message || axiosError.response?.data?.detail || t('toast.loginFailedGeneric')
      showToast(fallback)
    }
  } finally {
    loading.value = false
  }
}

function onNumpadPress(key: number | string) {
  flashKey.value = key
  setTimeout(() => { flashKey.value = null }, 150)

  if (key === '⌫') {
    pinInput.value = pinInput.value.slice(0, -1)
    pinError.value = ''
    return
  }
  if (key === '清空') {
    pinInput.value = ''
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
  emojiPin.value = []
  pinError.value = ''
  tempToken.value = ''
  trustedUser.value = null
  step2User.value = null
}

function switchAccount() {
  backToStep1()
}

function focusPinHint() {
  // TrustedDeviceCard confirm — user is already on step 2, nothing extra needed
}

// Emoji PIN functions
function addEmoji(emoji: string) {
  flashKey.value = emoji
  setTimeout(() => { flashKey.value = null }, 150)
  if (emojiPin.value.length < 4) {
    emojiPin.value.push(emoji)
  }
}

function deleteEmoji() {
  emojiPin.value.pop()
}

function clearEmojiPin() {
  emojiPin.value = []
  pinError.value = ''
}

// Auto-submit emoji PIN when 4 emojis selected
watch(
  () => emojiPin.value.length,
  async (len) => {
    if (len === 4 && !submitting.value) {
      submitting.value = true
      loading.value = true
      pinError.value = ''
      try {
        await authStore.loginStep2({
          temp_token: tempToken.value,
          factor_type: 'emoji_pin',
          payload: { pin_sequence: emojiPin.value },
        })
        showToast(t('toast.loginSuccess'))
        router.push('/')
      } catch (error: unknown) {
        shaking.value = true
        emojiPin.value = []
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
        submitting.value = false
      }
    }
  },
)
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

.numina-logo {
  width: 220px;
  height: auto;
  display: block;
  margin: 0 auto;
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
  --van-button-primary-background: #bdbbff;
  --van-button-primary-border-color: #bdbbff;
  color: #010120;
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

.numpad-action {
  font-size: 14px !important;
  font-weight: 500 !important;
  background: rgba(189, 187, 255, 0.15) !important;
  color: #bdbbff !important;
}

@keyframes flash {
  0% { background: rgba(255, 255, 255, 0.12); }
  40% { background: rgba(189, 187, 255, 0.6); }
  100% { background: rgba(255, 255, 255, 0.12); }
}

.numpad-btn.flash {
  animation: flash 0.15s ease-out;
}

.numpad-action.flash {
  animation: flash 0.15s ease-out;
}

.pin-username {
  color: #fff;
  font-size: 18px;
  font-weight: 600;
  margin: 0 0 4px;
  letter-spacing: -0.01em;
}

.pin-confirm-btn {
  max-width: 280px;
  margin-bottom: 12px;
  --van-button-primary-background: #bdbbff;
  --van-button-primary-border-color: #bdbbff;
  --van-button-primary-color: #010120;
}

.back-actions {
  padding: 0;
  width: 100%;
  max-width: 280px;
}

.back-btn-primary {
  --van-button-primary-background: #bdbbff;
  --van-button-primary-border-color: #bdbbff;
  --van-button-primary-color: #010120;
}

.trusted-card {
  margin-bottom: 24px;
}

.pin-user-card {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.pin-avatar {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  font-weight: 700;
  color: #fff;
  box-shadow: 0 2px 12px rgba(1, 1, 32, 0.35);
}

.pin-user-info {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
}

.pin-display-name {
  color: #fff;
  font-size: 16px;
  font-weight: 600;
  margin: 0;
  letter-spacing: -0.01em;
}

.pin-username-sub {
  color: rgba(255, 255, 255, 0.55);
  font-size: 12px;
  margin: 0;
}

/* Emoji PIN styles */
.emoji-pin-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
}

.emoji-pin-display {
  display: flex;
  gap: 16px;
  margin-bottom: 20px;
}

.emoji-pin-slot {
  width: 48px;
  height: 48px;
  border-radius: 8px;
  border: 2px solid rgba(255, 255, 255, 0.5);
  background: transparent;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  transition: background 0.15s, border-color 0.15s;
}

.emoji-pin-slot.filled {
  background: rgba(255, 255, 255, 0.1);
  border-color: rgba(255, 255, 255, 0.8);
}

.emoji-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
  margin-bottom: 16px;
  width: 100%;
  max-width: 320px;
}

.emoji-btn {
  font-size: 28px;
  min-height: 56px;
  min-width: 56px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.08);
  cursor: pointer;
  transition: background 0.1s, transform 0.1s;
}

.emoji-btn:active {
  transform: scale(0.92);
  background: rgba(255, 255, 255, 0.2);
}

.emoji-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.emoji-btn.flash {
  animation: flash 0.15s ease-out;
}

.emoji-actions {
  display: flex;
  gap: 12px;
  margin-bottom: 8px;
}

.emoji-action-btn {
  min-height: 44px;
  min-width: 88px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.08);
  font-size: 14px;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.85);
  cursor: pointer;
  transition: background 0.15s;
}

.emoji-action-btn:active {
  background: rgba(255, 255, 255, 0.18);
}

.emoji-action-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.emoji-loading {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
  color: rgba(255, 255, 255, 0.9);
  font-size: 14px;
}
</style>
