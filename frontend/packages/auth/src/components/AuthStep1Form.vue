<template>
  <form class="auth-step1-form" @submit.prevent="onSubmit">
    <div class="form-field">
      <label class="field-label" for="auth-username">用户名</label>
      <input
        id="auth-username"
        v-model="username"
        class="field-input"
        type="text"
        placeholder="请输入用户名"
        autocomplete="username"
        required
      />
    </div>

    <div class="form-field">
      <label class="field-label" for="auth-password">密码</label>
      <div class="password-wrapper">
        <input
          id="auth-password"
          v-model="password"
          class="field-input"
          :type="showPassword ? 'text' : 'password'"
          placeholder="请输入密码"
          autocomplete="current-password"
          required
        />
        <button
          type="button"
          class="eye-btn"
          :aria-label="showPassword ? '隐藏密码' : '显示密码'"
          @click="showPassword = !showPassword"
        >
          <!-- eye open -->
          <svg v-if="showPassword" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
            <circle cx="12" cy="12" r="3"/>
          </svg>
          <!-- eye closed -->
          <svg v-else width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/>
            <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/>
            <line x1="1" y1="1" x2="23" y2="23"/>
          </svg>
        </button>
      </div>
    </div>

    <!-- Captcha slot — parent injects AltchaWidget when showAltcha is true -->
    <slot v-if="showAltcha" name="captcha" />

    <!-- Error message -->
    <p v-if="error" class="form-error" role="alert">{{ error }}</p>

    <div class="form-actions">
      <button
        type="submit"
        class="submit-btn"
        :disabled="loading"
      >
        <span v-if="loading" class="btn-spinner" aria-hidden="true" />
        <span>下一步</span>
      </button>
    </div>
  </form>
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
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* Field */
.form-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field-label {
  font-size: 14px;
  color: var(--auth-label-color, rgba(255, 255, 255, 0.6));
  padding: 0 4px;
}

.field-input {
  width: 100%;
  box-sizing: border-box;
  padding: 12px 14px;
  background: var(--auth-input-bg, rgba(255, 255, 255, 0.07));
  border: 1px solid var(--auth-input-border, rgba(255, 255, 255, 0.12));
  border-radius: 10px;
  font-size: 15px;
  color: var(--auth-input-color, rgba(255, 255, 255, 0.9));
  outline: none;
  transition: border-color 0.2s;
}

.field-input::placeholder {
  color: var(--auth-placeholder-color, rgba(255, 255, 255, 0.3));
}

.field-input:focus {
  border-color: rgba(99, 102, 241, 0.6);
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.15);
}

/* Password wrapper */
.password-wrapper {
  position: relative;
}

.password-wrapper .field-input {
  padding-right: 44px;
}

.eye-btn {
  position: absolute;
  right: 10px;
  top: 50%;
  transform: translateY(-50%);
  background: none;
  border: none;
  padding: 4px;
  cursor: pointer;
  color: var(--auth-eye-color, rgba(255, 255, 255, 0.4));
  display: flex;
  align-items: center;
  transition: color 0.15s;
}

.eye-btn:hover {
  color: var(--auth-eye-hover-color, rgba(255, 255, 255, 0.7));
}

/* Error */
.form-error {
  margin: 0;
  padding: 0 4px;
  font-size: 13px;
  color: #ee0a24;
  line-height: 1.4;
}

/* Submit button */
.form-actions {
  padding-top: 8px;
}

.submit-btn {
  width: 100%;
  padding: 13px;
  background: linear-gradient(135deg, #6366f1, #7c3aed);
  border: none;
  border-radius: 24px;
  font-size: 16px;
  font-weight: 500;
  color: #fff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  transition: opacity 0.2s, transform 0.15s;
}

.submit-btn:hover:not(:disabled) {
  opacity: 0.9;
}

.submit-btn:active:not(:disabled) {
  transform: scale(0.98);
}

.submit-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 255, 255, 0.4);
  border-top-color: #fff;
  border-radius: 50%;
  animation: btn-spin 0.7s linear infinite;
  flex-shrink: 0;
}

@keyframes btn-spin {
  to { transform: rotate(360deg); }
}

/* Light theme overrides */
:global(.theme-light) .auth-step1-form {
  --auth-label-color: rgba(0, 0, 0, 0.6);
  --auth-input-bg: #fff;
  --auth-input-border: rgba(0, 0, 0, 0.2);
  --auth-input-color: rgba(0, 0, 0, 0.9);
  --auth-placeholder-color: rgba(0, 0, 0, 0.35);
  --auth-eye-color: rgba(0, 0, 0, 0.4);
  --auth-eye-hover-color: rgba(0, 0, 0, 0.7);
}

:global(.theme-light) .form-error {
  color: #c0392b;
}
</style>
