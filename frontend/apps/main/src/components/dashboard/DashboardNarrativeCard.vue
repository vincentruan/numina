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
const expanded = ref(false)
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

function onDismiss() {
  dismissed.value = true
  sessionStorage.setItem(dismissKey(), '1')
}

onMounted(() => {
  load()
})
</script>

<template>
  <!-- Loading: title + spinner row (matches collapsed height ~40px) -->
  <div
    v-if="loading && !dismissed"
    class="narrative-card narrative-card--loading"
    data-test="narrative-loading"
  >
    <div class="narrative-card__header">
      <span class="narrative-card__label">
        <van-loading size="14px" type="spinner" color="var(--color-primary, #646cff)" />
        {{ t('dashboard.narrative.title') }}
      </span>
    </div>
  </div>

  <!-- Narrative card -->
  <div
    v-else-if="narrative && !dismissed"
    class="narrative-card"
    :class="{ 'narrative-card--expanded': expanded }"
    :aria-label="t('dashboard.narrative.ariaLabel')"
    data-test="narrative-card"
  >
    <!-- Close button -->
    <button class="narrative-card__close" :aria-label="t('common.close')" @click="onDismiss">
      <van-icon name="cross" size="14" />
    </button>

    <!-- Header row: label + toggle -->
    <div class="narrative-card__header">
      <span class="narrative-card__label">{{ t('dashboard.narrative.title') }}</span>
      <button class="narrative-card__toggle" @click="toggleExpand">
        <van-icon :name="expanded ? 'arrow-up' : 'arrow-down'" size="12" />
        {{ expanded ? t('dashboard.narrative.collapse') : t('dashboard.narrative.expand') }}
      </button>
    </div>

    <!-- Content -->
    <div v-show="expanded" class="narrative-card__content">
      <p class="narrative-card__text">{{ narrative }}</p>
    </div>

    <!-- Collapsed preview: first sentence only -->
    <div v-show="!expanded" class="narrative-card__preview">
      <p class="narrative-card__text narrative-card__text--clamp">{{ firstSentence }}</p>
    </div>
  </div>
</template>

<style scoped>
.narrative-card {
  background: var(--card-bg);
  border-radius: 12px;
  margin: 8px 12px;
  padding: 12px 16px;
  position: relative;
  border-left: 3px solid var(--color-primary, #646cff);
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
  transition: all 0.25s ease-in-out;
}

[data-theme='dark'] .narrative-card {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.28);
}

/* Loading state: same footprint as collapsed header */
.narrative-card--loading {
  min-height: 40px;
  display: flex;
  align-items: center;
}

/* Header row: label on left, toggle on right */
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

/* Close button: top-right corner */
.narrative-card__close {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: transparent;
  color: var(--text-secondary, #969799);
  cursor: pointer;
  border-radius: 50%;
  padding: 0;
}

.narrative-card__close:active {
  background: rgba(0, 0, 0, 0.06);
}

[data-theme='dark'] .narrative-card__close:active {
  background: rgba(255, 255, 255, 0.1);
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
  padding: 4px 0;
  white-space: nowrap;
  flex-shrink: 0;
  min-height: 28px;
}

.narrative-card__toggle:active {
  color: var(--color-primary, #646cff);
}

/* Content area */
.narrative-card__content {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--van-border-color, #f2f3f5);
}

[data-theme='dark'] .narrative-card__content {
  border-top-color: rgba(255, 255, 255, 0.08);
}

/* Narrative text typography */
.narrative-card__text {
  font-size: 14px;
  line-height: 1.6;
  color: var(--text-primary, #323233);
  margin: 0;
  word-break: break-word;
  white-space: pre-wrap;
}

/* Collapsed preview: clamp to 2 lines */
.narrative-card__preview {
  margin-top: 8px;
}

.narrative-card__text--clamp {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* Responsive */
@media (max-width: 428px) {
  .narrative-card {
    margin: 8px 0;
    border-radius: 0;
  }
}

/* Smooth expand/collapse transition */
.narrative-card__content,
.narrative-card__preview {
  transition: opacity 0.2s ease;
}

.narrative-card--expanded .narrative-card__content {
  opacity: 1;
}
</style>
