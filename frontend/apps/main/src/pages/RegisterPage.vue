<template>
  <div class="register-page" role="main" aria-label="创建家庭">
    <!-- Background particle canvas (full field, dim) -->
    <canvas ref="bgCanvasRef" class="deer-canvas deer-canvas--bg" aria-hidden="true"></canvas>
    <!-- Deer-masked particle canvas (bright particles clipped to deer silhouette) -->
    <canvas ref="deerCanvasRef" class="deer-canvas deer-canvas--deer" aria-hidden="true"></canvas>

    <div class="register-content">
      <div class="register-header">
        <NuminaLogo class="numina-logo" :width="220" />
        <h1 class="app-title">{{ t('register.title') }}</h1>
        <p class="app-subtitle">{{ t('register.subtitle') }}</p>
      </div>

      <van-form class="register-form" @submit="onSubmit">
        <van-cell-group inset>
          <van-field
            v-model="form.family_invitation_code"
            :label="t('register.inviteCodeLabel')"
            :placeholder="t('register.inviteCodePlaceholder')"
            maxlength="6"
            :formatter="formatInvitationCode"
            format-trigger="onBlur"
            :rules="[
              { required: true, message: t('auth.form.inviteCodeRequired') },
              { validator: validateInvitationCode, message: t('auth.form.inviteCodeLength') }
            ]"
          />
          <van-field
            v-model="form.family_name"
            :label="t('register.familyNameLabel')"
            :placeholder="t('register.familyNamePlaceholder')"
            :rules="[{ required: true, message: t('auth.form.familyNameRequired') }]"
            :error-message="getError('family_name')?.msg"
          />
          <van-field
            v-model="form.username"
            :label="t('register.usernameLabel')"
            :placeholder="t('register.usernamePlaceholder')"
            :formatter="formatUsername"
            format-trigger="onChange"
            :rules="[{ required: true, message: t('auth.form.usernameRequired') }]"
            :error-message="getError('username')?.msg"
          />
          <van-field
            v-model="form.display_name"
            :label="t('register.displayNameLabel')"
            :placeholder="t('register.displayNamePlaceholder')"
            :rules="[{ required: true, message: t('auth.form.displayNameRequired') }]"
          />
          <div class="password-field-wrapper">
            <van-field
              v-model="form.password"
              :type="showPassword ? 'text' : 'password'"
              :label="t('register.passwordLabel')"
              :placeholder="t('register.passwordPlaceholder')"
              :rules="[
                { required: true, message: t('auth.form.passwordRequired') },
                { validator: validatePassword, message: t('auth.form.passwordMin8') }
              ]"
              :error-message="getError('password')?.msg"
            >
              <template #right-icon>
                <van-icon :name="showPassword ? 'eye-o' : 'closed-eye'" @click="showPassword = !showPassword" />
              </template>
            </van-field>
            <PasswordStrengthIndicator :password="form.password" />
          </div>
          <div class="password-field-wrapper">
            <van-field
              v-model="confirmPassword"
              :type="showConfirmPassword ? 'text' : 'password'"
              :label="t('register.confirmPasswordLabel')"
              :placeholder="t('register.confirmPasswordPlaceholder')"
              :rules="[
                { required: true, message: t('auth.form.confirmPasswordRequired') },
                { validator: validateConfirmPassword, message: t('auth.form.passwordMismatch') }
              ]"
            >
              <template #right-icon>
                <van-icon :name="showConfirmPassword ? 'eye-o' : 'closed-eye'" @click="showConfirmPassword = !showConfirmPassword" />
              </template>
            </van-field>
          </div>
        </van-cell-group>

        <!-- ALTCHA captcha widget -->
        <AltchaWidget ref="altchaRef" v-model="form.altcha" endpoint="register" />

        <div class="form-actions">
          <van-button round block type="primary" native-type="submit" :loading="loading">
            {{ t('register.submitBtn') }}
          </van-button>
        </div>
      </van-form>

      <div class="register-links">
        <router-link to="/login">{{ t('auth.hasAccountLogin') }}</router-link>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, provide } from 'vue'
