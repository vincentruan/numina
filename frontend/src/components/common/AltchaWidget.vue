<template>
  <div
    class="altcha-container"
    :aria-busy="isComputing"
    aria-live="polite"
  >
    <!-- Test mode indicator for development -->
    <div v-if="!isProduction" class="altcha-test-mode">
      <van-notice-bar color="#1989fa" background="#ecf9ff">
        开发模式：验证码已禁用
      </van-notice-bar>
    </div>
    <!-- ALTCHA widget for production -->
    <template v-else>
      <!-- Loading/computing indicator -->
      <div v-if="isComputing" class="altcha-loading">
        <van-loading size="24px">
          正在验证...
        </van-loading>
      </div>
      <!-- Success indicator (brief) -->
      <div v-else-if="showSuccess" class="altcha-success">
        <van-icon name="success" color="#07c160" size="24px" />
        <span class="sr-only">验证成功</span>
      </div>
      <!-- Error message -->
      <div v-if="errorMessage" role="alert" class="altcha-error">
        {{ errorMessage }}
      </div>
      <!-- Widget rendered client-side only -->
      <div v-html="widgetHtml" class="altcha-widget-wrapper"></div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, watch, nextTick } from 'vue'

const props = defineProps<{
  modelValue?: string
  endpoint?: 'login' | 'register' | 'join-family'
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string | undefined]
}>()

const isProduction = import.meta.env.PROD
const isMounted = ref(false)
const isComputing = ref(false)
const showSuccess = ref(false)
const errorMessage = ref('')

// Widget state for accessibility announcements
const stateAnnouncement = computed(() => {
  if (isComputing.value) return '正在计算验证'
  if (showSuccess.value) return '验证成功'
  if (errorMessage.value) return '验证失败'
  return ''
})

// Widget HTML template with endpoint parameter
const widgetHtml = computed(() => {
  if (!isMounted.value) return ''
  const endpointParam = props.endpoint ? `?endpoint=${props.endpoint}` : ''
  return `
    <altcha-widget
      challengeurl="/api/v1/captcha/challenge${endpointParam}"
      name="altcha"
      hidelogo
      hidefooter
      strings='{"label":"点击验证","labelVerified":"验证通过","labelVerifying":"验证中...","labelLoading":"加载中...","error":"验证失败，请重试"}'
    ></altcha-widget>
  `
})

onMounted(async () => {
  isMounted.value = true

  if (!isProduction) {
    // In development mode, emit undefined to skip captcha
    emit('update:modelValue', undefined)
    return
  }

  // Wait for v-html DOM to be updated (widgetHtml computed depends on isMounted)
  await nextTick()

  // ALTCHA widget emits custom events that may not bubble properly
  // We need to listen directly on the widget element
  const setupWidgetListeners = () => {
    const widget = document.querySelector('altcha-widget')
    if (!widget) {
      // Widget not ready yet, retry after a short delay
      setTimeout(setupWidgetListeners, 100)
      return
    }

    // ALTCHA stores payload in a hidden input element
    // Read from hidden input when state changes to VERIFIED
    widget.addEventListener('statechange', ((event: Event) => {
      const customEvent = event as CustomEvent
      const state = customEvent.detail?.state?.toString().toUpperCase()

      // ALTCHA State enum values: UNVERIFIED, VERIFYING, VERIFIED, ERROR, EXPIRED, CODE
      if (state === 'VERIFYING') {
        isComputing.value = true
        errorMessage.value = ''
        showSuccess.value = false
      } else if (state === 'VERIFIED') {
        isComputing.value = false
        showSuccess.value = true
        errorMessage.value = ''

        // Read payload from hidden input created by ALTCHA
        // Need to wait for DOM to update - ALTCHA sets the hidden input after firing the event
        setTimeout(() => {
          const hiddenInput = document.querySelector('input[name="altcha"]') as HTMLInputElement
          if (hiddenInput?.value) {
            emit('update:modelValue', hiddenInput.value)
          }
        }, 50)

        // Brief success indicator (500ms)
        setTimeout(() => {
          showSuccess.value = false
        }, 500)
      } else if (state === 'ERROR' || state === 'EXPIRED') {
        isComputing.value = false
        showSuccess.value = false
        errorMessage.value = state === 'EXPIRED' ? '验证码已过期，请重新验证' : '验证失败，请重试'
      } else {
        isComputing.value = false
        showSuccess.value = false
      }
    }) as EventListener)
  }

  // Start setup after a small delay to ensure widget is rendered
  setTimeout(setupWidgetListeners, 50)
})

// Expose reset method for parent components
defineExpose({
  reset: () => {
    if (isProduction) {
      const widget = document.querySelector('altcha-widget') as any
      if (widget && widget.reset) {
        widget.reset()
        emit('update:modelValue', undefined)
        errorMessage.value = ''
        showSuccess.value = false
        isComputing.value = false
      }
    }
  },
})
</script>

<style scoped>
.altcha-container {
  width: 100%;
}

.altcha-test-mode {
  margin: 16px 0;
}

.altcha-widget-wrapper {
  display: flex;
  justify-content: center;
  margin: 16px 0;
}

.altcha-widget-wrapper :deep(altcha-widget) {
  width: 100%;
  max-width: 300px;
}

.altcha-loading {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 16px 0;
}

.altcha-success {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 16px 0;
}

.altcha-error {
  color: #ee0a24;
  font-size: 14px;
  text-align: center;
  padding: 8px 0;
}

/* Screen reader only class */
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

/* Dark mode support via CSS custom properties */
/* ALTCHA v1.0.1 doesn't have a 'dark' attribute, so we use CSS */
:global([data-theme="dark"]) .altcha-widget-wrapper :deep(altcha-widget) {
  --altcha-color-base: #1a1a1a;
  --altcha-color-text: #f5f5f5;
  --altcha-color-border: #3a3a3a;
  --altcha-color-border-focus: #1989fa;
  --altcha-color-bg: #2a2a2a;
  --altcha-color-bg-hover: #3a3a3a;
  --altcha-color-error: #ee0a24;
  --altcha-color-success: #07c160;
}
</style>