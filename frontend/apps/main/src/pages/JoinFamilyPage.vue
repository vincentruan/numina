<template>
  <div class="join-page" role="main" aria-label="加入家庭">
    <!-- Background particle canvas (full field, dim) -->
    <canvas ref="bgCanvasRef" class="deer-canvas deer-canvas--bg" aria-hidden="true"></canvas>
    <!-- Deer-masked particle canvas (bright particles clipped to deer silhouette) -->
    <canvas ref="deerCanvasRef" class="deer-canvas deer-canvas--deer" aria-hidden="true"></canvas>

    <div class="join-content">
      <div class="join-header">
        <NuminaLogo class="numina-logo" :width="220" />
        <h1 class="app-title">{{ t('auth.joinFamilyTitle') }}</h1>
        <p class="app-subtitle">{{ t('auth.joinFamilySubtitle') }}</p>
      </div>

      <van-form class="join-form" @submit="onSubmit">
        <van-cell-group inset>
          <van-field
            v-model="form.invite_code"
            :label="t('auth.inviteCodeLabel')"
            :placeholder="t('auth.inviteCodePlaceholder')"
            :formatter="formatInviteCode"
            format-trigger="onChange"
            :rules="[{ required: true, message: t('auth.form.inviteCodeRequired') }]"
          />
          <van-field
            v-model="form.username"
            :label="t('auth.usernameLabel')"
            :placeholder="t('auth.usernamePlaceholder')"
            :formatter="formatUsername"
            format-trigger="onChange"
            :rules="[{ required: true, message: t('auth.form.usernameRequired') }]"
          />
          <van-field
            v-model="form.display_name"
            :label="t('auth.displayNameLabel')"
            :placeholder="t('auth.displayNamePlaceholder')"
            :rules="[{ required: true, message: t('auth.form.displayNameRequired') }]"
          />
          <div class="password-field-wrapper">
            <van-field
              v-model="form.password"
              :type="showPassword ? 'text' : 'password'"
              :label="t('auth.passwordLabel')"
              :placeholder="t('auth.passwordPlaceholder')"
              :rules="[
                { required: true, message: t('auth.form.passwordRequired') },
                { validator: (v: string) => v.length >= 6, message: t('auth.form.passwordMin6') }
              ]"
            >
              <template #right-icon>
                <van-icon :name="showPassword ? 'eye-o' : 'closed-eye'" @click="showPassword = !showPassword" />
              </template>
            </van-field>
          </div>
          <div class="password-field-wrapper">
            <van-field
              v-model="confirmPassword"
              :type="showConfirmPassword ? 'text' : 'password'"
              :label="t('auth.confirmPasswordLabel')"
              :placeholder="t('auth.confirmPasswordPlaceholder')"
              :rules="[
                { required: true, message: t('auth.form.confirmPasswordRequired') },
                { validator: (v: string) => v === form.password, message: t('auth.form.passwordMismatch') }
              ]"
            >
              <template #right-icon>
                <van-icon :name="showConfirmPassword ? 'eye-o' : 'closed-eye'" @click="showConfirmPassword = !showConfirmPassword" />
              </template>
            </van-field>
          </div>
        </van-cell-group>

        <!-- ALTCHA captcha widget -->
        <AltchaWidget ref="altchaRef" v-model="form.altcha" endpoint="join-family" />

        <div class="form-actions">
          <van-button round block type="primary" native-type="submit" :loading="loading">
            {{ t('auth.joinFamilyButton') }}
          </van-button>
        </div>
      </van-form>

      <div class="join-links">
        <router-link to="/login">{{ t('auth.hasAccountLogin') }}</router-link>
        <span class="divider">|</span>
        <router-link to="/register">{{ t('auth.createNewFamily') }}</router-link>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { showToast, showFailToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import { useDeerField } from '@/composables/useDeerField'
import AltchaWidget from '@/components/common/AltchaWidget.vue'
import NuminaLogo from '@/components/common/NuminaLogo.vue'

const { t } = useI18n()

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const loading = ref(false)
const confirmPassword = ref('')
const altchaRef = ref()
const showPassword = ref(false)
const showConfirmPassword = ref(false)

const bgCanvasRef = ref<HTMLCanvasElement | null>(null)
const deerCanvasRef = ref<HTMLCanvasElement | null>(null)
useDeerField(bgCanvasRef, deerCanvasRef)

const form = ref({
  invite_code: '',
  username: '',
  display_name: '',
  password: '',
  altcha: undefined as string | undefined
})

// Formatter for invite code (auto-uppercase)
function formatInviteCode(value: string): string {
  return value.toUpperCase()
}

// Pre-fill invite code from share link (?code=XXXXXX)
onMounted(() => {
  const code = route.query.code
  if (typeof code === 'string' && code.length > 0) {
    form.value.invite_code = code.toUpperCase()
  }
})

// Formatter for username (auto-lowercase)
function formatUsername(value: string): string {
  return value.toLowerCase()
}

async function onSubmit() {
  loading.value = true
  try {
    await authStore.joinFamily(form.value)
    showToast(t('toast.joinSuccess'))
    router.push('/')
  } catch (error: unknown) {
    // Handle captcha-related errors
    const err = error as { response?: { data?: { code?: string }; status?: number } }
    const code = err.response?.data?.code || ''
    const status = err.response?.status

    if (code.startsWith('CAPTCHA_') || status === 503) {
      altchaRef.value?.reset()
    }

    // Use i18n for known error codes; api interceptor handles non-auth errors
    const i18nKey = code ? `errors.${code}` : ''
    if (i18nKey && t(i18nKey) !== i18nKey) {
      showFailToast(t(i18nKey))
    }
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.join-page {
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

@media (prefers-reduced-motion: reduce) {
  .deer-canvas {
    display: none;
  }
}

.join-content {
  position: relative;
  z-index: 2;
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
}

.join-header {
  text-align: center;
  margin-bottom: 30px;
}

.numina-logo {
  width: 220px;
  height: auto;
  display: block;
  margin: 0 auto 10px;
}

.app-title {
  font-size: 28px;
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

.join-form {
  width: 100%;
  max-width: 400px;
  padding: 0 16px;
}

/* Strip Vant inset group card styling */
.join-form :deep(.van-cell-group--inset) {
  margin: 0;
  border-radius: 0;
  box-shadow: none;
  background: transparent;
  overflow: visible;
}

/* Dark theme overrides for Vant components in join form */
.join-form :deep(.van-cell-group) {
  background: transparent;
}

/* Glass morphism input fields — matches login page */
.join-form :deep(.van-cell) {
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
.join-form :deep(.van-cell)::after {
  display: none;
}

.join-form :deep(.van-cell):focus-within {
  border-color: #bdbbff;
  background: rgba(189, 187, 255, 0.1);
  box-shadow:
    0 0 0 3px rgba(189, 187, 255, 0.3),
    0 0 18px rgba(189, 187, 255, 0.55),
    0 0 40px rgba(189, 187, 255, 0.2),
    inset 0 1px 0 rgba(255, 255, 255, 0.12);
}

.join-form :deep(.van-field__label) {
  color: rgba(255, 255, 255, 0.9);
  font-weight: 500;
}

.join-form :deep(.van-field__control) {
  color: #fff;
  caret-color: #bdbbff;
}

.join-form :deep(.van-field__placeholder) {
  color: rgba(255, 255, 255, 0.35);
}

.join-form :deep(.van-field__right-icon) {
  color: rgba(189, 187, 255, 0.8);
}

.password-field-wrapper {
  position: relative;
}

.password-field-wrapper :deep(.van-field__right-icon) {
  cursor: pointer;
}

.form-actions {
  padding: 20px 0 0;
}

/* Glass morphism button — matches login page */
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

.join-links {
  margin-top: 20px;
  text-align: center;
}

.join-links a {
  color: rgba(255, 255, 255, 0.9);
  text-decoration: none;
  font-size: 14px;
}

.divider {
  color: rgba(255, 255, 255, 0.5);
  margin: 0 12px;
}
</style>
