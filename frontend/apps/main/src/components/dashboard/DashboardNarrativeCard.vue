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
const thinking = ref('')
const expanded = ref<string[]>([])
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
      thinking.value = data.thinking || ''
    }
  } catch {
    narrative.value = null
  } finally {
    loading.value = false
  }
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
  <van-cell-group
    v-if="!dismissed && (loading || narrative)"
    inset
    class="narrative-card"
    data-test="narrative-card"
  >
    <van-collapse v-model="expanded" class="narrative-collapse">
      <van-collapse-item name="narrative">
        <template #title>
          <div class="narrative-card__header">
            <span class="narrative-card__title">
              <span class="narrative-card__icon">
                <van-loading
                  v-if="loading"
                  size="16px"
                  type="spinner"
                  color="var(--van-primary-color, #1989fa)"
                />
                <IIcon v-else :icon="'lucide:sparkles'" size="18" class="narrative-card__icon-svg" />
              </span>
              <span class="narrative-card__title-text">{{ t('dashboard.narrative.title') }}</span>
            </span>
            <span v-if="loading" class="narrative-card__status narrative-card__status--loading">
              <van-loading size="12px" type="spinner" />
            </span>
            <button class="narrative-card__close" :aria-label="t('common.close')" @click.stop="onDismiss">
              <van-icon name="cross" size="14" />
            </button>
          </div>
        </template>

        <!-- Loading skeleton inside expanded area -->
        <template v-if="loading">
          <div class="narrative-card__thinking-shimmer">
            <div class="shimmer-line shimmer-line--long" />
            <div class="shimmer-line shimmer-line--short" />
          </div>
        </template>

        <!-- Loaded narrative -->
        <template v-else-if="narrative">
          <!-- Narrative text -->
          <p class="narrative-card__text">{{ narrative }}</p>
        </template>

        <!-- Thinking indicator: always visible when loading or has thinking data -->
        <template v-if="(loading || thinking) && !dismissed">
          <button class="narrative-card__thinking-toggle" @click.stop="toggleThinking">
            <IIcon :icon="'lucide:lightbulb'" size="14" class="narrative-card__thinking-icon" />
            <span class="narrative-card__thinking-status">
              <template v-if="loading">{{ t('dashboard.narrative.thinking') }}</template>
              <template v-else>{{ t('dashboard.narrative.thinkingDone', { seconds: loadDuration }) }}</template>
            </span>
            <van-icon :name="thinkingExpanded ? 'arrow-up' : 'arrow-down'" size="10" />
          </button>
          <div v-show="thinkingExpanded" class="narrative-card__thinking-content">
            <p class="narrative-card__thinking-text">{{ thinking }}</p>
          </div>
        </template>
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

/* Shimmer loading placeholder */
.narrative-card__thinking-shimmer {
  padding: 12px 0 4px;
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

/* Thinking indicator */
.narrative-card__thinking-toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 4px;
  font-size: 12px;
  color: var(--text-secondary, #969799);
  background: none;
  border: none;
  cursor: pointer;
  padding: 6px 0;
  width: 100%;
}

.narrative-card__thinking-icon {
  color: var(--van-primary-color, #1989fa);
}

.narrative-card__thinking-status {
  flex: 1;
}

.narrative-card__thinking-content {
  margin-top: 0;
  padding: 8px 12px;
  background: var(--van-background-2, #f7f8fa);
  border-radius: 8px;
}

[data-theme='dark'] .narrative-card__thinking-content {
  background: rgba(255, 255, 255, 0.04);
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
