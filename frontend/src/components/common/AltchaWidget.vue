<template>
  <div class="altcha-container">
    <!-- Test mode indicator for development -->
    <div v-if="!isProduction" class="altcha-test-mode">
      <van-notice-bar color="#1989fa" background="#ecf9ff">
        开发模式：验证码已禁用
      </van-notice-bar>
    </div>
    <!-- ALTCHA widget for production -->
    <div v-else ref="widgetContainer" class="altcha-widget-wrapper">
      <altcha-widget
        ref="altchaRef"
        :challengeurl="challengeUrl"
        :strings="stringsJson"
        name="altcha"
        hidelogo
        hidefooter
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'

const props = defineProps<{
  modelValue?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string | undefined]
}>()

const altchaRef = ref<HTMLElement | null>(null)
const widgetContainer = ref<HTMLElement | null>(null)
const isProduction = import.meta.env.PROD

const challengeUrl = '/api/v1/captcha/challenge'

// Chinese localization strings
const stringsJson = JSON.stringify({
  label: '点击验证',
  labelVerified: '验证通过',
  labelVerifying: '验证中...',
  labelLoading: '加载中...',
  error: '验证失败，请重试',
})

// Watch for altcha-widget change event
onMounted(() => {
  if (!isProduction) {
    // In development mode, emit undefined to skip captcha
    emit('update:modelValue', undefined)
    return
  }

  // Wait for the widget to be available
  setTimeout(() => {
    const widget = altchaRef.value
    if (widget) {
      widget.addEventListener('change', ((event: Event) => {
        const customEvent = event as CustomEvent
        const payload = customEvent.detail?.payload
        if (payload) {
          emit('update:modelValue', payload)
        } else {
          emit('update:modelValue', undefined)
        }
      }) as EventListener)
    }
  }, 100)
})

// Expose reset method for parent components
defineExpose({
  reset: () => {
    if (altchaRef.value && 'reset' in altchaRef.value) {
      ;(altchaRef.value as any).reset()
      emit('update:modelValue', undefined)
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
</style>