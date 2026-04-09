<template>
  <div class="altcha-container">
    <!-- Dev mode: silent pass-through -->
    <div v-if="!isProduction" class="altcha-dev-notice">
      <van-notice-bar color="#1989fa" background="#ecf9ff">
        开发模式：验证码已禁用
      </van-notice-bar>
    </div>

    <!-- Production: custom unified UI -->
    <template v-else>
      <!-- Captcha card — matches van-cell-group inset style -->
      <div
        class="captcha-card"
        :class="{
          'captcha-card--verified': state === 'verified',
          'captcha-card--error': state === 'error',
          'captcha-card--verifying': state === 'verifying',
        }"
        role="group"
        aria-label="人机验证"
      >
        <!-- Left: checkbox / progress / checkmark -->
        <div class="captcha-indicator" aria-hidden="true">
          <!-- Idle: plain checkbox -->
          <div v-if="state === 'idle'" class="captcha-checkbox" @click="triggerVerification">
            <div class="checkbox-box"></div>
          </div>

          <!-- Verifying: green circular progress ring -->
          <div v-else-if="state === 'verifying'" class="captcha-progress">
            <svg viewBox="0 0 36 36" class="progress-ring" aria-hidden="true">
              <!-- Track -->
              <circle
                class="progress-ring__track"
                cx="18" cy="18" r="15"
                fill="none"
                stroke-width="3"
              />
              <!-- Animated arc -->
              <circle
                class="progress-ring__arc"
                cx="18" cy="18" r="15"
                fill="none"
                stroke-width="3"
                stroke-linecap="round"
              />
            </svg>
          </div>

          <!-- Verified: green checkmark -->
          <div v-else-if="state === 'verified'" class="captcha-check">
            <svg viewBox="0 0 24 24" class="check-icon" aria-hidden="true">
              <circle cx="12" cy="12" r="11" class="check-circle" />
              <polyline points="6,12 10,16 18,8" class="check-mark" />
            </svg>
          </div>

          <!-- Error: red X -->
          <div v-else-if="state === 'error'" class="captcha-error-icon" @click="triggerVerification">
            <svg viewBox="0 0 24 24" class="error-icon" aria-hidden="true">
              <circle cx="12" cy="12" r="11" class="error-circle" />
              <line x1="8" y1="8" x2="16" y2="16" class="error-line" />
              <line x1="16" y1="8" x2="8" y2="16" class="error-line" />
            </svg>
          </div>
        </div>

        <!-- Right: label text -->
        <div class="captcha-label">
          <span v-if="state === 'idle'" class="captcha-label__text" @click="triggerVerification">点击验证</span>
          <span v-else-if="state === 'verifying'" class="captcha-label__text captcha-label__text--muted">验证中...</span>
          <span v-else-if="state === 'verified'" class="captcha-label__text captcha-label__text--success">验证通过</span>
          <span v-else-if="state === 'error'" class="captcha-label__text captcha-label__text--error">验证失败，点击重试</span>
        </div>

        <!-- Altcha branding (minimal) -->
        <div class="captcha-brand" aria-hidden="true">
          <span class="captcha-brand__text">ALTCHA</span>
        </div>
      </div>

      <!-- Error detail below card -->
      <div v-if="errorMessage" role="alert" class="captcha-error-msg">
        {{ errorMessage }}
      </div>

      <!-- Hidden altcha-widget for challenge/payload — never visible -->
      <div class="altcha-hidden" aria-hidden="true" v-html="widgetHtml"></div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, nextTick } from 'vue'

const props = defineProps<{
  modelValue?: string
  endpoint?: 'login' | 'register' | 'join-family'
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string | undefined]
}>()

const isProduction = import.meta.env.PROD
const isMounted = ref(false)
const errorMessage = ref('')

type CaptchaState = 'idle' | 'verifying' | 'verified' | 'error'
const state = ref<CaptchaState>('idle')

const widgetHtml = computed(() => {
  if (!isMounted.value) return ''
  const endpointParam = props.endpoint ? `?endpoint=${props.endpoint}` : ''
  return `
    <altcha-widget
      challengeurl="/api/v1/captcha/challenge${endpointParam}"
      name="altcha"
      hidelogo
      hidefooter
      auto="onload"
      strings='{"label":"点击验证","labelVerified":"验证通过","labelVerifying":"验证中...","labelLoading":"加载中...","error":"验证失败，请重试"}'
    ></altcha-widget>
  `
})

function triggerVerification() {
  if (state.value !== 'idle' && state.value !== 'error') return
  // The hidden altcha-widget handles the actual challenge automatically (auto="onload")
  // For manual trigger on click, we reset and let it re-run
  const widget = document.querySelector('altcha-widget') as any
  if (widget) {
    if (widget.reset) widget.reset()
    // Trigger the widget's internal verification
    if (widget.verify) widget.verify()
  }
  state.value = 'verifying'
  errorMessage.value = ''
}

