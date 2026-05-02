<template>
  <div class="auth-page">
    <!-- Step 1: username only -->
    <div v-if="step === 1" class="step-container">
      <div class="auth-hero">
        <div class="app-logo">🌟</div>
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
            :rules="[{ required: true, message: t('auth.usernameRequired') }]"
          />
          <van-field
            v-model="form.password"
            :type="showPassword ? 'text' : 'password'"
            name="password"
            :label="t('auth.password')"
            :placeholder="t('auth.passwordPlaceholder')"
            :rules="[{ required: true, message: t('auth.passwordRequired') }]"
          >
            <template #right-icon>
              <van-icon
                :name="showPassword ? 'eye-o' : 'closed-eye'"
                style="cursor:pointer"
                @click="showPassword = !showPassword"
              />
            </template>
          </van-field>
        </van-cell-group>

        <p v-if="step1Error" class="step1-error">{{ step1Error }}</p>

        <div class="form-actions">
          <van-button
            round block type="primary" native-type="submit" :loading="loading"
            class="btn-next"
          >
            {{ t('auth.nextStep') }}
          </van-button>
        </div>
      </van-form>
    </div>

    <!-- Step 2: emoji PIN -->
    <div v-else class="step-container">
      <!-- Trusted device card — shown when device check identified the user -->
      <TrustedDeviceCard
        v-if="trustedUser"
        :display-name="trustedUser.displayName"
        :avatar-color="trustedUser.avatarColor"
        :loading="false"
        @confirm="() => {}"
        @switch-account="onSwitchAccount"
      />

      <template v-else>
        <div v-if="childInfo.avatarColor" class="child-avatar" :style="{ backgroundColor: childInfo.avatarColor }">
          {{ (childInfo.displayName ?? '?').charAt(0) }}
        </div>
        <p class="child-name">{{ childInfo.displayName }}</p>
      </template>

      <!-- WebAuthn mode -->
      <div v-if="authMode === 'webauthn'" class="webauthn-mode">
        <p class="instruction">{{ t('auth.useFingerprint') }}</p>
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

      <!-- PIN mode -->
      <div v-else class="pin-mode">
        <div class="pin-display" :class="{ shake: shaking }">
          <span
            v-for="i in 4"
            :key="i"
            class="pin-slot"
            :class="{ filled: pin.length >= i }"
          ></span>
        </div>

        <p v-if="childAuthStore.isLocked" class="lock-message">
          {{ childAuthStore.lockMessage ? t(`errors.${childAuthStore.lockMessage}`) : '' }}
        </p>
        <p v-else-if="childAuthStore.loginError" class="error-message">
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

        <button
          v-if="webAuthnAvailable"
          class="switch-btn"
          @click="switchToWebAuthn"
        >
          {{ t('auth.useFaceId') }}
        </button>
      </div>

      <button class="back-btn" @click="backToStep1">
        {{ t('auth.backToLogin') }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
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
// temp_token from step1 — required for step2 PIN verification
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

onMounted(async () => {
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
/* ── Canvas ── */
.auth-page {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  background: var(--color-canvas);
}

.step-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
  padding: 48px 16px 24px;
}

/* ── Step 1 hero — peach feature card ── */
.auth-hero {
  width: 100%;
  background: var(--color-brand-peach);
  border-radius: var(--radius-xl);
  padding: 32px 20px;
  text-align: center;
  margin-bottom: 32px;
}
.app-logo { font-size: 48px; margin-bottom: 8px; }
.app-title {
  font-family: Inter, sans-serif;
  font-size: 28px;
  font-weight: 600;
  color: var(--color-ink);
  margin: 0;
  letter-spacing: -0.5px;
}
.app-subtitle {
  font-family: Inter, sans-serif;
  font-size: 14px;
  color: var(--color-ink);
  opacity: 0.7;
  margin-top: 4px;
}

.login-form {
  width: 100%;
  max-width: 400px;
}
.form-actions { padding: 24px 16px 0; }

/* Primary next button */
.btn-next {
  background: var(--color-primary);
  border: none;
  border-radius: var(--radius-md);
  height: 44px;
  color: var(--color-on-primary);
}

.step1-error {
  font-family: Inter, sans-serif;
  color: var(--color-brand-coral);
  font-size: 14px;
  text-align: center;
  margin: 8px 16px 0;
}

/* ── Step 2 ── */
.child-avatar {
  width: 80px;
  height: 80px;
  border-radius: var(--radius-pill);
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: Inter, sans-serif;
  font-size: 36px;
  font-weight: 500;
  color: var(--color-on-dark);
  margin-bottom: 12px;
}
.child-name {
  font-family: Inter, sans-serif;
  font-size: 20px;
  font-weight: 600;
  margin: 0 0 24px;
  color: var(--color-ink);
}

.webauthn-mode {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}
.instruction {
  font-family: Inter, sans-serif;
  font-size: 16px;
  color: var(--color-muted);
  margin: 0;
}

/* Unlock button */
.btn-unlock {
  background: var(--color-primary);
  color: var(--color-on-primary);
  border: none;
  border-radius: var(--radius-md);
  height: 44px;
  min-width: 160px;
}

.pin-mode {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.pin-display {
  display: flex;
  gap: 16px;
  margin-bottom: 20px;
}
.pin-slot {
  width: 24px;
  height: 24px;
  border-radius: var(--radius-pill);
  border: 2px solid var(--color-muted-soft);
  background: transparent;
  transition: background 0.15s, border-color 0.15s;
}
.pin-slot.filled {
  background: var(--color-ink);
  border-color: var(--color-ink);
}

@keyframes shake {
  0%, 100% { transform: translateX(0); }
  20% { transform: translateX(-8px); }
  40% { transform: translateX(8px); }
  60% { transform: translateX(-6px); }
  80% { transform: translateX(6px); }
}
.shake { animation: shake 0.5s ease; }

.lock-message,
.error-message {
  font-family: Inter, sans-serif;
  color: var(--color-brand-coral);
  font-size: 14px;
  margin: 0 0 16px;
}

/* ── Emoji grid ── */
.emoji-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 20px;
  width: 100%;
  max-width: 320px;
}
.emoji-btn {
  font-size: 28px;
  min-height: 56px;
  min-width: 56px;
  border: 1px solid var(--color-hairline);
  border-radius: var(--radius-md);
  background: var(--color-surface-soft);
  cursor: pointer;
  transition: transform 0.1s, opacity 0.1s;
}
.emoji-btn:active { transform: scale(0.92); }
.emoji-btn:disabled { opacity: 0.35; cursor: not-allowed; }
.emoji-btn:focus-visible {
  outline: 3px solid var(--color-brand-ochre);
  outline-offset: 2px;
}

/* ── PIN action buttons ── */
.pin-actions { display: flex; gap: 16px; margin-bottom: 4px; }
.pin-action-btn {
  min-height: 44px;
  min-width: 88px;
  border: 1px solid var(--color-hairline);
  border-radius: var(--radius-md);
  background: var(--color-surface-soft);
  font-family: Inter, sans-serif;
  font-size: 14px;
  font-weight: 500;
  color: var(--color-body);
  cursor: pointer;
  transition: background 0.15s;
}
.pin-action-btn:active { background: var(--color-surface-card); }

/* ── Utility buttons — 44px touch targets ── */
.switch-btn {
  margin-top: 16px;
  background: transparent;
  border: none;
  font-family: Inter, sans-serif;
  font-size: 14px;
  color: var(--color-muted);
  cursor: pointer;
  text-decoration: underline;
  min-height: 44px;
  padding: 0 8px;
  display: flex;
  align-items: center;
}
.back-btn {
  margin-top: 24px;
  background: transparent;
  border: none;
  font-family: Inter, sans-serif;
  font-size: 14px;
  color: var(--color-muted-soft);
  cursor: pointer;
  min-height: 44px;
  padding: 0 8px;
  display: flex;
  align-items: center;
}
</style>
