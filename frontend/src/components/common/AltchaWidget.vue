<template>
  <div class="altcha-container">
    <!-- Test mode indicator for development -->
    <div v-if="!isProduction" class="altcha-test-mode">
      <van-notice-bar color="#1989fa" background="#ecf9ff">
        开发模式：验证码已禁用
      </van-notice-bar>
    </div>
    <!-- ALTCHA widget for production - rendered client-side only -->
    <div v-else v-html="widgetHtml" class="altcha-widget-wrapper"></div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'

const props = defineProps<{
  modelValue?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string | undefined]
}>()

const isProduction = import.meta.env.PROD
const isMounted = ref(false)

// Widget HTML template
const widgetHtml = computed(() => {
  if (!isMounted.value) return ''
  return `
    <altcha-widget
      challengeurl="/api/v1/captcha/challenge"
      name="altcha"
      hidelogo
      hidefooter
      strings='{"label":"点击验证","labelVerified":"验证通过","labelVerifying":"验证中...","labelLoading":"加载中...","error":"验证失败，请重试"}'
    ></altcha-widget>
  `
})

onMounted(() => {
  isMounted.value = true

  if (!isProduction) {
    // In development mode, emit undefined to skip captcha
    emit('update:modelValue', undefined)
    return
  }

  // Listen for the altcha change event on the container
  const container = document.querySelector('.altcha-widget-wrapper')
  if (container) {
    container.addEventListener('change', ((event: Event) => {
      const target = event.target as HTMLElement
      if (target.tagName.toLowerCase() === 'altcha-widget') {
        const customEvent = event as CustomEvent
        const payload = customEvent.detail?.payload
        emit('update:modelValue', payload || undefined)
      }
    }) as EventListener)
  }
})

// Expose reset method for parent components
defineExpose({
  reset: () => {
    if (isProduction) {
      const widget = document.querySelector('altcha-widget') as any
      if (widget && widget.reset) {
        widget.reset()
        emit('update:modelValue', undefined)
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
</style>