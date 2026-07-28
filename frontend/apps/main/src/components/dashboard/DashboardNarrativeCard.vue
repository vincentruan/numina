<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getNarrative } from '@/api/dashboard'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'

const { t } = useI18n()
const authStore = useAuthStore()

const loading = ref(true)
const narrative = ref<string | null>(null)
const firstSentence = ref('')
const thinking = ref('')
const expanded = ref(false)
const thinkingExpanded = ref(false)
const dismissed = ref(false)

function dismissKey(): string {
  return `narrative_dismissed_${authStore.user?.family_id ?? 'unknown'}`
}

async function load() {
  if (sessionStorage.getItem(dismissKey()) === '1') {
    dismissed.value = true
    loading.value = false
    return
  }

  try {
    const resp = await getNarrative()
    const data = resp.data
    if (data.narrative) {
      narrative.value = data.narrative
      firstSentence.value = data.first_sentence || data.narrative
      thinking.value = data.thinking || ''
    }
  } catch {
    narrative.value = null
  } finally {
    loading.value = false
  }
}

function toggleExpand() {
  expanded.value = !expanded.value
}

function toggleThinking() {
  thinkingExpanded.value = !thinkingExpanded.value
}

function onDismiss() {
  dismissed.value = true
  sessionStorage.setItem(dismissKey(), '1')
}

onMounted(() => {
  load()
})
</script>

<template>
  <!-- Loading: title + spinner -->
  <div
    v-if="loading && !dismissed"
    class="narrative-card narrative-card--loading"
    data-test="narrative-loading"
  >
    <span class="narrative-card__label">
      <van-loading size="14px" type="spinner" color="var(--color-primary, #646cff)" />
      {{ t('dashboard.narrative.title') }}
    </span>
  </div>

  <!-- Narrative card -->
  <div
    v-else-if="narrative && !dismissed"
    class="narrative-card"
    :class="{ 'narrative-card--expanded': expanded }"
    :aria-label="t('dashboard.narrative.ariaLabel')"
    data-test="narrative-card"
  >
    <!-- Header row -->
    <div class="narrative-card__header">
      <span class="narrative-card__label">{{ t('dashboard.narrative.title') }}</span>
      <div class="narrative-card__actions">
        <button class="narrative-card__toggle" @click="toggleExpand">
          <van-icon :name="expanded ? 'arrow-up' : 'arrow-down'" size="12" />
          {{ expanded ? t('dashboard.narrative.collapse') : t('dashboard.narrative.expand') }}
        </button>
        <button class="narrative-card__close" :aria-label="t('common.close')" @click="onDismiss">
          <van-icon name="cross" size="14" />
        </button>
      </div>
    </div>

    <!-- Collapsed preview -->
    <div v-show="!expanded" class="narrative-card__preview">
      <p class="narrative-card__text narrative-card__text--clamp">{{ firstSentence }}</p>
    </div>

    <!-- Expanded content -->
    <div v-show="expanded" class="narrative-card__content">
      <!-- Narrative text -->
      <p class="narrative-card__text">{{ narrative }}</p>

      <!-- Thinking section (only if there is thinking content) -->
      <div v-if="thinking" class="narrative-card__thinking">
        <button class="narrative-card__thinking-toggle" @click="toggleThinking">
          <van-icon :name="thinkingExpanded ? 'arrow-up' : 'arrow-down'" size="10" />
          {{ thinkingExpanded ? t('dashboard.narrative.collapse') : t('dashboard.narrative.expand') }}
          {{ t('dashboard.narrative.thinking', '思考过程') }}
        </button>
        <div
          v-show="thinkingExpanded"
          class="narrative-card__thinking-content"
        >
          <p class="narrative-card__thinking-text">{{ thinking }}</p>
        </div>
        <div
          v-show="!thinkingExpanded"
          class="narrative-card__thinking-preview"
        >
          <p class="narrative-card__thinking-text narrative-card__text--clamp">{{ thinking }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.narrative-card {
  background: var(--card-bg);
  border-radius: 12px;
  margin: 8px 12px;
  padding: 12px 16px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
  transition: all 0.25s ease-in-out;
}

[data-theme='dark'] .narrative-card {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.28);
}

/* Loading state */
.narrative-card--loading {
  min-height: 40px;
  display: flex;
  align-items: center;
}

/* Header row */
.narrative-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 24px;
}

.narrative-card__label {
  font-size: 12px;
  color: var(--color-primary, #646cff);
  font-weight: 500;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

/* Action buttons grouped on the right */
.narrative-card__actions {
  display: flex;
  align-items: center;
  gap: 4px;
}

/* Toggle button */
.narrative-card__toggle {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 12px;
  color: var(--text-secondary, #969799);
  background: none;
  border: none;
  cursor: pointer;
  padding: 4px 6px;
  white-space: nowrap;
  min-height: 28px;
  border-radius: 4px;
}

.narrative-card__toggle:active {
  color: var(--color-primary, #646cff);
  background: rgba(0, 0, 0, 0.04);
}

[data-theme='dark'] .narrative-card__toggle:active {
  background: rgba(255, 255, 255, 0.06);
}

/* Close button */
.narrative-card__close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  color: var(--text-secondary, #969799);
  cursor: pointer;
  border-radius: 50%;
  padding: 0;
  flex-shrink: 0;
}

.narrative-card__close:active {
  background: rgba(0, 0, 0, 0.06);
}

[data-theme='dark'] .narrative-card__close:active {
  background: rgba(255, 255, 255, 0.1);
}

/* Preview (collapsed) */
.narrative-card__preview {
  margin-top: 8px;
}

/* Content (expanded) */
.narrative-card__content {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--van-border-color, #f2f3f5);
}

[data-theme='dark'] .narrative-card__content {
  border-top-color: rgba(255, 255, 255, 0.08);
}

/* Narrative text */
.narrative-card__text {
  font-size: 14px;
  line-height: 1.6;
  color: var(--text-primary, #323233);
  margin: 0;
  word-break: break-word;
  white-space: pre-wrap;
}

/* Clamp to 2 lines */
.narrative-card__text--clamp {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* Thinking section */
.narrative-card__thinking {
  margin-top: 12px;
  padding: 10px 12px;
  background: var(--van-background-2, #f7f8fa);
  border-radius: 8px;
}

[data-theme='dark'] .narrative-card__thinking {
  background: rgba(255, 255, 255, 0.04);
}

.narrative-card__thinking-toggle {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 11px;
  color: var(--text-secondary, #969799);
  background: none;
  border: none;
  cursor: pointer;
  padding: 2px 0;
  white-space: nowrap;
}

.narrative-card__thinking-content {
  margin-top: 6px;
}

.narrative-card__thinking-preview {
  margin-top: 6px;
}

.narrative-card__thinking-text {
  font-size: 12px;
  line-height: 1.5;
  color: var(--text-secondary, #969799);
  margin: 0;
  word-break: break-word;
  white-space: pre-wrap;
}

/* Responsive */
@media (max-width: 428px) {
  .narrative-card {
    margin: 8px 0;
    border-radius: 0;
  }
}
</style>
