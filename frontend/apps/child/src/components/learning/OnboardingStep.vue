<template>
  <div class="onboarding-step">
    <div
      v-for="i in total"
      :key="i"
      class="step-dot"
      :class="{ 'step-dot--active': i === step, 'step-dot--done': i < step }"
    >
      <span v-if="i < step" class="step-dot__check">✓</span>
    </div>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'OnboardingStep' })

defineProps<{
  step: number
  total: number
}>()
</script>

<style scoped>
.onboarding-step {
  display: flex;
  justify-content: center;
  gap: 8px;
  padding: 16px 0;
}

.step-dot {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--color-hairline);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s;
}

.step-dot--active {
  background: var(--color-primary);
}

.step-dot--done {
  background: var(--color-brand-ochre);
}

.step-dot__check {
  font-size: 12px;
  font-weight: 700;
  color: var(--color-canvas);
}
</style>
