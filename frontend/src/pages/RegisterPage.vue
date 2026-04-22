<template>
  <div class="register-page">
    <div class="register-header">
      <h1 class="app-title">创建家庭</h1>
      <p class="app-subtitle">创建一个新的家庭账本</p>
    </div>

    <van-form class="register-form" @submit="onSubmit">
      <van-cell-group inset>
        <van-field
          v-model="form.family_invitation_code"
          label="家庭邀请码"
          placeholder="请输入6位邀请码"
          maxlength="6"
          :formatter="formatInvitationCode"
          format-trigger="onBlur"
          :rules="[{ required: true, message: '请输入邀请码' }]"
        />
        <van-field
          v-model="form.family_name"
          label="家庭名称"
          placeholder="请输入家庭名称"
          :rules="[{ required: true, message: '请输入家庭名称' }]"
          :error-message="getError('family_name')?.msg"
          @blur="validateField('family_name')"
        />
        <van-field
          v-model="form.username"
          label="用户名"
          placeholder="请输入用户名"
          :rules="[{ required: true, message: '请输入用户名' }]"
          :error-message="getError('username')?.msg"
          @blur="validateField('username')"
        />
        <van-field
          v-model="form.display_name"
          label="显示名称"
          placeholder="请输入显示名称"
          :rules="[{ required: true, message: '请输入显示名称' }]"
          @blur="validateField('display_name')"
        />
        <div class="password-field-wrapper">
          <van-field
            v-model="form.password"
            :type="showPassword ? 'text' : 'password'"
            label="密码"
            placeholder="请输入密码(至少6位)"
            :rules="[
              { required: true, message: '请输入密码' },
              { validator: validatePassword, message: '密码至少6位' }
            ]"
            :error-message="getError('password')?.msg"
            @blur="validateField('password')"
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
            label="确认密码"
            placeholder="请再次输入密码"
            :rules="[
              { required: true, message: '请确认密码' },
              { validator: validateConfirmPassword, message: '两次密码不一致' }
            ]"
            @blur="validateField('confirm')"
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
          创建并注册
        </van-button>
      </div>
    </van-form>

    <div class="register-links">
      <router-link to="/login">已有账号？去登录</router-link>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, provide } from 'vue'
import { useRouter } from 'vue-router'
import { showToast } from 'vant'
import { useAuthStore } from '@/stores/auth'
import AltchaWidget from '@/components/common/AltchaWidget.vue'
import PasswordStrengthIndicator from '@/components/common/PasswordStrengthIndicator.vue'
import { useValidationErrors, validationErrorsKey } from '@/composables/useValidationErrors'

const router = useRouter()
const authStore = useAuthStore()
const loading = ref(false)
const confirmPassword = ref('')
const altchaRef = ref()
const showPassword = ref(false)
const showConfirmPassword = ref(false)

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

// Real-time validation functions
function validatePassword(value: string): boolean {
  return value.length >= 6
}

function validateConfirmPassword(value: string): boolean {
  return value === form.value.password
}

function validateField(field: string) {
  // Trigger real-time validation feedback
  // Vant's van-field handles this via :rules prop
}

async function onSubmit() {
  clearErrors()
  loading.value = true
  try {
    await authStore.register(form.value)
    showToast('注册成功')
    router.push('/')
  } catch (error: any) {
    // Handle field-level validation errors (422)
    setErrors(error)

    // Handle captcha-related errors
    const code = error.response?.data?.code || ''
    const message = error.response?.data?.message || ''
    const status = error.response?.status

    const isCaptchaError = code.startsWith('CAPTCHA_')
    if (status === 503 || code === 'CAPTCHA_SERVICE_UNAVAILABLE') {
      showToast(message || '验证服务暂时不可用，请稍后重试')
    } else if (isCaptchaError) {
      // Captcha error - reset widget but preserve form data
      altchaRef.value?.reset()
      showToast(message)
    } else if (code === 'FAMILY_INVITATION_CODE_NOT_FOUND') {
      showToast('邀请码不存在')
    } else if (code === 'FAMILY_INVITATION_CODE_ALREADY_USED') {
      showToast('邀请码已被使用')
    } else if (code === 'FAMILY_INVITATION_CODE_REVOKED') {
      showToast('邀请码已被撤销')
    }
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.register-page {
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  flex-direction: column;
  align-items: center;
  padding-top: 10vh;
}
.register-header {
  text-align: center;
  margin-bottom: 30px;
}
.app-title {
  font-size: 28px;
  font-weight: 700;
  color: #fff;
  margin: 0;
}
.app-subtitle {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.8);
  margin-top: 8px;
}
.register-form {
  width: 100%;
  max-width: 400px;
}
.password-field-wrapper {
  position: relative;
}
.password-field-wrapper :deep(.van-field__right-icon) {
  cursor: pointer;
  color: var(--van-field-right-icon-color);
}
.form-actions {
  padding: 24px 16px 0;
}
.register-links {
  margin-top: 20px;
  text-align: center;
}
.register-links a {
  color: rgba(255, 255, 255, 0.9);
  textDecoration: none;
  font-size: 14px;
}
</style>
