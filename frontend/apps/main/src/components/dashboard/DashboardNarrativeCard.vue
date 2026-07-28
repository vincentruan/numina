<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getNarrative } from '@/api/dashboard'
import type { NarrativeResponse } from '@/api/dashboard'
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
  // Check sessionStorage for dismiss state (R15) — scoped per family (P1 fix)
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
    // Silent degradation (R2/F3): hide card on failure
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
  // Independent async load — does not block the page (KTD4)
  load()
})
</script>

<template>
  <!-- Skeleton while loading (R12/R16) -->
  <div v-if="loading && !dismissed" class="narrative-card narrative-card--skeleton" data-test="narrative-skeleton">
    <div class="narrative-card__inner">
      <van-skeleton :row="1" row-width="80%" animate />
    </div>
  </div>

  <!-- Narrative card (R1/R8/R9/R13) -->
  <div
    v-else-if="narrative && !dismissed"
    class="narrative-card"
    :class="{ 'narrative-card--expanded': expanded }"
    :aria-label="t('dashboard.narrative.ariaLabel')"
    data-test="narrative-card"
  >
    <!-- Close button (R15) -->
    <button class="narrative-card__close" :aria-label="t('common.close')" @click="onDismiss">
      <van-icon name="cross" size="14" />
    </button>

    <div class="narrative-card__inner">
      <!-- Label (R9) -->
      <div class="narrative-card__label">{{ t('dashboard.narrative.title') }}</div>

      <!-- Text content (R1/R13) -->
      <div class="narrative-card__body">
        <div v-if="expanded" class="narrative-card__text">{{ narrative }}</div>
        <div v-else class="narrative-card__text narrative-card__text--collapsed">
          {{ firstSentence }}
        </div>
        <button class="narrative-card__toggle" @click="toggleExpand">
          {{ expanded ? t('dashboard.narrative.collapse') : t('dashboard.narrative.expand') }}
          <van-icon :name="expanded ? 'arrow-up' : 'arrow-down'" size="12" />
        </button>
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
  position: relative;
  border-left: 3px solid var(--color-primary, #646cff);
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
  transition: all 0.25s ease-in-out;
  overflow: hidden;
}

[data-theme='dark'] .narrative-card {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.28);
}

.narrative-card--skeleton {
  border-left: 3px solid var(--color-primary, #646cff);
  opacity: 0.6;
  min-height: 40px;
  display: flex;
  align-items: center;
}

.narrative-card--skeleton :deep(.van-skeleton) {
  padding: 0;
}

.narrative-card__close {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: transparent;
  color: var(--text-secondary, #969799);
  cursor: pointer;
  border-radius: 50%;
  padding: 0;
  z-index: 1;
}

.narrative-card__close:hover {
  background: rgba(0, 0, 0, 0.05);
}

[data-theme='dark'] .narrative-card__close:hover {
  background: rgba(255, 255, 255, 0.1);
}

.narrative-card__inner {
  padding-right: 20px;
}

.narrative-card__label {
  font-size: 12px;
  color: var(--color-primary, #646cff);
  font-weight: 500;
  margin-bottom: 4px;
}

.narrative-card__body {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.narrative-card__text {
  flex: 1;
  font-size: 14px;
  line-height: 1.5;
  color: var(--text-primary, #323233);
  word-break: break-word;
}

.narrative-card__text--collapsed {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.narrative-card__toggle {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  gap: 2px;
  font-size: 12px;
  color: var(--color-primary, #646cff);
  background: none;
  border: none;
  cursor: pointer;
  padding: 2px 0;
  white-space: nowrap;
}

/* Responsive (R10) */
@media (max-width: 428px) {
  .narrative-card {
    margin: 8px 0;
    border-radius: 0;
  }
}
</style>
