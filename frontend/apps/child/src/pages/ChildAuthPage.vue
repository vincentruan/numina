<template>
  <div class="auth-page" role="main" :aria-label="t('auth.childLogin')">
    <!-- Cosmic star background canvas -->
    <canvas ref="canvasRef" class="cosmic-canvas" aria-hidden="true"></canvas>

    <div class="auth-content">
      <!-- Step 1: username + password -->
      <div v-if="step === 1" class="step-container">
        <div class="auth-header">
          <h1 class="app-title">Numina</h1>
          <p class="app-subtitle">{{ t('auth.childLogin') }}</p>
        </div>

        <van-form class="login-form" @submit="onStep1Submit">
          <van-cell-group inset>
            <van-field
              v-model="form.username"
              name="username"
              :label="t('auth.username')"
              :placeholder="t('auth.usernamePlaceholder')"
              autocomplete="username"
              :rules="[{ required: true, message: t('auth.usernameRequired') }]"
            />
            <van-field
              v-model="form.password"
              :type="showPassword ? 'text' : 'password'"
              name="password"
              :label="t('auth.password')"
              :placeholder="t('auth.passwordPlaceholder')"
              autocomplete="current-password"
              :rules="[{ required: true, message: t('auth.passwordRequired') }]"
              @keyup.enter="onStep1Submit"
            >
              <template #right-icon>
                <van-icon
                  :name="showPassword ? 'eye-o' : 'closed-eye'"
                  style="cursor: pointer"
                  @click="showPassword = !showPassword"
                />
              </template>
            </van-field>
          </van-cell-group>

          <p v-if="step1Error" class="step1-error">{{ step1Error }}</p>

          <div class="form-actions">
            <van-button round block type="primary" native-type="submit" :loading="loading" class="btn-next">
              {{ t('auth.nextStep') }}
            </van-button>
          </div>
        </van-form>
      </div>

      <!-- Step 2: emoji PIN / WebAuthn -->
      <div v-else class="step-container pin-step">
        <!-- Trusted device card -->
        <TrustedDeviceCard
          v-if="trustedUser"
          :display-name="trustedUser.displayName"
          :avatar-color="trustedUser.avatarColor"
          :loading="false"
          class="trusted-card"
          @confirm="() => {}"
          @switch-account="onSwitchAccount"
        />

        <template v-else>
          <div
            v-if="childInfo.avatarColor"
            class="child-avatar"
            :style="{ backgroundColor: childInfo.avatarColor }"
          >
            {{ (childInfo.displayName ?? '?').charAt(0) }}
          </div>
          <p class="child-name">{{ childInfo.displayName }}</p>
        </template>

        <!-- WebAuthn mode -->
        <div v-if="authMode === 'webauthn'" class="webauthn-mode">
          <p class="pin-hint">{{ t('auth.useFingerprint') }}</p>
          <van-button
            round
            size="large"
            :loading="loading"
            class="btn-unlock"
            @click="attemptWebAuthn"
          >
            {{ loading ? t('auth.verifying') : t('auth.unlock') }}
          </van-button>
          <button class="switch-btn" @click="switchToPin">
            {{ t('auth.useEmojiPin') }}
          </button>
        </div>

        <!-- Emoji PIN mode -->
        <div v-else class="pin-mode">
          <p class="pin-hint">{{ t('auth.enterPin') }}</p>

          <div class="pin-display" :class="{ shake: shaking }">
            <span
              v-for="i in 4"
              :key="i"
              class="pin-slot"
              :class="{ filled: pin.length >= i }"
            ></span>
          </div>

          <p v-if="childAuthStore.isLocked" class="pin-error">
            {{ childAuthStore.lockMessage ? t(`errors.${childAuthStore.lockMessage}`) : '' }}
          </p>
          <p v-else-if="childAuthStore.loginError" class="pin-error">
            {{ childAuthStore.loginError ? t(`errors.${childAuthStore.loginError}`) : '' }}
          </p>

          <div class="emoji-grid">
            <button
              v-for="emoji in EMOJIS"
              :key="emoji"
              class="emoji-btn"
              :disabled="childAuthStore.isLocked || pin.length >= 4"
              @click="addEmoji(emoji)"
            >
              {{ emoji }}
            </button>
          </div>

          <div class="pin-actions">
            <button class="pin-action-btn" @click="deleteEmoji">{{ t('auth.deleteEmoji') }}</button>
            <button class="pin-action-btn" @click="clearPin">{{ t('auth.clearPin') }}</button>
          </div>

          <button v-if="webAuthnAvailable" class="switch-btn" @click="switchToWebAuthn">
            {{ t('auth.useFaceId') }}
          </button>
        </div>

        <button class="back-btn" @click="backToStep1">
          {{ t('auth.backToLogin') }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { showToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { useChildAuthStore, TrustedDeviceCard, getDeviceFingerprint } from '@numina/auth'
import { checkWebAuthnSupport, authenticatePasskey } from '@/utils/webauthn'
import { getAuthenticationOptions, authenticateWithPasskey } from '@/api/webauthn'
import { checkDevice } from '@/api/device'
import axios from 'axios'

const { t } = useI18n()

const EMOJIS = ['🐱', '🐶', '🐸', '🦊', '🐼', '🐨', '🦁', '🐯', '🌟', '🌈', '🍎', '🎈']

const router = useRouter()
const childAuthStore = useChildAuthStore()

const step = ref<1 | 2>(1)
const loading = ref(false)
const step1Error = ref('')
const childInfo = ref({ displayName: '', avatarColor: '', childId: '' })
const tempToken = ref('')
const authMode = ref<'webauthn' | 'pin'>('pin')
const pin = ref<string[]>([])
const shaking = ref(false)
const webAuthnAvailable = ref(false)
const submitting = ref(false)
const showPassword = ref(false)
const form = ref({ username: '', password: '' })

interface TrustedUser {
  displayName: string
  avatarColor: string
  secondFactorType: 'emoji_pin' | 'webauthn'
}
const trustedUser = ref<TrustedUser | null>(null)

// ── Star canvas ──────────────────────────────────────────────────────────────
const canvasRef = ref<HTMLCanvasElement | null>(null)
let rafId: number | null = null

function initStars() {
  const canvas = canvasRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  canvas.width = window.innerWidth
  canvas.height = window.innerHeight

  const stars = Array.from({ length: 120 }, () => ({
    x: Math.random() * canvas.width,
    y: Math.random() * canvas.height,
    r: Math.random() * 1.5 + 0.3,
    alpha: Math.random() * 0.6 + 0.2,
    speed: Math.random() * 0.15 + 0.05,
  }))

  function draw() {
    if (!ctx || !canvas) return
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    for (const s of stars) {
      ctx.beginPath()
      ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2)
      ctx.fillStyle = `rgba(255,255,255,${s.alpha})`
      ctx.fill()
      s.y += s.speed
      if (s.y > canvas.height) {
        s.y = 0
        s.x = Math.random() * canvas.width
      }
    }
    rafId = requestAnimationFrame(draw)
  }
  draw()
}

onMounted(async () => {
  initStars()

  const support = checkWebAuthnSupport()
  if (support.supported) webAuthnAvailable.value = true

  try {
    const fingerprint = await getDeviceFingerprint()
    const result = await checkDevice(fingerprint)
    if (result.trusted && result.temp_token && result.display_name && result.avatar_color && result.second_factor_type) {
      tempToken.value = result.temp_token
      childInfo.value = {
        displayName: result.display_name,
        avatarColor: result.avatar_color,
        childId: result.user_id != null ? String(result.user_id) : '',
      }
      trustedUser.value = {
        displayName: result.display_name,
        avatarColor: result.avatar_color,
        secondFactorType: result.second_factor_type,
      }
      if (result.second_factor_type === 'webauthn') {
        authMode.value = 'webauthn'
      }
      step.value = 2
    }
  } catch {
    // Device check failure is non-fatal — fall through to normal step 1
  }
})

onUnmounted(() => {
  if (rafId !== null) cancelAnimationFrame(rafId)
})

function onSwitchAccount() {
  trustedUser.value = null
  tempToken.value = ''
  step.value = 1
  pin.value = []
  childAuthStore.clearLoginError()
}

async function onStep1Submit() {
  if (!form.value.username.trim()) return
  step1Error.value = ''
  loading.value = true
  try {
    const result = await childAuthStore.childLoginStep1(
      form.value.username.trim(),
      form.value.password,
    )
    childInfo.value = {
      displayName: result.display_name ?? form.value.username,
      avatarColor: result.avatar_color ?? '#FF6B6B',
      childId: result.user_id != null ? String(result.user_id) : '',
    }
    tempToken.value = result.temp_token ?? ''
    step.value = 2
  } catch {
    step1Error.value = t('errors.AUTH_INVALID_CREDENTIALS')
  } finally {
    loading.value = false
  }
}

async function attemptWebAuthn() {
  loading.value = true
  try {
    const optionsResponse = await getAuthenticationOptions(childInfo.value.childId)
    const { options, challenge } = optionsResponse
    const credential = await authenticatePasskey(options)
    await authenticateWithPasskey(childInfo.value.childId, credential, challenge)
    showToast(t('toast.loginSuccess'))
    router.push('/')
  } catch (err: unknown) {
    if (err instanceof Error && err.name === 'NotAllowedError') {
      // user cancelled — no error shown
    } else if (axios.isAxiosError(err) && err.response?.status === 400) {
      showToast(t('toast.noPasskey'))
      authMode.value = 'pin'
    } else {
      showToast(t('toast.verifyFailed'))
    }
  } finally {
    loading.value = false
  }
}

function switchToPin() { authMode.value = 'pin' }
function switchToWebAuthn() { authMode.value = 'webauthn' }

function addEmoji(emoji: string) {
  if (pin.value.length < 4) pin.value.push(emoji)
}

function deleteEmoji() { pin.value.pop() }

function clearPin() {
  pin.value = []
  childAuthStore.clearLoginError()
}

function backToStep1() {
  step.value = 1
  pin.value = []
  tempToken.value = ''
  step1Error.value = ''
  childAuthStore.clearLoginError()
}

watch(
  () => pin.value.length,
  async (len) => {
    if (len === 4 && !submitting.value) {
      submitting.value = true
      try {
        await childAuthStore.childLoginStep2(tempToken.value, [...pin.value])
        showToast(t('toast.loginSuccess'))
        router.push('/')
      } catch {
        shaking.value = true
        pin.value = []
        setTimeout(() => { shaking.value = false }, 600)
      } finally {
        submitting.value = false
      }
    }
  },
)
</script>

<style scoped>
/* ── Page shell ── */
.auth-page {
  min-height: 100vh;
  background: linear-gradient(160deg, #010120 0%, #000010 100%);
  display: flex;
  flex-direction: column;
  align-items: center;
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

.auth-content {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
  padding-top: min(15vh, 60px);
}

/* ── Step containers ── */
.step-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
}

/* ── Step 1 header ── */
.auth-header {
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

/* ── Login form ── */
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

.btn-next {
  --van-button-primary-background: #bdbbff;
  --van-button-primary-border-color: #bdbbff;
  color: #010120;
}

.step1-error {
  color: #ffcdd2;
  font-size: 14px;
  text-align: center;
  margin: 8px 16px 0;
}

/* ── Step 2 ── */
.pin-step {
  padding: 0 16px;
  max-width: 360px;
}

.trusted-card {
  margin-bottom: 24px;
}

.child-avatar {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 36px;
  font-weight: 500;
  color: #fff;
  margin-bottom: 12px;
}

.child-name {
  font-size: 20px;
  font-weight: 600;
  margin: 0 0 24px;
  color: #fff;
}

.pin-hint {
  color: rgba(255, 255, 255, 0.9);
  font-size: 16px;
  margin: 0 0 24px;
  text-align: center;
}

/* ── PIN dots ── */
.pin-display {
  display: flex;
  gap: 16px;
  margin-bottom: 20px;
}

.pin-slot {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  border: 2px solid rgba(255, 255, 255, 0.5);
  background: transparent;
  transition: background 0.15s, border-color 0.15s;
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

.shake { animation: shake 0.5s ease; }

.pin-error {
  color: #ffcdd2;
  font-size: 14px;
  margin: 0 0 16px;
  text-align: center;
}

/* ── Emoji grid ── */
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

.emoji-btn:active { transform: scale(0.92); background: rgba(255, 255, 255, 0.2); }
.emoji-btn:disabled { opacity: 0.35; cursor: not-allowed; }
.emoji-btn:focus-visible { outline: 3px solid #bdbbff; outline-offset: 2px; }

/* ── PIN action buttons ── */
.pin-actions {
  display: flex;
  gap: 12px;
  margin-bottom: 8px;
}

.pin-action-btn {
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

.pin-action-btn:active { background: rgba(255, 255, 255, 0.18); }

/* ── WebAuthn mode ── */
.webauthn-mode {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  width: 100%;
}

.btn-unlock {
  --van-button-primary-background: #bdbbff;
  --van-button-primary-border-color: #bdbbff;
  --van-button-primary-color: #010120;
  min-width: 160px;
}

/* ── Utility buttons ── */
.switch-btn {
  margin-top: 8px;
  background: transparent;
  border: none;
  font-size: 14px;
  color: rgba(255, 255, 255, 0.55);
  cursor: pointer;
  text-decoration: underline;
  min-height: 44px;
  padding: 0 8px;
  display: flex;
  align-items: center;
}

.back-btn {
  margin-top: 20px;
  background: transparent;
  border: none;
  font-size: 14px;
  color: rgba(255, 255, 255, 0.4);
  cursor: pointer;
  min-height: 44px;
  padding: 0 8px;
  display: flex;
  align-items: center;
}
</style>
