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
        <h1 class="app-title">Numina</h1>
        <p class="app-subtitle">家庭资产可视化管理</p>
      </div>

      <van-form class="login-form" @submit="onSubmit">
        <van-cell-group inset>
          <van-field
            v-model="form.username"
            name="username"
            label="用户名"
            placeholder="请输入用户名"
            :rules="[{ required: true, message: '请输入用户名' }]"
          />
          <div class="password-field-wrapper">
            <van-field
              v-model="form.password"
              :type="showPassword ? 'text' : 'password'"
              name="password"
              label="密码"
              placeholder="请输入密码"
              :rules="[{ required: true, message: '请输入密码' }]"
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
          <van-button round block type="primary" native-type="submit" :loading="loading">
            登录
          </van-button>
        </div>
      </van-form>

      <div class="login-links">
        <router-link to="/register">创建家庭</router-link>
        <span class="divider">|</span>
        <router-link to="/join-family">加入家庭</router-link>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { showToast } from 'vant'
import { useAuthStore } from '@/stores/auth'
import AltchaWidget from '@/components/common/AltchaWidget.vue'
import { useStarField } from '@/composables/useStarField'

const router = useRouter()
const authStore = useAuthStore()
const loading = ref(false)
const altchaRef = ref()
const showPassword = ref(false)

// Canvas ref for star field animation
const canvasRef = ref<HTMLCanvasElement | null>(null)

// Initialize star field animation (auto-starts in onMounted)
useStarField(canvasRef)

const form = ref({
  username: '',
  password: '',
  altcha: undefined as string | undefined
})

async function onSubmit() {
  loading.value = true
  try {
    await authStore.login(form.value)
    showToast('登录成功')
    router.push('/')
  } catch (error: unknown) {
    // Handle captcha-related errors
    const axiosError = error as { response?: { status?: number; data?: { detail?: string } } }
    const detail = axiosError.response?.data?.detail || ''
    const status = axiosError.response?.status

    if (status === 503) {
      showToast('验证服务暂时不可用，请稍后重试')
    } else if (detail.includes('验证码')) {
      // Captcha error - reset widget but preserve form data
      altchaRef.value?.reset()
      showToast(detail)
    }
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  flex-direction: column;
  align-items: center;
  padding-top: 15vh;
  position: relative;
  overflow: hidden;
}

/* Cosmic canvas - below content */
.cosmic-canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  z-index: 0;
  pointer-events: none;
}

/* Login content - above canvas */
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

.app-title {
  font-size: 36px;
  font-weight: 700;
  color: #fff;
  margin: 0;
  letter-spacing: 2px;
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
/* Override Vant primary color on login button for WCAG AA contrast */
.form-actions :deep(.van-button--primary) {
  --van-button-primary-background: var(--color-action-primary);
  --van-button-primary-border-color: var(--color-action-primary);
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
</style>