<template>
  <div class="login-page" role="main" aria-label="登录">
    <!-- Background particle canvas (full field, dim) -->
    <canvas ref="bgCanvasRef" class="deer-canvas deer-canvas--bg" aria-hidden="true"></canvas>
    <!-- Deer-masked particle canvas (bright particles clipped to deer silhouette) -->
    <canvas ref="deerCanvasRef" class="deer-canvas deer-canvas--deer" aria-hidden="true"></canvas>

    <!-- Login content (above canvas) -->
    <div class="login-content">
      <div class="login-header">
        <!-- Numina cursive wordmark — extracted to <NuminaLogo /> so the AI hub
             agent grid and other surfaces can reuse the same SVG. -->
        <NuminaLogo v-if="step === 1" class="numina-logo" :width="220" />

        <p v-if="step === 1" class="app-subtitle">
          <span class="subtitle-char c1">家</span><span class="subtitle-char c2">庭</span><span class="subtitle-char c3">资</span><span class="subtitle-char c4">产</span><span class="subtitle-char c5">可</span><span class="subtitle-char c6">视</span><span class="subtitle-char c7">化</span><span class="subtitle-char c8">管</span><span class="subtitle-char c9">理</span>
        </p>
      </div>

      <!-- Step 1: username + password -->
      <Transition name="step-fade" mode="out-in">
      <!-- Step 0: Account carousel -->
      <div v-if="step === 0" key="step0" class="account-select-step">
        <NuminaLogo class="numina-logo" :width="220" />
        <p class="step0-subtitle">{{ t('login.selectAccount') }}</p>

        <van-swipe :loop="false" :width="260" :show-indicators="true" class="account-swipe">
          <van-swipe-item
            v-for="user in boundUsers"
            :key="user.userId"
            @click="onSelectUser(user)"
          >
            <div class="account-card" :class="{ selected: selectedUser?.userId === user.userId }">
              <div class="account-avatar" :style="{ background: user.avatarColor }">
                {{ user.displayName.charAt(0) }}
              </div>
              <p class="account-name">{{ user.displayName }}</p>
              <span class="account-role">{{ t(`role.${user.role}`) }}</span>
            </div>
          </van-swipe-item>

          <van-swipe-item @click="switchToStep1">
            <div class="account-card account-card--other">
              <div class="account-avatar account-avatar--add">+</div>
              <p class="account-name">{{ t('login.otherAccount') }}</p>
            </div>
          </van-swipe-item>
        </van-swipe>

        <Transition name="step-fade">
          <div v-if="selectedUser && !(selectedUser.hasPasskey && webauthnSupported)" class="select-captcha-area">
            <p class="captcha-hint">{{ t('login.verifyToContinue') }}</p>
            <AltchaWidget
              ref="selectAltchaRef"
              v-model="selectAltcha"
              endpoint="login"
            />
          </div>
        </Transition>
      </div>

      <div v-else-if="step === 1" key="step1" class="login-form">
        <van-cell-group inset>
          <van-field
            v-model="form.username"
            name="username"
            :label="t('login.username')"
            :placeholder="t('login.usernamePlaceholder')"
            autocomplete="username"
          />
          <div class="password-field-wrapper">
            <van-field
              v-model="form.password"
              :type="showPassword ? 'text' : 'password'"
              name="password"
              :label="t('login.password')"
              :placeholder="t('login.passwordPlaceholder')"
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
            {{ t('common.next') }}
          </van-button>
        </div>
      </div>

      <!-- Step 2: PIN verification (numeric or emoji based on secondFactorType) -->
      <div v-else key="step2" class="pin-step">
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
        <p class="pin-hint">{{ secondFactorType === 'emoji_pin' ? t('secondFactor.emojiPinHint') : t('secondFactor.digitalPinHint') }}</p>

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
            v-for="n in [1,2,3,4,5,6,7,8,9,t('secondFactor.numpadClear'),0,t('secondFactor.numpadDelete')]"
            :key="n"
            class="numpad-btn"
            :class="{
              'numpad-action': n === t('secondFactor.numpadClear') || n === t('secondFactor.numpadDelete'),
              'numpad-action--delete': n === t('secondFactor.numpadDelete'),
              flash: flashKey === n,
            }"
            :disabled="loading"
            @click="onNumpadPress(n)"
          >{{ n }}</button>
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
            <button class="emoji-action-btn" :disabled="loading" @click="clearEmojiPin">{{ t('secondFactor.numpadClear') }}</button>
            <button class="emoji-action-btn emoji-action-btn--delete" :disabled="loading" @click="deleteEmoji">⌫</button>
          </div>
        </div>

        <van-button
          round
          block
          type="primary"
          :loading="loading"
          :disabled="secondFactorType === 'emoji_pin' ? emojiPin.length < 4 : pinInput.length < 6"
          class="pin-confirm-btn"
          @click="secondFactorType === 'emoji_pin' ? submitEmojiPin() : submitPin()"
        >{{ t('common.confirm') }}</van-button>

        <div class="form-actions back-actions">
          <van-button round block type="primary" class="back-btn-primary" :disabled="loading" @click="backToStep1">
            {{ t('login.backToLogin') }}
          </van-button>
        </div>
      </div>
      </Transition>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { showSuccessToast, showFailToast } from 'vant'
