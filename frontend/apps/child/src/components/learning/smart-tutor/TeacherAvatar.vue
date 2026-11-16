<script setup lang="ts">
/**
 * TeacherAvatar — visual teacher persona indicator.
 *
 * Displays an animated avatar representing the current teacher persona
 * based on subject × age_group. Shows emotion feedback (thinking, encouraging,
 * celebrating) based on the current tutoring phase.
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

interface Props {
  subject: string
  ageGroup: string
  phase: string
  isStreaming?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  isStreaming: false,
})

const { t } = useI18n()

// Subject-based color and icon mapping
const subjectConfig = computed(() => {
  const configs: Record<string, { color: string; emoji: string; labelKey: string }> = {
    mathematics: { color: '#4A90D9', emoji: '🧮', labelKey: 'learning.smart_tutor.teacher_math' },
    chinese: { color: '#D94A6B', emoji: '📖', labelKey: 'learning.smart_tutor.teacher_chinese' },
    english: { color: '#4AD97A', emoji: '🌍', labelKey: 'learning.smart_tutor.teacher_english' },
    science: { color: '#D9A34A', emoji: '🔬', labelKey: 'learning.smart_tutor.teacher_science' },
  }
  return configs[props.subject] ?? configs.mathematics!
})

// Age-based style modifiers
const ageModifier = computed(() => {
  const modifiers: Record<string, string> = {
    low: 'avatar--playful',
    mid: 'avatar--friendly',
    high: 'avatar--academic',
  }
  return modifiers[props.ageGroup] ?? 'avatar--friendly'
})

// Phase-based emotion
const emotion = computed(() => {
  if (props.isStreaming) return 'thinking'
  const emotions: Record<string, string> = {
    diagnose: 'curious',
    focused_guidance: 'encouraging',
    prerequisite_retrace: 'thoughtful',
    misconception_correction: 'gentle',
    verify: 'expectant',
    consolidate: 'celebrating',
    end: 'celebrating',
  }
  return emotions[props.phase] ?? 'neutral'
})

const emotionEmoji = computed(() => {
  const map: Record<string, string> = {
    thinking: '🤔',
    curious: '🧐',
    encouraging: '😊',
    thoughtful: '💭',
    gentle: '🤗',
    expectant: '👀',
    celebrating: '🎉',
    neutral: '😄',
  }
  return map[emotion.value] ?? '😄'
})
</script>

<template>
  <div class="teacher-avatar" :class="[ageModifier]">
    <div class="teacher-avatar__circle" :style="{ backgroundColor: subjectConfig.color }">
      <span class="teacher-avatar__emoji">{{ subjectConfig.emoji }}</span>
    </div>
    <div class="teacher-avatar__bubble" aria-live="polite">
      <span class="teacher-avatar__emotion">{{ emotionEmoji }}</span>
    </div>
    <div class="teacher-avatar__label">{{ t(subjectConfig.labelKey) }}</div>
    <div v-if="isStreaming" class="teacher-avatar__pulse" />
  </div>
</template>

<style scoped>
.teacher-avatar {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.teacher-avatar__circle {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  transition: transform 0.3s ease;
}

.avatar--playful .teacher-avatar__circle {
  border-radius: 30% 70% 70% 30% / 30% 30% 70% 70%;
  animation: wobble 3s ease-in-out infinite;
}

.avatar--friendly .teacher-avatar__circle {
  border-radius: 50%;
}

.avatar--academic .teacher-avatar__circle {
  border-radius: 12px;
}

.teacher-avatar__emoji {
  font-size: 24px;
}

.teacher-avatar__bubble {
  position: absolute;
  top: -4px;
  right: -4px;
  width: 24px;
  height: 24px;
  background: var(--color-surface-card, #fff);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.12);
  font-size: 14px;
}

.teacher-avatar__label {
  font-size: 11px;
  color: var(--color-body, #666);
  white-space: nowrap;
}

.teacher-avatar__pulse {
  position: absolute;
  top: 0;
  left: 50%;
  transform: translateX(-50%);
  width: 48px;
  height: 48px;
  border-radius: 50%;
  border: 2px solid currentColor;
  opacity: 0;
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes wobble {
  0%, 100% { transform: rotate(-3deg); }
  50% { transform: rotate(3deg); }
}

@keyframes pulse {
  0% { transform: translateX(-50%) scale(1); opacity: 0.6; }
  100% { transform: translateX(-50%) scale(1.4); opacity: 0; }
}
</style>
