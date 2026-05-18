<template>
  <div class="join-page">
    <div class="join-header">
      <h1 class="app-title">加入家庭</h1>
      <p class="app-subtitle">使用邀请码加入已有家庭</p>
    </div>

    <van-form class="join-form" @submit="onSubmit">
      <van-cell-group inset>
        <van-field
          v-model="form.invite_code"
          label="邀请码"
          placeholder="请输入家庭邀请码"
          :rules="[{ required: true, message: t('auth.form.inviteCodeRequired') }]"
        />
        <van-field
          v-model="form.username"
          label="用户名"
          placeholder="请输入用户名"
          :rules="[{ required: true, message: t('auth.form.usernameRequired') }]"
        />
        <van-field
          v-model="form.display_name"
          label="显示名称"
          placeholder="请输入显示名称"
          :rules="[{ required: true, message: t('auth.form.displayNameRequired') }]"
        />
        <div class="password-field-wrapper">
          <van-field
            v-model="form.password"
            :type="showPassword ? 'text' : 'password'"
            label="密码"
            placeholder="请输入密码(至少6位)"
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
            label="确认密码"
            placeholder="请再次输入密码"
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
          加入家庭
        </van-button>
      </div>
    </van-form>

    <div class="join-links">
      <router-link to="/login">已有账号？去登录</router-link>
      <span class="divider">|</span>
      <router-link to="/register">创建新家庭</router-link>
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

const { t } = useI18n()

const router = useRouter()
const authStore = useAuthStore()
const loading = ref(false)
const confirmPassword = ref('')
const altchaRef = ref()
const showPassword = ref(false)
const showConfirmPassword = ref(false)

const form = ref({
  invite_code: '',
  username: '',
  display_name: '',
  password: '',
  altcha: undefined as string | undefined
})

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
      showToast(t(i18nKey))
    }
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.join-page {
  min-height: 100vh;
  background: linear-gradient(160deg, #010120 0%, #000010 100%);
  display: flex;
  flex-direction: column;
  align-items: center;
  padding-top: 10vh;
}
.join-header {
  text-align: center;
  margin-bottom: 30px;
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
}
.form-actions {
  padding: 24px 16px 0;
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
.password-field-wrapper :deep(.van-field__right-icon) {
  cursor: pointer;
  color: var(--van-field-right-icon-color);
}
</style>
