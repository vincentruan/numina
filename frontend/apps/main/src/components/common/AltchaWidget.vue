<template>
  <div class="altcha-container">
    <!-- Captcha disabled (per server config): silent pass-through with subtle dark pill -->
    <div v-if="!captchaEnabled" class="altcha-dev-notice" aria-hidden="true">
      <span class="altcha-dev-pill">{{ t('captcha.disabled') }}</span>
    </div>

    <!-- Captcha enabled: custom unified UI -->
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
          <div v-if="state === 'idle'" class="captcha-checkbox" role="button" tabindex="0" :aria-label="t('captcha.label')" @click="triggerVerification" @keydown.enter="triggerVerification" @keydown.space.prevent="triggerVerification">
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
          <div v-else-if="state === 'error'" class="captcha-error-icon" role="button" tabindex="0" :aria-label="t('captcha.error')" @click="triggerVerification" @keydown.enter="triggerVerification" @keydown.space.prevent="triggerVerification">
            <svg viewBox="0 0 24 24" class="error-icon" aria-hidden="true">
              <circle cx="12" cy="12" r="11" class="error-circle" />
              <line x1="8" y1="8" x2="16" y2="16" class="error-line" />
              <line x1="16" y1="8" x2="8" y2="16" class="error-line" />
            </svg>
          </div>
        </div>

        <!-- Right: label text -->
        <div class="captcha-label">
          <span v-if="state === 'idle'" class="captcha-label__text" role="button" tabindex="0" @click="triggerVerification" @keydown.enter="triggerVerification" @keydown.space.prevent="triggerVerification">{{ t('captcha.label') }}</span>
          <span v-else-if="state === 'verifying'" class="captcha-label__text captcha-label__text--muted">{{ t('captcha.labelVerifying') }}</span>
          <span v-else-if="state === 'verified'" class="captcha-label__text captcha-label__text--success">{{ t('captcha.labelVerified') }}</span>
          <span v-else-if="state === 'error'" class="captcha-label__text captcha-label__text--error">{{ t('captcha.error') }}</span>
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

      <!-- Hidden altcha-widget for challenge/payload — never visible, not keyboard-reachable -->
      <!-- eslint-disable-next-line vue/no-v-html -- widgetHtml is a static template literal, no user input -->
      <div class="altcha-hidden" v-html="widgetHtml"></div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const props = defineProps<{
  modelValue?: string
  endpoint?: 'login' | 'register' | 'join-family'
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string | undefined]
}>()

const isMounted = ref(false)
const captchaEnabled = ref(false)
const errorMessage = ref('')

type CaptchaState = 'idle' | 'verifying' | 'verified' | 'error'
const state = ref<CaptchaState>('idle')

const widgetHtml = computed(() => {
  if (!isMounted.value) return ''
  const endpointParam = props.endpoint ? `?endpoint=${props.endpoint}` : ''
  const strings = JSON.stringify({
    label: t('captcha.label'),
    labelVerified: t('captcha.labelVerified'),
    labelVerifying: t('captcha.labelVerifying'),
    labelLoading: t('captcha.labelLoading'),
    error: t('captcha.error')
  })
  return `
    <altcha-widget
      challengeurl="/api/v1/captcha/challenge${endpointParam}"
      name="altcha"
      hidelogo
      hidefooter
      auto="onload"
      tabindex="-1"
      strings='${strings}'
    ></altcha-widget>
  `
})

function triggerVerification() {
  if (state.value !== 'idle' && state.value !== 'error') return
  // The hidden altcha-widget handles the actual challenge automatically (auto="onload")
  // For manual trigger on click, we reset and let it re-run
  const widget = document.querySelector('altcha-widget') as HTMLElement & { reset?: () => void; verify?: () => void }
  if (widget) {
    if (widget.reset) widget.reset()
    // Trigger the widget's internal verification
    if (widget.verify) widget.verify()
  }
  state.value = 'verifying'
  errorMessage.value = ''
}

const setupWidgetListeners = (retries = 0) => {
  const widget = document.querySelector('altcha-widget')
  if (!widget) {
    if (retries < 30) {
      setTimeout(() => setupWidgetListeners(retries + 1), 100)
    } else {
      // altcha script failed to load — treat as error so user sees feedback
      state.value = 'error'
      errorMessage.value = t('captcha.loadFailed')
    }
    return
  }

  widget.addEventListener('statechange', (event: Event) => {
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
      errorMessage.value = s === 'EXPIRED' ? t('captcha.expired') : t('captcha.error')
    } else if (s === 'UNVERIFIED') {
      state.value = 'idle'
    }
  })
}

onMounted(async () => {
  isMounted.value = true
  try {
    const res = await fetch('/api/v1/captcha/config')
    const data = await res.json()
    // API returns raw {captcha_enabled: bool} (not envelope-wrapped — see captcha router comment)
    captchaEnabled.value = data?.captcha_enabled === true
  } catch {
    captchaEnabled.value = true // fail-safe: assume enabled
  }
  if (!captchaEnabled.value) {
    emit('update:modelValue', undefined)
    return
  }
  await nextTick()
  setTimeout(setupWidgetListeners, 50)
})

defineExpose({
  reset: () => {
    if (captchaEnabled.value) {
      const widget = document.querySelector('altcha-widget') as HTMLElement & { reset?: () => void; verify?: () => void }
      if (widget?.reset) widget.reset()
      emit('update:modelValue', undefined)
      state.value = 'idle'
      errorMessage.value = ''
    }
  },
  isEnabled: () => captchaEnabled.value,
})
</script>

<style scoped>
.altcha-container {
  width: 100%;
}

.altcha-dev-notice {
  margin: 12px 0;
  display: flex;
  justify-content: center;
}

.altcha-dev-pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 12px;
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.02em;
  color: rgba(255, 255, 255, 0.45);
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 100px;
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
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

/* ── Captcha card — dark glass style for login background ── */
.captcha-card {
  display: flex;
  align-items: center;
  margin: 12px 16px;
  padding: 0 16px;
  height: 52px;
  background: rgba(255, 255, 255, 0.08);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-radius: 8px;
  box-shadow: 0 0 0 1px rgba(189, 187, 255, 0.2);
  cursor: pointer;
  user-select: none;
  transition: box-shadow 0.2s ease;
  color: rgba(255, 255, 255, 0.85);
}

.captcha-card:active {
  box-shadow: 0 0 0 1px rgba(189, 187, 255, 0.4);
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
  border: 1.5px solid rgba(189, 187, 255, 0.4);
  border-radius: 3px;
  background: rgba(255, 255, 255, 0.06);
  transition: border-color 0.2s;
}

.captcha-card:hover .checkbox-box {
  border-color: rgba(189, 187, 255, 0.7);
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
  stroke: rgba(189, 187, 255, 0.2);
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
  color: rgba(255, 255, 255, 0.85);
  line-height: 1;
}

.captcha-label__text--muted {
  color: rgba(255, 255, 255, 0.5);
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
  color: rgba(255, 255, 255, 0.35);
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
