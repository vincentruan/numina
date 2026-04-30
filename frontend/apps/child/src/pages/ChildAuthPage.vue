<template>
  <div class="auth-page">
    <!-- Step 1: username + password -->
    <div v-if="step === 1" class="step-container">
      <div class="auth-header">
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
          <div class="password-field-wrapper">
            <van-field
              v-model="form.password"
              :type="showPassword ? 'text' : 'password'"
              name="password"
              :label="t('auth.password')"
              :placeholder="t('auth.passwordPlaceholder')"
              :rules="[{ required: true, message: t('auth.passwordRequired') }]"
            >
              <template #right-icon>
                <van-icon :name="showPassword ? 'eye-o' : 'closed-eye'" @click="showPassword = !showPassword" />
              </template>
            </van-field>
          </div>
        </van-cell-group>

        <p v-if="step1Error" class="step1-error">{{ step1Error }}</p>

        <div class="form-actions">
          <van-button round block type="primary" native-type="submit" :loading="loading"
            style="background: var(--color-primary); border: none; border-radius: var(--radius-md); height: 44px;">
            {{ t('auth.nextStep') }}
          </van-button>
        </div>
      </van-form>
    </div>

    <!-- Step 2: emoji PIN -->
    <div v-else class="step-container">
      <div v-if="childInfo.avatarColor" class="child-avatar" :style="{ backgroundColor: childInfo.avatarColor }">
        {{ (childInfo.displayName ?? '?').charAt(0) }}
      </div>
      <p class="child-name">{{ childInfo.displayName }}</p>

      <!-- WebAuthn mode -->
      <div v-if="authMode === 'webauthn'" class="webauthn-mode">
        <p class="instruction">{{ t('auth.useFingerprint') }}</p>
        <van-button
          round
          size="large"
          :loading="loading"
          style="background: var(--color-primary); color: var(--color-on-primary); border: none; border-radius: var(--radius-md); height: 44px; min-width: 160px;"
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
          <button class="pin-action-btn" @click="deleteEmoji">删除</button>
          <button class="pin-action-btn" @click="clearPin">清除</button>
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
import { useChildAuthStore } from '@numina/auth'
import { checkWebAuthnSupport, authenticatePasskey } from '@/utils/webauthn'
import { getAuthenticationOptions, authenticateWithPasskey } from '@/api/webauthn'
import { setUser } from '@numina/auth'
import axios from 'axios'

const { t } = useI18n()

const EMOJIS = ['🐱', '🐶', '🐸', '🦊', '🐼', '🐨', '🦁', '🐯', '🌟', '🌈', '🍎', '🎈']

const router = useRouter()
const childAuthStore = useChildAuthStore()

const step = ref<1 | 2>(1)
const loading = ref(false)
const showPassword = ref(false)
const step1Error = ref('')
const tempToken = ref('')
const childInfo = ref({ displayName: '', avatarColor: '', childId: '' })

const authMode = ref<'webauthn' | 'pin'>('pin')
const pin = ref<string[]>([])
const shaking = ref(false)
const webAuthnAvailable = ref(false)
const submitting = ref(false)

const form = ref({ username: '', password: '' })

onMounted(async () => {
  const support = checkWebAuthnSupport()
  if (!support.supported) return
  webAuthnAvailable.value = true
})

async function onStep1Submit() {
  loading.value = true
  step1Error.value = ''
  try {
    const result = await childAuthStore.childLoginStep1(form.value.username, form.value.password)

    if (result.second_factor_required && result.temp_token) {
      tempToken.value = result.temp_token
      childInfo.value = {
        displayName: result.display_name ?? form.value.username,
        avatarColor: result.avatar_color ?? '#4F46E5',
        childId: result.user_id ? String(result.user_id) : '',
      }
      step.value = 2

      if (webAuthnAvailable.value && childInfo.value.childId) {
        try {
          await getAuthenticationOptions(childInfo.value.childId)
          authMode.value = 'webauthn'
        } catch {
          authMode.value = 'pin'
        }
      }
    } else {
      showToast(t('toast.loginSuccess'))
      router.push('/')
    }
  } catch (err: unknown) {
    if (axios.isAxiosError(err) && err.response?.status === 423) {
      step1Error.value = t('errors.ACCOUNT_LOCKED')
    } else {
      const code = axios.isAxiosError(err) ? err.response?.data?.code : undefined
      const i18nKey = code ? `errors.${code}` : ''
      if (i18nKey && t(i18nKey) !== i18nKey) {
        step1Error.value = t(i18nKey)
      } else {
        step1Error.value = t('errors.INVALID_CREDENTIALS')
      }
    }
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

    setUser({
      id: childInfo.value.childId,
      display_name: childInfo.value.displayName,
      avatar_color: childInfo.value.avatarColor,
      role: 'child',
    })

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

/* ── Step 1 header ── */
.auth-header {
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
  color: var(--color-muted);
  margin-top: 4px;
}

.login-form {
  width: 100%;
  max-width: 400px;
}
.form-actions { padding: 24px 16px 0; }

.step1-error {
  font-family: Inter, sans-serif;
  color: var(--color-brand-coral);
  font-size: 14px;
  text-align: center;
  margin: 8px 16px 0;
}

.password-field-wrapper :deep(.van-field__right-icon) { cursor: pointer; }

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
  font-weight: 700;
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
  width: 20px;
  height: 20px;
  border-radius: var(--radius-pill);
  border: 2px solid var(--color-muted-soft);
  background: transparent;
  transition: background 0.15s;
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

/* ── PIN action buttons ── */
.pin-actions { display: flex; gap: 16px; margin-bottom: 4px; }
.pin-action-btn {
  min-height: 44px;
  min-width: 80px;
  border: 1px solid var(--color-hairline);
  border-radius: var(--radius-md);
  background: var(--color-surface-soft);
  font-family: Inter, sans-serif;
  font-size: 14px;
  font-weight: 500;
  color: var(--color-body);
  cursor: pointer;
}

/* ── Utility buttons ── */
.switch-btn {
  margin-top: 16px;
  background: transparent;
  border: none;
  font-family: Inter, sans-serif;
  font-size: 13px;
  color: var(--color-muted);
  cursor: pointer;
  text-decoration: underline;
}
.back-btn {
  margin-top: 24px;
  background: transparent;
  border: none;
  font-family: Inter, sans-serif;
  font-size: 13px;
  color: var(--color-muted-soft);
  cursor: pointer;
}
</style>