import { useAuthStore } from '@/stores/auth'
import { useDeerField } from '@/composables/useDeerField'
import { TrustedDeviceCard, readDeviceId } from '@numina/auth'
import { checkDevice, selectDeviceUser, getDeviceWebAuthnAuthOptions, verifyDeviceWebAuthn } from '@/api/device'
import type { DeviceCheckUser } from '@/api/device'
import { checkWebAuthnSupport, authenticatePasskey } from '@/utils/webauthn'
import { getChildBaseUrl } from '@/utils/childApp'
import NuminaLogo from '@/components/common/NuminaLogo.vue'

const { t } = useI18n()

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const loading = ref(false)
const altchaRef = ref()
const showPassword = ref(false)

const bgCanvasRef = ref<HTMLCanvasElement | null>(null)
const deerCanvasRef = ref<HTMLCanvasElement | null>(null)
useDeerField(bgCanvasRef, deerCanvasRef)

const step = ref<0 | 1 | 2>(1)
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

interface BoundUser {
  userId: string
  displayName: string
  avatarColor: string
  role: string
  secondFactorType: string | null
  hasPasskey: boolean
}
const boundUsers = ref<BoundUser[]>([])
const selectedUser = ref<BoundUser | null>(null)
const deviceIdRef = ref<string | null>(null)
const selectAltchaRef = ref()
const selectAltcha = ref<string | undefined>(undefined)
const webauthnSupported = ref(false)

// User info from step1 response — shown in step2 header
const step2User = ref<{ displayName: string; avatarColor: string } | null>(null)

const form = ref({
  username: '',
  password: '',
  altcha: undefined as string | undefined,
})

