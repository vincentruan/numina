<template>
  <div class="join-page">
    <div class="join-header">
      <h1 class="app-title">加入家庭</h1>
      <p class="app-subtitle">使用邀请码加入已有家庭</p>
    </div>

    <van-form @submit="onSubmit" class="join-form">
      <van-cell-group inset>
        <van-field
          v-model="form.invite_code"
          label="邀请码"
          placeholder="请输入家庭邀请码"
          :rules="[{ required: true, message: '请输入邀请码' }]"
        />
        <van-field
          v-model="form.username"
          label="用户名"
          placeholder="请输入用户名"
          :rules="[{ required: true, message: '请输入用户名' }]"
        />
        <van-field
          v-model="form.display_name"
          label="显示名称"
          placeholder="请输入显示名称"
          :rules="[{ required: true, message: '请输入显示名称' }]"
        />
        <van-field
          v-model="form.password"
          type="password"
          label="密码"
          placeholder="请输入密码(至少6位)"
          :rules="[
            { required: true, message: '请输入密码' },
            { validator: (v: string) => v.length >= 6, message: '密码至少6位' }
          ]"
        />
        <van-field
          v-model="confirmPassword"
          type="password"
          label="确认密码"
          placeholder="请再次输入密码"
          :rules="[
            { required: true, message: '请确认密码' },
            { validator: (v: string) => v === form.password, message: '两次密码不一致' }
          ]"
        />
      </van-cell-group>

      <!-- ALTCHA captcha widget -->
      <AltchaWidget v-model="form.altcha" />

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
import { useAuthStore } from '@/stores/auth'
import AltchaWidget from '@/components/common/AltchaWidget.vue'

const router = useRouter()
const authStore = useAuthStore()
const loading = ref(false)
const confirmPassword = ref('')

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
    showToast('加入成功')
    router.push('/')
  } catch {
    // Error handled by interceptor
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.join-page {
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
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
  font-weight: 700;
  color: #fff;
  margin: 0;
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
</style>
