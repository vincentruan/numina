<script setup lang="ts">
/**
 * SocraticSteps — visual indicator of the Socratic guidance phase.
 *
 * Shows the current phase in the guidance state machine and the
 * child's progress through the tutoring session.
 */
import { computed } from 'vue'
import type { TutorPhase } from '@/composables/useSmartTutor'

interface Props {
  currentPhase: TutorPhase
  stepCount: number
  maxSteps?: number
}

const props = withDefaults(defineProps<Props>(), {
  maxSteps: 5,
})

const phases: { key: TutorPhase; label: string; icon: string }[] = [
  { key: 'diagnose', label: '诊断', icon: '🔍' },
  { key: 'focused_guidance', label: '引导', icon: '💡' },
  { key: 'verify', label: '验证', icon: '✅' },
  { key: 'consolidate', label: '巩固', icon: '🏆' },
]

const currentIndex = computed(() => {
  const phaseOrder: TutorPhase[] = [
    'diagnose',
    'focused_guidance',
    'prerequisite_retrace',
    'misconception_correction',
    'verify',
    'consolidate',
    'end',
  ]
  const idx = phaseOrder.indexOf(props.currentPhase)
  if (props.currentPhase === 'prerequisite_retrace' || props.currentPhase === 'misconception_correction') {
    return 1 // show as part of guidance phase
  }
  if (props.currentPhase === 'end') return 3
  return Math.min(idx, 3)
})
</script>

<template>
  <div class="socratic-steps">
    <div class="socratic-steps__track">
      <div
        v-for="(phase, idx) in phases"
        :key="phase.key"
        class="socratic-steps__step"
        :class="{
          'socratic-steps__step--active': idx === currentIndex,
          'socratic-steps__step--done': idx < currentIndex,
        }"
      >
        <div class="socratic-steps__icon">
          <span v-if="idx < currentIndex">✓</span>
          <span v-else>{{ phase.icon }}</span>
        </div>
        <span class="socratic-steps__label">{{ phase.label }}</span>
      </div>
      <div class="socratic-steps__line">
        <div
          class="socratic-steps__progress"
          :style="{ width: `${(currentIndex / (phases.length - 1)) * 100}%` }"
        />
      </div>
    </div>
    <div class="socratic-steps__counter">
      第 {{ stepCount }} / {{ maxSteps }} 步
    </div>
  </div>
</template>

<style scoped>
.socratic-steps {
  padding: 12px 16px;
  background: var(--color-surface-card, #fff);
  border-radius: 12px;
}

.socratic-steps__track {
  display: flex;
  justify-content: space-between;
  position: relative;
  padding-bottom: 8px;
}

.socratic-steps__step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  z-index: 1;
  transition: transform 0.2s;
}

.socratic-steps__step--active {
  transform: scale(1.1);
}

.socratic-steps__icon {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-canvas, #f5f5f5);
  font-size: 16px;
  transition: background 0.3s;
}

.socratic-steps__step--active .socratic-steps__icon {
  background: var(--color-primary, #0a0a0a);
  color: var(--color-canvas, #fff);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
}

.socratic-steps__step--done .socratic-steps__icon {
  background: #4AD97A;
  color: #fff;
}

.socratic-steps__label {
  font-size: 11px;
  color: var(--color-body, #666);
}

.socratic-steps__step--active .socratic-steps__label {
  color: var(--color-ink, #0a0a0a);
  font-weight: 600;
}

.socratic-steps__line {
  position: absolute;
  top: 16px;
  left: 24px;
  right: 24px;
  height: 3px;
  background: var(--color-canvas, #e0e0e0);
  border-radius: 2px;
  z-index: 0;
}

.socratic-steps__progress {
  height: 100%;
  background: var(--color-primary, #0a0a0a);
  border-radius: 2px;
  transition: width 0.4s ease;
}

.socratic-steps__counter {
  text-align: center;
  font-size: 12px;
  color: var(--color-body, #999);
  margin-top: 4px;
}
</style>
