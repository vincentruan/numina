<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import WelcomeExamples from '@/components/ai-chat/WelcomeExamples.vue'

const { t } = useI18n()

const emit = defineEmits<{
  startChat: [text: string]
}>()

function handleSuggestionClick(text: string) {
  emit('startChat', text)
}
</script>

<template>
  <div class="welcome-page">
    <div class="welcome-hero">
      <div class="welcome-icon">
        <svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M12 2L2 7l10 5 10-5-10-5z" />
          <path d="M2 17l10 5 10-5" />
          <path d="M2 12l10 5 10-5" />
        </svg>
      </div>
      <h1 class="welcome-title">{{ t('aiChat.welcomeTitle') }}</h1>
      <p class="welcome-subtitle">{{ t('aiChat.welcomeSubtitle') }}</p>
    </div>
    <div class="welcome-examples">
      <WelcomeExamples
        agent-id="numina"
        @select="handleSuggestionClick"
      />
    </div>
  </div>
</template>

<style scoped>
.welcome-page {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 100%;
  padding: 48px 16px;
  gap: 32px;
}

.welcome-hero {
  text-align: center;
}

.welcome-icon {
  color: var(--van-primary-color, #1989fa);
  margin-bottom: 16px;
}

.welcome-title {
  font-size: 24px;
  font-weight: 600;
  color: var(--van-text-color, #333);
  margin: 0 0 8px;
}

.welcome-subtitle {
  font-size: 14px;
  color: var(--van-text-color-2, #666);
  margin: 0;
}

.welcome-examples {
  width: 100%;
  max-width: 400px;
}
</style>
