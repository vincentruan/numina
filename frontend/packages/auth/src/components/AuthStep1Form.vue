<template>
  <van-form class="auth-step1-form" @submit="onSubmit">
    <van-cell-group inset>
      <van-field
        v-model="username"
        name="username"
        label="用户名"
        placeholder="请输入用户名"
        type="text"
        autocomplete="username"
        :rules="[{ required: true, message: '请输入用户名' }]"
      />
      <div class="password-field-wrapper">
        <van-field
          v-model="password"
          :type="showPassword ? 'text' : 'password'"
          name="password"
          label="密码"
          placeholder="请输入密码"
          autocomplete="current-password"
          :rules="[{ required: true, message: '请输入密码' }]"
        >
          <template #right-icon>
            <van-icon
              :name="showPassword ? 'eye-o' : 'closed-eye'"
              @click="showPassword = !showPassword"
            />
          </template>
        </van-field>
      </div>
    </van-cell-group>

    <!-- Captcha slot — parent injects AltchaWidget when showAltcha is true -->
    <slot v-if="showAltcha" name="captcha" />

    <!-- Error message -->
    <p v-if="error" class="form-error" role="alert">{{ error }}</p>

    <div class="form-actions">
      <van-button
        round
        block
        type="primary"
        native-type="submit"
        :loading="loading"
        :disabled="loading"
      >
        下一步
      </van-button>
    </div>
  </van-form>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const props = defineProps<{
  showAltcha: boolean
  loading: boolean
  error?: string
  altchaToken?: string
}>()

const emit = defineEmits<{
  (e: 'submit', username: string, password: string, altchaToken?: string): void
}>()

const username = ref('')
const password = ref('')
const showPassword = ref(false)

function onSubmit() {
  emit('submit', username.value, password.value, props.altchaToken)
}
</script>

<style scoped>
.auth-step1-form {
  width: 100%;
  max-width: 400px;
}

.password-field-wrapper :deep(.van-field__right-icon) {
  cursor: pointer;
  color: var(--van-field-right-icon-color);
}

.form-error {
  margin: 8px 16px 0;
  font-size: 13px;
  color: #ee0a24;
  line-height: 1.4;
}

.form-actions {
  padding: 24px 16px 0;
}

.form-actions :deep(.van-button--primary) {
  --van-button-primary-background: var(--color-action-primary);
  --van-button-primary-border-color: var(--color-action-primary);
}

/* Light theme overrides */
:global(.theme-light .auth-step1-form) .form-error {
  color: #c0392b;
}
</style>