const setupWidgetListeners = () => {
  const widget = document.querySelector('altcha-widget')
  if (!widget) {
    setTimeout(setupWidgetListeners, 100)
    return
  }

  widget.addEventListener('statechange', ((event: Event) => {
    const customEvent = event as CustomEvent
    const s = customEvent.detail?.state?.toString().toUpperCase()

    if (s === 'VERIFYING') {
      state.value = 'verifying'
      errorMessage.value = ''
    } else if (s === 'VERIFIED') {
      state.value = 'verified'
      errorMessage.value = ''
      setTimeout(() => {
        const hiddenInput = document.querySelector('input[name="altcha"]') as HTMLInputElement
        if (hiddenInput?.value) {
          emit('update:modelValue', hiddenInput.value)
        }
      }, 50)
    } else if (s === 'ERROR' || s === 'EXPIRED') {
      state.value = 'error'
      errorMessage.value = s === 'EXPIRED' ? '验证码已过期，请重新验证' : '验证失败，请重试'
    } else if (s === 'UNVERIFIED') {
      state.value = 'idle'
    }
  }) as EventListener)
}

onMounted(async () => {
  isMounted.value = true
  if (!isProduction) {
    emit('update:modelValue', undefined)
    return
  }
  await nextTick()
  setTimeout(setupWidgetListeners, 50)
})

defineExpose({
  reset: () => {
    if (isProduction) {
      const widget = document.querySelector('altcha-widget') as any
      if (widget?.reset) widget.reset()
      emit('update:modelValue', undefined)
      state.value = 'idle'
      errorMessage.value = ''
    }
  },
})
</script>

<style scoped>
.altcha-container {
  width: 100%;
}

.altcha-dev-notice {
  margin: 16px 0;
}

/* ── Hidden altcha widget ── */
.altcha-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  opacity: 0;
  pointer-events: none;
}

/* ── Captcha card — mirrors van-cell-group inset ── */
.captcha-card {
  display: flex;
  align-items: center;
  margin: 12px 16px;
  padding: 0 16px;
  height: 52px;
  background: var(--card-bg);
  border-radius: 8px;
  box-shadow: 0 0 0 1px var(--separator);
  cursor: pointer;
  user-select: none;
  transition: box-shadow 0.2s ease;
}

.captcha-card:active {
  box-shadow: 0 0 0 1px rgba(0, 0, 0, 0.12);
}

.captcha-card--verified {
  cursor: default;
  box-shadow: 0 0 0 1.5px #07c160;
}

.captcha-card--error {
  box-shadow: 0 0 0 1.5px #ee0a24;
}

.captcha-card--verifying {
  cursor: default;
}

/* ── Indicator area (left 36px) ── */
.captcha-indicator {
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 12px;
}

/* Idle checkbox */
.captcha-checkbox {
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.checkbox-box {
  width: 18px;
  height: 18px;
  border: 1.5px solid var(--separator);
  border-radius: 3px;
  background: var(--card-bg);
  transition: border-color 0.2s;
}

.captcha-card:hover .checkbox-box {
  border-color: #969799;
}

/* Circular progress ring */
.captcha-progress {
  width: 28px;
  height: 28px;
}

.progress-ring {
  width: 28px;
  height: 28px;
  transform: rotate(-90deg);
}

.progress-ring__track {
  stroke: var(--separator);
}

.progress-ring__arc {
  stroke: #07c160;
  /* circumference of r=15 circle ≈ 94.25 */
  stroke-dasharray: 94.25;
  stroke-dashoffset: 94.25;
  animation: ring-spin 1.2s ease-in-out infinite;
}

@keyframes ring-spin {
  0%   { stroke-dashoffset: 94.25; opacity: 1; }
  60%  { stroke-dashoffset: 10;    opacity: 1; }
  80%  { stroke-dashoffset: 10;    opacity: 0.6; }
  100% { stroke-dashoffset: 94.25; opacity: 1; }
}

/* Verified checkmark */
.captcha-check {
  width: 28px;
  height: 28px;
}

.check-icon {
  width: 28px;
  height: 28px;
}

.check-circle {
  fill: #07c160;
  stroke: none;
}

.check-mark {
  fill: none;
  stroke: #fff;
  stroke-width: 2;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-dasharray: 20;
  stroke-dashoffset: 20;
  animation: draw-check 0.35s ease-out 0.05s forwards;
}

@keyframes draw-check {
  to { stroke-dashoffset: 0; }
}

/* Error icon */
.captcha-error-icon {
  width: 28px;
  height: 28px;
}

.error-icon {
  width: 28px;
  height: 28px;
}

.error-circle {
  fill: #ee0a24;
  stroke: none;
}

.error-line {
  stroke: #fff;
  stroke-width: 2;
  stroke-linecap: round;
}

/* ── Label ── */
.captcha-label {
  flex: 1;
  min-width: 0;
}

.captcha-label__text {
  font-size: 14px;
  color: var(--text-primary);
  line-height: 1;
}

.captcha-label__text--muted {
  color: #969799;
}

.captcha-label__text--success {
  color: #07c160;
  font-weight: 500;
}

.captcha-label__text--error {
  color: #ee0a24;
}

/* ── Brand ── */
.captcha-brand {
  flex-shrink: 0;
  margin-left: 8px;
}

.captcha-brand__text {
  font-size: 10px;
  color: var(--text-tertiary);
  letter-spacing: 0.5px;
  font-weight: 500;
}

/* ── Error message below card ── */
.captcha-error-msg {
  margin: 0 16px 8px;
  font-size: 12px;
  color: #ee0a24;
  line-height: 1.4;
}

/* ── Reduced motion ── */
@media (prefers-reduced-motion: reduce) {
  .progress-ring__arc {
    animation: none;
    stroke-dashoffset: 30;
  }
  .check-mark {
    animation: none;
    stroke-dashoffset: 0;
  }
}
</style>
