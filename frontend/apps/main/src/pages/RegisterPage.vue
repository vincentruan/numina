<template>
  <div class="auth-page" role="main" aria-label="创建家庭">
    <!-- Background particle canvas (full field, dim) -->
    <canvas ref="bgCanvasRef" class="deer-canvas deer-canvas--bg" aria-hidden="true"></canvas>
    <!-- Deer-masked particle canvas (bright particles clipped to deer silhouette) -->
    <canvas ref="deerCanvasRef" class="deer-canvas deer-canvas--deer" aria-hidden="true"></canvas>

    <div class="auth-content">
      <div class="auth-header">
        <NuminaLogo class="auth-logo" :width="220" />
        <h1 class="auth-title">{{ t('register.title') }}</h1>
        <p class="auth-subtitle">{{ t('register.subtitle') }}</p>
      </div>

      <van-form class="auth-form" @submit="onSubmit">
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

      <div class="auth-links">
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
@import '@/styles/auth-page.css';
</style>
