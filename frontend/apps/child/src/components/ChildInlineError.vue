<template>
  <Transition name="inline-error-slide">
    <div
      v-if="visible"
      class="child-inline-error"
      role="alert"
      aria-live="polite"
    >
      <span class="child-inline-error__icon" aria-hidden="true">!</span>
      <span class="child-inline-error__text">{{ message }}</span>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { watch, onBeforeUnmount } from 'vue'

const props = withDefaults(defineProps<{
  message: string
  visible: boolean
}>(), {
  message: '',
})

const emit = defineEmits<{
  'update:visible': [value: boolean]
}>()

let dismissTimer: ReturnType<typeof setTimeout> | null = null

watch(() => props.visible, (val) => {
  if (dismissTimer) {
    clearTimeout(dismissTimer)
    dismissTimer = null
  }
  if (val) {
    dismissTimer = setTimeout(() => {
      emit('update:visible', false)
      dismissTimer = null
    }, 3000)
  }
})

onBeforeUnmount(() => {
  if (dismissTimer) {
    clearTimeout(dismissTimer)
    dismissTimer = null
  }
})
</script>

<style scoped>
.child-inline-error {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  margin: 8px 16px;
  background: var(--color-surface-soft);
  border: 1px solid var(--color-muted-soft);
  border-radius: var(--radius-md, 12px);
  color: var(--color-ink);
  font-size: 14px;
  line-height: 1.4;
}

.child-inline-error__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  flex-shrink: 0;
  border-radius: 50%;
  background: var(--color-brand-peach);
  color: var(--color-ink);
  font-size: 13px;
  font-weight: 700;
}

.child-inline-error__text {
  flex: 1;
}

/* Slide transition */
.inline-error-slide-enter-active,
.inline-error-slide-leave-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}

.inline-error-slide-enter-from,
.inline-error-slide-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

/* Respect prefers-reduced-motion */
@media (prefers-reduced-motion: reduce) {
  .inline-error-slide-enter-active,
  .inline-error-slide-leave-active {
    transition: opacity 0.15s ease;
  }

  .inline-error-slide-enter-from,
  .inline-error-slide-leave-to {
    opacity: 0;
    transform: none;
  }
}
</style>