import { useRouter } from 'vue-router'
import { showSuccessToast, showFailToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import { useDeerField } from '@/composables/useDeerField'
import AltchaWidget from '@/components/common/AltchaWidget.vue'
import PasswordStrengthIndicator from '@/components/common/PasswordStrengthIndicator.vue'
import NuminaLogo from '@/components/common/NuminaLogo.vue'
import { useValidationErrors, validationErrorsKey } from '@/composables/useValidationErrors'

const { t } = useI18n()

const router = useRouter()
const authStore = useAuthStore()
const loading = ref(false)
const confirmPassword = ref('')
const altchaRef = ref()
const showPassword = ref(false)
const showConfirmPassword = ref(false)

const bgCanvasRef = ref<HTMLCanvasElement | null>(null)
const deerCanvasRef = ref<HTMLCanvasElement | null>(null)
useDeerField(bgCanvasRef, deerCanvasRef)

const validationErrorsComposable = useValidationErrors()
const { setErrors, clearErrors, getError } = validationErrorsComposable
provide(validationErrorsKey, validationErrorsComposable)

const form = ref({
  family_invitation_code: '',
  family_name: '',
  username: '',
  display_name: '',
  password: '',
  altcha: undefined as string | undefined
})

// Formatter for invitation code (auto-uppercase)
function formatInvitationCode(value: string): string {
  return value.toUpperCase()
}

// Formatter for username (auto-lowercase)
function formatUsername(value: string): string {
  return value.toLowerCase()
}

// Validate invitation code length (4-6)
function validateInvitationCode(value: string): boolean {
  return value.length >= 4 && value.length <= 6
}

// Real-time validation functions
function validatePassword(value: string): boolean {
  return value.length >= 8
}

function validateConfirmPassword(value: string): boolean {
  return value === form.value.password
}

async function onSubmit() {
  clearErrors()
  loading.value = true
  try {
    await authStore.register(form.value)
    showSuccessToast(t('toast.registerSuccess'))
    router.push('/')
  } catch (error: unknown) {
    // Handle field-level validation errors (422)
    setErrors(error)

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
.register-page {
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

.register-content {
  position: relative;
  z-index: 2;
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
}

.register-header {
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

.register-form {
  width: 100%;
  max-width: 400px;
  padding: 0 16px;
}

/* Strip Vant inset group card styling */
.register-form :deep(.van-cell-group--inset) {
  margin: 0;
  border-radius: 0;
  box-shadow: none;
  background: transparent;
  overflow: visible;
}

/* Dark theme overrides for Vant components in register form */
.register-form :deep(.van-cell-group) {
  background: transparent;
}

/* Glass morphism input fields — matches login page */
.register-form :deep(.van-cell) {
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
.register-form :deep(.van-cell)::after {
  display: none;
}

.register-form :deep(.van-cell):focus-within {
  border-color: #bdbbff;
  background: rgba(189, 187, 255, 0.1);
  box-shadow:
    0 0 0 3px rgba(189, 187, 255, 0.3),
    0 0 18px rgba(189, 187, 255, 0.55),
    0 0 40px rgba(189, 187, 255, 0.2),
    inset 0 1px 0 rgba(255, 255, 255, 0.12);
}

.register-form :deep(.van-field__label) {
  color: rgba(255, 255, 255, 0.9);
  font-weight: 500;
}

.register-form :deep(.van-field__control) {
  color: #fff;
  caret-color: #bdbbff;
}

.register-form :deep(.van-field__placeholder) {
  color: rgba(255, 255, 255, 0.35);
}

.register-form :deep(.van-field__right-icon) {
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

.register-links {
  margin-top: 20px;
  text-align: center;
}

.register-links a {
  color: rgba(255, 255, 255, 0.9);
  text-decoration: none;
  font-size: 14px;
}
</style>