onMounted(async () => {
  const { supported } = checkWebAuthnSupport()
  webauthnSupported.value = supported

  try {
    const deviceId = await readDeviceId()

    if (!deviceId) return

    deviceIdRef.value = deviceId
    const { data } = await checkDevice(deviceId)

    if (data.trusted && data.users.length > 0) {
      boundUsers.value = data.users.map((u: DeviceCheckUser) => ({
        userId: String(u.user_id),
        displayName: u.display_name,
        avatarColor: u.avatar_color,
        role: u.role,
        secondFactorType: u.second_factor_type,
        hasPasskey: u.has_passkey,
      }))
      step.value = 0
    }
  } catch {
    // Non-fatal — fall through to step 1
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

    if (result.temp_token) {
      tempToken.value = result.temp_token
      secondFactorType.value = result.second_factor_type ?? 'numeric_pin'
      if (result.display_name && result.avatar_color) {
        step2User.value = { displayName: result.display_name, avatarColor: result.avatar_color }
      }
      step.value = 2
    } else if (!result.second_factor_required) {
      // Single-step login complete — token already set via cookie
      await authStore.fetchMe()
      // fetchMe() succeeded — safe to show success and navigate
      showSuccessToast(t('toast.loginSuccess'))
      authStore.showTrustPrompt = true
      const user = authStore.user
      if (user?.role === 'child') {
        const childBaseUrl = getChildBaseUrl()
      const redirect = route.query.redirect as string
      if (redirect && redirect.startsWith('/child/')) {
        window.location.href = `${childBaseUrl}${redirect.replace('/child/', '')}`
      } else {
        window.location.href = childBaseUrl
      }
        return
      }
      router.push('/')
    } else {
      // second_factor_required=true but no temp_token — malformed server response
      showFailToast(t('toast.loginFailedGeneric'))
    }
  } catch (error: unknown) {
    const axiosError = error as { response?: { data?: { code?: string; message?: string; detail?: string }; status?: number } }
    const code = axiosError.response?.data?.code
    const status = axiosError.response?.status
    if (code?.startsWith('CAPTCHA_') || status === 503) {
      altchaRef.value?.reset()
    }

    const i18nKey = code ? `errors.${code}` : ''
    if (i18nKey && t(i18nKey) !== i18nKey) {
      showFailToast(t(i18nKey))
    } else {
      const fallback = axiosError.response?.data?.message || axiosError.response?.data?.detail || t('toast.loginFailedGeneric')
      showFailToast(fallback)
    }
  } finally {
    loading.value = false
  }
}

function onSelectUser(user: BoundUser) {
  selectedUser.value = user

  if (user.hasPasskey && webauthnSupported.value) {
    authenticateWithWebAuthn(user)
  }
}

async function authenticateWithWebAuthn(user: BoundUser) {
  if (!deviceIdRef.value) return
  loading.value = true
  try {
    const { data: authOptions } = await getDeviceWebAuthnAuthOptions(
      deviceIdRef.value,
      user.userId,
    )

    const credential = await authenticatePasskey(authOptions.options)

    const { data } = await verifyDeviceWebAuthn(
      deviceIdRef.value,
      user.userId,
      credential,
      authOptions.challenge,
    )

    if (data.second_factor_required && data.temp_token) {
      tempToken.value = data.temp_token
      secondFactorType.value = data.second_factor_type ?? 'numeric_pin'
      trustedUser.value = {
        displayName: data.display_name ?? user.displayName,
        avatarColor: data.avatar_color ?? user.avatarColor,
      }
      step.value = 2
    } else {
      await authStore.fetchMe()
      showSuccessToast(t('toast.loginSuccess'))
      authStore.showTrustPrompt = true
      const authUser = authStore.user
      if (authUser?.role === 'child') {
        const childBaseUrl = getChildBaseUrl()
        window.location.href = childBaseUrl
        return
      }
      router.push('/')
    }
  } catch {
    showFailToast(t('toast.webauthnFailed'))
    // Fall back — show ALTCHA by resetting hasPasskey so template condition reveals captcha
    selectedUser.value = { ...user, hasPasskey: false }
  } finally {
    loading.value = false
  }
}

function switchToStep1() {
  step.value = 1
  selectedUser.value = null
  boundUsers.value = []
}

async function onSelectAltchaComplete() {
  if (!selectedUser.value || !deviceIdRef.value || !selectAltcha.value) return
  loading.value = true
  try {
    const { data } = await selectDeviceUser(
      deviceIdRef.value,
      selectedUser.value.userId,
      selectAltcha.value,
    )
    if (data.second_factor_required && data.temp_token) {
      tempToken.value = data.temp_token
      secondFactorType.value = data.second_factor_type ?? 'numeric_pin'
      trustedUser.value = {
        displayName: data.display_name ?? selectedUser.value.displayName,
        avatarColor: data.avatar_color ?? selectedUser.value.avatarColor,
      }
      step.value = 2
    } else {
      await authStore.fetchMe()
      showSuccessToast(t('toast.loginSuccess'))
      authStore.showTrustPrompt = true
      const user = authStore.user
      if (user?.role === 'child') {
        const childBaseUrl = getChildBaseUrl()
        window.location.href = childBaseUrl
        return
      }
      router.push('/')
    }
  } catch (error: unknown) {
    const axiosError = error as { response?: { data?: { code?: string; message?: string }; status?: number } }
    const code = axiosError.response?.data?.code
    if (code) {
      const i18nKey = `errors.${code}`
      showFailToast(t(i18nKey) !== i18nKey ? t(i18nKey) : axiosError.response?.data?.message || t('toast.loginFailedGeneric'))
    } else {
      showFailToast(t('toast.loginFailedGeneric'))
    }
    selectAltchaRef.value?.reset()
    selectAltcha.value = undefined
  } finally {
    loading.value = false
  }
}

watch(selectAltcha, (val) => {
  if (val) {
    onSelectAltchaComplete()
  }
})

function onNumpadPress(key: number | string) {
  flashKey.value = key
  setTimeout(() => { flashKey.value = null }, 150)

  if (key === t('secondFactor.numpadDelete') || key === '⌫') {
    pinInput.value = pinInput.value.slice(0, -1)
    pinError.value = ''
    return
  }
  if (key === t('secondFactor.numpadClear')) {
    pinInput.value = ''
    pinError.value = ''
    return
  }
  if (typeof key === 'number' && pinInput.value.length < 6) {
    pinInput.value += String(key)
    if (pinInput.value.length === 6) {
      submitPin()
    }
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
    showSuccessToast(t('toast.loginSuccess'))
    // Redirect based on user role
    const user = authStore.user
    if (user?.role === 'child') {
      const childBaseUrl = getChildBaseUrl()
      const redirect = route.query.redirect as string
      if (redirect && redirect.startsWith('/child/')) {
        window.location.href = `${childBaseUrl}${redirect.replace('/child/', '')}`
      } else {
        window.location.href = childBaseUrl
      }
      return
    }
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
    if (emojiPin.value.length === 4) {
      submitEmojiPin()
    }
  }
}

function deleteEmoji() {
  emojiPin.value.pop()
}

function clearEmojiPin() {
  emojiPin.value = []
  pinError.value = ''
}

async function submitEmojiPin() {
  if (emojiPin.value.length < 4 || submitting.value) return
  submitting.value = true
  loading.value = true
  pinError.value = ''
  try {
    await authStore.loginStep2({
      temp_token: tempToken.value,
      factor_type: 'emoji_pin',
      payload: { pin_sequence: emojiPin.value },
    })
    showSuccessToast(t('toast.loginSuccess'))
    const user = authStore.user
    if (user?.role === 'child') {
      const childBaseUrl = getChildBaseUrl()
      const redirect = route.query.redirect as string
      if (redirect && redirect.startsWith('/child/')) {
        window.location.href = `${childBaseUrl}${redirect.replace('/child/', '')}`
      } else {
        window.location.href = childBaseUrl
      }
      return
    }
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
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  background: #010120;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding-top: min(15vh, 60px);
  position: relative;
  overflow: hidden;
}

.deer-canvas {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.deer-canvas--bg {
  z-index: 0;
}

/* The deer canvas is masked to the deer SVG silhouette — mask applied via JS (blob URL) for mobile compatibility */
.deer-canvas--deer {
  z-index: 1;
  mask-repeat: no-repeat;
  mask-position: center center;
  mask-size: contain;
  -webkit-mask-repeat: no-repeat;
  -webkit-mask-position: center center;
  -webkit-mask-size: contain;
}

@media (min-width: 768px) {
  .deer-canvas--deer {
    mask-size: 72vh;
    -webkit-mask-size: 72vh;
  }
}

/* Respect user preference for reduced motion */
@media (prefers-reduced-motion: reduce) {
  .deer-canvas {
    display: none;
  }
}

.login-content {
  position: relative;
  z-index: 2;
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
  font-size: 15px;
  font-family: 'ZCOOL KuaiLe', 'Ma Shan Zheng', 'Noto Sans SC', cursive, sans-serif;
  font-weight: 400;
  letter-spacing: 0.12em;
  margin-top: 10px;
  display: flex;
  gap: 1px;
  justify-content: center;
}

.subtitle-char {
  display: inline-block;
  animation: subtitleFloat 3s ease-in-out infinite;
}

.subtitle-char:nth-child(odd) {
  animation-direction: alternate;
}

@keyframes subtitleFloat {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-3px); }
}

/* Stagger the float animation per character */
.subtitle-char.c1 { animation-delay: 0s; }
.subtitle-char.c2 { animation-delay: 0.1s; }
.subtitle-char.c3 { animation-delay: 0.2s; }
.subtitle-char.c4 { animation-delay: 0.3s; }
.subtitle-char.c5 { animation-delay: 0.4s; }
.subtitle-char.c6 { animation-delay: 0.5s; }
.subtitle-char.c7 { animation-delay: 0.6s; }
.subtitle-char.c8 { animation-delay: 0.7s; }
.subtitle-char.c9 { animation-delay: 0.8s; }

/* Rainbow colors — warm to cool cycle */
.c1 { color: #ff6b6b; }
.c2 { color: #ff9f43; }
.c3 { color: #ffd93d; }
.c4 { color: #6bcb77; }
.c5 { color: #4ecdc4; }
.c6 { color: #74b9ff; }
.c7 { color: #a29bfe; }
.c8 { color: #fd79a8; }
.c9 { color: #fdcb6e; }

@media (prefers-reduced-motion: reduce) {
  .subtitle-char {
    animation: none;
  }
}

.login-form {
  width: 100%;
  max-width: 400px;
  padding: 0 16px;
}

/* Strip Vant inset group card styling */
.login-form :deep(.van-cell-group--inset) {
  margin: 0;
  border-radius: 0;
  box-shadow: none;
  background: transparent;
  /* Allow backdrop-filter and focus glow to escape the group boundary */
  overflow: visible;
}

/* Dark theme overrides for Vant components in login form */
.login-form :deep(.van-cell-group) {
  background: transparent;
}

/* Glass morphism input fields */
.login-form :deep(.van-cell) {
  background: rgba(255, 255, 255, 0.06);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 2px solid rgba(189, 187, 255, 0.35);
  border-radius: 8px;
  margin-bottom: 14px;
  transition: border-color 0.25s, box-shadow 0.25s, background 0.25s;
  box-shadow:
    0 4px 16px rgba(1, 1, 32, 0.3),
    inset 0 1px 0 rgba(255, 255, 255, 0.08);
}

/* Hide Vant's default bottom hairline divider */
.login-form :deep(.van-cell)::after {
  display: none;
}

.login-form :deep(.van-cell):focus-within {
  border-color: #bdbbff;
  background: rgba(189, 187, 255, 0.1);
  /* Multi-layer glow: ring + mid spread + outer halo — visible on mobile */
  box-shadow:
    0 0 0 3px rgba(189, 187, 255, 0.3),
    0 0 18px rgba(189, 187, 255, 0.55),
    0 0 40px rgba(189, 187, 255, 0.2),
    inset 0 1px 0 rgba(255, 255, 255, 0.12);
}

.login-form :deep(.van-field__label) {
  color: rgba(255, 255, 255, 0.9);
  font-weight: 500;
}

.login-form :deep(.van-field__control) {
  color: #fff;
  caret-color: #bdbbff;
}

.login-form :deep(.van-field__placeholder) {
  color: rgba(255, 255, 255, 0.35);
}

.login-form :deep(.van-field__right-icon) {
  color: rgba(189, 187, 255, 0.8);
}

.form-actions {
  padding: 20px 0 0;
}

/* Glass morphism button — background uses white glass token per Visual Standards */
.form-actions :deep(.van-button--primary) {
  --van-button-primary-background: rgba(255, 255, 255, 0.12);
  --van-button-primary-border-color: rgba(189, 187, 255, 0.6);
  --van-button-primary-color: #fff;
  font-weight: 600;
  letter-spacing: 0.06em;
  transition: box-shadow 0.25s, background 0.25s, border-color 0.25s;
  box-shadow:
    0 0 0 1px rgba(189, 187, 255, 0.15),
    0 0 20px rgba(189, 187, 255, 0.25),
    inset 0 1px 0 rgba(255, 255, 255, 0.1);
}

.form-actions :deep(.van-button--primary:active) {
  --van-button-primary-background: rgba(255, 255, 255, 0.2);
  --van-button-primary-border-color: #bdbbff;
  box-shadow:
    0 0 0 3px rgba(189, 187, 255, 0.35),
    0 0 28px rgba(189, 187, 255, 0.55),
    0 0 56px rgba(189, 187, 255, 0.2),
    inset 0 1px 0 rgba(255, 255, 255, 0.15);
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
  border: 2px solid rgba(189, 187, 255, 0.5);
  background: transparent;
  transition: background 0.15s, border-color 0.15s, box-shadow 0.15s;
}

.pin-slot.filled {
  background: #bdbbff;
  border-color: #bdbbff;
  box-shadow: 0 0 8px rgba(189, 187, 255, 0.7);
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
  height: 64px;
  border: 1px solid rgba(189, 187, 255, 0.2);
  border-radius: 8px;
  background: rgba(189, 187, 255, 0.08);
  color: #fff;
  font-size: 22px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s, transform 0.1s, border-color 0.15s, box-shadow 0.15s;
}

.numpad-btn:hover:not(:disabled) {
  background: rgba(189, 187, 255, 0.15);
  border-color: rgba(189, 187, 255, 0.45);
}

.numpad-btn:active:not(:disabled) {
  background: rgba(189, 187, 255, 0.3);
  border-color: rgba(189, 187, 255, 0.7);
  transform: scale(0.93);
  box-shadow: 0 0 12px rgba(189, 187, 255, 0.35);
}

.numpad-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.numpad-action {
  font-size: 14px !important;
  font-weight: 600 !important;
  background: rgba(189, 187, 255, 0.14) !important;
  border-color: rgba(189, 187, 255, 0.5) !important;
  color: #fff !important;
}

.numpad-action--delete {
  font-size: 28px !important;
}

.emoji-action-btn--delete {
  font-size: 22px !important;
  font-weight: 700 !important;
}

@keyframes flash {
  0% { background: rgba(189, 187, 255, 0.08); box-shadow: none; }
  40% { background: rgba(189, 187, 255, 0.45); box-shadow: 0 0 16px rgba(189, 187, 255, 0.5); }
  100% { background: rgba(189, 187, 255, 0.08); box-shadow: none; }
}

.numpad-btn.flash {
  animation: flash 0.18s ease-out;
}

.numpad-action.flash {
  animation: flash 0.18s ease-out;
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
  --van-button-primary-background: rgba(189, 187, 255, 0.18);
  --van-button-primary-border-color: rgba(189, 187, 255, 0.7);
  --van-button-primary-color: #fff;
  font-weight: 600;
  letter-spacing: 0.04em;
  transition: box-shadow 0.2s, background 0.2s;
  box-shadow: 0 0 16px rgba(189, 187, 255, 0.2);
}

.back-actions {
  padding: 0;
  width: 100%;
  max-width: 280px;
}

.back-btn-primary {
  --van-button-primary-background: rgba(255, 255, 255, 0.06);
  --van-button-primary-border-color: rgba(255, 255, 255, 0.25);
  --van-button-primary-color: rgba(255, 255, 255, 0.75);
  font-weight: 500;
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
  border: 2px solid rgba(189, 187, 255, 0.4);
  background: rgba(189, 187, 255, 0.05);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  transition: background 0.15s, border-color 0.15s, box-shadow 0.15s;
}

.emoji-pin-slot.filled {
  background: rgba(189, 187, 255, 0.15);
  border-color: rgba(189, 187, 255, 0.9);
  box-shadow: 0 0 10px rgba(189, 187, 255, 0.35);
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
  border: 1px solid rgba(189, 187, 255, 0.2);
  border-radius: 8px;
  background: rgba(189, 187, 255, 0.07);
  cursor: pointer;
  transition: background 0.1s, transform 0.1s, border-color 0.1s, box-shadow 0.1s;
}

.emoji-btn:hover:not(:disabled) {
  background: rgba(189, 187, 255, 0.14);
  border-color: rgba(189, 187, 255, 0.4);
}

.emoji-btn:active:not(:disabled) {
  transform: scale(0.91);
  background: rgba(189, 187, 255, 0.28);
  border-color: rgba(189, 187, 255, 0.65);
  box-shadow: 0 0 10px rgba(189, 187, 255, 0.3);
}

.emoji-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.emoji-btn.flash {
  animation: flash 0.18s ease-out;
}

.emoji-actions {
  display: flex;
  gap: 12px;
  margin-bottom: 8px;
}

.emoji-action-btn {
  min-height: 44px;
  min-width: 88px;
  border: 1px solid rgba(189, 187, 255, 0.3);
  border-radius: 8px;
  background: rgba(189, 187, 255, 0.08);
  font-size: 14px;
  font-weight: 500;
  color: #bdbbff;
  cursor: pointer;
  transition: background 0.15s, box-shadow 0.15s;
}

.emoji-action-btn:active {
  background: rgba(189, 187, 255, 0.22);
  box-shadow: 0 0 10px rgba(189, 187, 255, 0.25);
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

/* Step transition */
.step-fade-enter-active,
.step-fade-leave-active {
  transition: opacity 0.22s ease, transform 0.22s ease;
}

.step-fade-enter-from {
  opacity: 0;
  transform: translateX(20px);
}

.step-fade-leave-to {
  opacity: 0;
  transform: translateX(-20px);
}

/* Step 0: Account carousel */
.account-select-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding-top: 60px;
}

.step0-subtitle {
  color: rgba(255, 255, 255, 0.7);
  font-size: 14px;
  margin-bottom: 24px;
}

.account-swipe {
  width: 100%;
  max-width: 340px;
}

.account-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 24px 16px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.06);
  backdrop-filter: blur(16px);
  border: 2px solid rgba(189, 187, 255, 0.35);
  transition: border-color 0.2s, box-shadow 0.2s;
  min-height: 160px;
  justify-content: center;
}

.account-card.selected {
  border-color: #bdbbff;
  box-shadow: 0 0 20px rgba(189, 187, 255, 0.4);
}

.account-card--other {
  opacity: 0.7;
}

.account-avatar {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  font-weight: 700;
  color: #fff;
  margin-bottom: 12px;
}

.account-avatar--add {
  background: rgba(189, 187, 255, 0.2);
  font-size: 32px;
  font-weight: 300;
}

.account-name {
  color: var(--text-primary, #f5f5f5);
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 4px;
}

.account-role {
  color: rgba(255, 255, 255, 0.5);
  font-size: 12px;
}

.select-captcha-area {
  margin-top: 24px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.captcha-hint {
  color: rgba(255, 255, 255, 0.6);
  font-size: 13px;
}

.account-swipe :deep(.van-swipe__indicator) {
  background: rgba(189, 187, 255, 0.3);
}

.account-swipe :deep(.van-swipe__indicator--active) {
  background: #bdbbff;
}
</style>

<style>
@font-face {
  font-family: 'ZCOOL KuaiLe';
  font-style: normal;
  font-weight: 400;
  font-display: swap;
  src: url('/fonts/zcool-kuaile-latin-400-normal.woff2') format('woff2');
  unicode-range: U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+0304, U+0308, U+0329, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD;
}
@font-face {
  font-family: 'ZCOOL KuaiLe';
  font-style: normal;
  font-weight: 400;
  font-display: swap;
  src: url('/fonts/zcool-kuaile-chinese-simplified-400-normal.woff2') format('woff2');
  unicode-range: U+0100-02BA, U+02BD-02C5, U+02C7-02CC, U+02CE-02D7, U+02DD-02FF, U+0304, U+0308, U+0329, U+1D00-1DBF, U+1E00-1E9F, U+1EF2-1EFF, U+2020, U+20A0-20AB, U+20AD-20C0, U+2113, U+2C60-2C7F, U+A720-A7FF, U+3000-9FFF, U+F900-FAFF, U+FE30-FE4F;
}
</style>
