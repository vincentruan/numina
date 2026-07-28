<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getNarrative } from '@/api/dashboard'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import IIcon from '@/components/IIcon.vue'

const { t } = useI18n()
const authStore = useAuthStore()

const loading = ref(true)
const loadStart = ref(0)
const loadDuration = ref(0)
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

  loadStart.value = Date.now()
  try {
    const resp = await getNarrative()
    const data = resp.data
    loadDuration.value = Math.round((Date.now() - loadStart.value) / 1000)
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
  <van-cell-group inset class="narrative-card" data-test="narrative-card">
    <!-- Loading state: header + shimmer thinking -->
    <template v-if="loading && !dismissed">
      <div class="narrative-card__header">
        <span class="narrative-card__title">
          <span class="narrative-card__icon">
            <van-loading size="16px" type="spinner" color="var(--van-primary-color, #1989fa)" />
          </span>
          <span class="narrative-card__title-text">{{ t('dashboard.narrative.title') }}</span>
        </span>
        <span class="narrative-card__status narrative-card__status--loading">
          <van-loading size="12px" type="spinner" />
        </span>
      </div>
      <!-- Shimmer thinking placeholder -->
      <div class="narrative-card__thinking-shimmer">
        <div class="shimmer-line shimmer-line--long" />
        <div class="shimmer-line shimmer-line--short" />
      </div>
    </template>

    <!-- Loaded narrative -->
    <van-collapse v-else-if="narrative && !dismissed" v-model="expanded as any" class="narrative-collapse">
      <van-collapse-item name="narrative">
        <template #title>
          <div class="narrative-card__header">
            <span class="narrative-card__title">
              <span class="narrative-card__icon">
                <IIcon :icon="'lucide:sparkles'" size="18" class="narrative-card__icon-svg" />
              </span>
              <span class="narrative-card__title-text">{{ t('dashboard.narrative.title') }}</span>
            </span>
            <span v-if="thinking" class="narrative-card__status">
              {{ t('dashboard.narrative.thinkingDone', { seconds: loadDuration }) }}
            </span>
            <button class="narrative-card__close" :aria-label="t('common.close')" @click.stop="onDismiss">
              <van-icon name="cross" size="14" />
            </button>
          </div>
        </template>

        <!-- Narrative text -->
        <p class="narrative-card__text">{{ narrative }}</p>

        <!-- Thinking section -->
        <div v-if="thinking" class="narrative-card__thinking">
          <button class="narrative-card__thinking-toggle" @click="toggleThinking">
            <van-icon :name="thinkingExpanded ? 'arrow-up' : 'arrow-down'" size="10" />
            {{ thinkingExpanded ? t('dashboard.narrative.collapse') : t('dashboard.narrative.expand') }}
            {{ t('dashboard.narrative.thinking', '思考过程') }}
          </button>
          <div v-show="thinkingExpanded" class="narrative-card__thinking-content">
            <p class="narrative-card__thinking-text">{{ thinking }}</p>
          </div>
          <div v-show="!thinkingExpanded" class="narrative-card__thinking-preview">
            <p class="narrative-card__thinking-text narrative-card__text--clamp">{{ thinking }}</p>
          </div>
        </div>
      </van-collapse-item>
    </van-collapse>
  </van-cell-group>
</template>

<style scoped>
.narrative-card {
  margin: 8px 0;
}

.narrative-card :deep(.van-cell) {
  background: var(--card-bg);
}

.narrative-collapse :deep(.van-collapse-item__title) {
  justify-content: flex-start;
}

.narrative-collapse :deep(.van-cell__title) {
  flex: 1;
  display: flex;
  min-width: 0;
}

.narrative-collapse :deep(.van-cell__value) {
  flex: none;
  width: 0;
}

/* Header row: icon+title on left, status+close on right */
.narrative-card__header {
  display: flex;
  align-items: center;
  width: 100%;
  min-width: 0;
  gap: 8px;
}

.narrative-card__title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex: 1;
  min-width: 0;
}

.narrative-card__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.4em;
  height: 1.4em;
  flex-shrink: 0;
}

.narrative-card__icon-svg {
  color: #1989fa;
}

.narrative-card__title-text {
  font-weight: 600;
}

.narrative-card__status {
  margin-left: 8px;
  font-size: 12px;
  color: var(--van-text-color-2);
  white-space: nowrap;
}

.narrative-card__status--loading {
  display: inline-flex;
  align-items: center;
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
  margin-left: 4px;
}

.narrative-card__close:active {
  background: rgba(0, 0, 0, 0.06);
}

[data-theme='dark'] .narrative-card__close:active {
  background: rgba(255, 255, 255, 0.1);
}

/* Narrative text */
.narrative-card__text {
  font-size: 14px;
  line-height: 1.6;
  color: var(--text-primary, #323233);
  margin: 0 0 8px;
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

/* Shimmer loading placeholder */
.narrative-card__thinking-shimmer {
  padding: 12px 16px 4px;
}

.shimmer-line {
  height: 12px;
  border-radius: 6px;
  background: linear-gradient(
    90deg,
    var(--van-skeleton-row-background, #f2f3f5) 25%,
    var(--van-active-color, #f2f3f5) 50%,
    var(--van-skeleton-row-background, #f2f3f5) 75%
  );
  background-size: 200% 100%;
  animation: shimmer 1.5s ease-in-out infinite;
  margin-bottom: 8px;
}

.shimmer-line--long {
  width: 90%;
}

.shimmer-line--short {
  width: 60%;
}

@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
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
</style>
