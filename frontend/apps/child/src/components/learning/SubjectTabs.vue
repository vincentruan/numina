<template>
  <div class="subject-tabs">
    <div class="subject-tabs__scroll">
      <button
        v-for="tab in tabs"
        :key="tab.subject"
        class="subject-tab"
        :class="{ active: tab.subject === modelValue }"
        @click="$emit('update:modelValue', tab.subject)"
      >
        <span class="subject-tab__icon">{{ subjectIcon(tab.subject) }}</span>
        <span class="subject-tab__label">{{ subjectLabel(tab.subject) }}</span>
        <span v-if="tab.count > 0" class="subject-tab__badge">{{ tab.count }}</span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'SubjectTabs' })

import { useI18n } from 'vue-i18n'

export interface SubjectTab {
  subject: string
  count: number
}

defineProps<{
  modelValue: string
  tabs: SubjectTab[]
}>()

defineEmits<{
  'update:modelValue': [value: string]
}>()

const { t } = useI18n()

function subjectLabel(subject: string): string {
  const key = `learning.subject.${subject}`
  const translated = t(key)
  // If i18n returns the key itself, fall back to capitalized subject
  return translated === key ? subject.charAt(0).toUpperCase() + subject.slice(1) : translated
}

function subjectIcon(subject: string): string {
  const icons: Record<string, string> = {
    mathematics: '🔢',
    math: '🔢',
    science: '🔬',
    english: '📖',
    language: '📖',
    history: '🏛️',
    personal_social: '🤝',
    life_skills: '🌱',
    computing: '💻',
    learning_to_learn: '🧠',
    arts: '🎨',
    music: '🎵',
    coding: '💻',
    life: '🌱',
  }
  return icons[subject.toLowerCase()] || '📚'
}
</script>

<style scoped>
.subject-tabs {
  position: sticky;
  top: 0;
  z-index: 10;
  background: var(--color-canvas);
  padding: 8px 0;
}

.subject-tabs__scroll {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding: 0 var(--space-md);
  scrollbar-width: none;
  -webkit-overflow-scrolling: touch;
}

.subject-tabs__scroll::-webkit-scrollbar {
  display: none;
}

.subject-tab {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border: 1px solid var(--color-hairline);
  border-radius: var(--radius-pill);
  background: var(--color-surface-card);
  font-family: Inter, sans-serif;
  font-size: 14px;
  font-weight: 500;
  color: var(--color-body);
  white-space: nowrap;
  cursor: pointer;
  transition: all 0.15s;
  min-height: 36px;
}

.subject-tab:active {
  transform: scale(0.96);
}

.subject-tab.active {
  background: var(--color-primary);
  color: var(--color-on-dark);
  border-color: var(--color-primary);
}

.subject-tab__icon {
  font-size: 16px;
  line-height: 1;
}

.subject-tab__label {
  line-height: 1;
}

.subject-tab__badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 20px;
  height: 20px;
  padding: 0 6px;
  border-radius: 10px;
  background: var(--color-brand-ochre);
  color: var(--color-ink);
  font-size: 12px;
  font-weight: 600;
  line-height: 1;
}

.subject-tab.active .subject-tab__badge {
  background: var(--color-surface-card);
  color: var(--color-ink);
}
</style>
