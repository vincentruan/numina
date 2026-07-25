<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getFinanceCoach } from '@/api/ai'
import type { FinanceSuggestion } from '@/types'
import { useI18n } from 'vue-i18n'
import IIcon from '@/components/IIcon.vue'

const { t } = useI18n()
const router = useRouter()
const suggestions = ref<FinanceSuggestion[]>([])
const loading = ref(true)
const loaded = ref(false)
const visible = ref(false)
const refreshing = ref(false)
const expanded = ref<string[]>([])

const count = computed(() => suggestions.value.length)

async function load(force = false) {
  try {
    refreshing.value = force
    const resp = await getFinanceCoach(force)
    // Advice baseline gate (spec §7.1): schema-validate before display.
    const valid = (resp.report.suggestions || []).filter(
      (s) =>
        s &&
        s.id &&
        ['high', 'medium', 'low'].includes(s.severity) &&
        s.title &&
        s.action &&
        s.target_type &&
        s.target_id &&
        s.cta_label,
    )
    if (valid.length === 0) {
      visible.value = false
      return
    }
    suggestions.value = valid.slice(0, 3)
    visible.value = true
  } catch {
    visible.value = false // silent hide on failure (spec §7.2)
  } finally {
    loading.value = false
    loaded.value = true
    refreshing.value = false
  }
}

function onCta(s: FinanceSuggestion) {
  // CTA navigates to the target entity (A1b-style passive entry).
  if (s.target_type === 'liability') router.push(`/liabilities/${s.target_id}`)
  else if (s.target_type === 'asset') router.push(`/assets/${s.target_id}`)
  else if (s.target_type === 'wish') router.push(`/wishes/${s.target_id}`)
}

async function onToggle(names: string[]) {
  if (names.includes('coach') && !loaded.value) {
    await load(false)
  }
}

onMounted(() => {
  // Independent async load — does not block the page.
  load(false)
})
</script>

<template>
  <van-cell-group inset class="chart-section finance-coach-card" data-test="finance-coach-card">
    <van-collapse v-model="expanded" @change="onToggle">
      <van-collapse-item name="coach">
        <template #title>
          <div class="coach-header">
            <span class="coach-title">
              <span class="coach-icon">
                <van-loading v-if="loading" size="16px" type="spinner" color="#1989fa" />
                <IIcon v-else :icon="'lucide:lightbulb'" size="18" class="coach-icon__svg" />
              </span>
              <span class="coach-title__text">{{ t('dashboard.financeCoach.title') }}</span>
            </span>
            <span v-if="loading" class="coach-summary coach-summary--loading">
              <van-loading size="12px" type="spinner" />
            </span>
            <span v-else-if="count > 0" class="coach-summary">
              {{ t('dashboard.financeCoach.count', { count }) }}
            </span>
            <span v-else class="coach-summary coach-summary--empty">
              {{ t('dashboard.financeCoach.empty') }}
            </span>
          </div>
        </template>

        <!-- Loading skeleton inside expanded area -->
        <template v-if="loading">
          <div v-for="i in 3" :key="i" class="fc-skeleton-item">
            <div class="fc-skeleton-bar" />
            <div class="fc-skeleton-body">
              <van-skeleton title :row="2" animate />
            </div>
          </div>
        </template>

        <!-- Loaded suggestions -->
        <template v-else-if="visible">
          <div
            v-for="s in suggestions"
            :key="s.id"
            :class="['fc-suggestion', `severity-${s.severity}`]"
            :data-test="`suggestion-${s.id}`"
          >
            <div class="fc-severity-bar" />
            <div class="fc-body">
              <div class="fc-s-title">{{ s.title }}</div>
              <div class="fc-s-action">{{ s.action }}</div>
            </div>
            <van-button size="small" type="primary" @click="onCta(s)">{{ s.cta_label }}</van-button>
          </div>
          <div class="fc-footer">
            <span class="fc-disclaimer">{{ t('dashboard.financeCoach.disclaimer') }}</span>
            <van-button size="mini" plain :loading="refreshing" @click.stop="load(true)">
              {{ t('dashboard.financeCoach.refresh') }}
            </van-button>
          </div>
        </template>

        <!-- Empty / error state inside expanded area -->
        <template v-else-if="loaded">
          <van-empty
            :description="t('dashboard.financeCoach.empty')"
            image-size="60"
            class="section-empty"
          />
        </template>
      </van-collapse-item>
    </van-collapse>
  </van-cell-group>
</template>

<style scoped>
.finance-coach-card {
  margin: 8px 0;
}
.finance-coach-card :deep(.van-collapse-item__title) {
  justify-content: flex-start;
}
.finance-coach-card :deep(.van-cell__title) {
  flex: 1;
  display: flex;
  align-items: center;
  min-width: 0;
}
.coach-header {
  display: flex;
  align-items: center;
  width: 100%;
  min-width: 0;
  gap: 8px;
}
.coach-title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex: 1;
  min-width: 0;
}
.coach-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.4em;
  height: 1.4em;
  flex-shrink: 0;
}
.coach-icon__svg {
  color: #1989fa;
}
.coach-title__text {
  font-weight: 600;
}
.coach-summary {
  margin-left: 8px;
  font-size: 12px;
  color: var(--van-text-color-2);
}
.coach-summary--loading {
  display: inline-flex;
  align-items: center;
}
.coach-summary--empty {
  color: var(--van-text-color-3);
}

/* Skeleton items inside expanded area */
.fc-skeleton-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  border-top: 1px solid var(--separator, #eee);
}
.fc-skeleton-bar {
  width: 4px;
  align-self: stretch;
  border-radius: 2px;
  background: var(--van-skeleton-row-background, #f2f3f5);
}
.fc-skeleton-body {
  flex: 1;
}
.fc-skeleton-body :deep(.van-skeleton) {
  padding: 0;
}

/* Loaded suggestion items */
.fc-suggestion {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  border-top: 1px solid var(--separator, #eee);
}
.fc-severity-bar {
  width: 4px;
  align-self: stretch;
  border-radius: 2px;
}
.severity-high .fc-severity-bar {
  background: #ee0a24;
}
.severity-medium .fc-severity-bar {
  background: #ff976a;
}
.severity-low .fc-severity-bar {
  background: #1989fa;
}
.fc-body {
  flex: 1;
}
.fc-s-title {
  font-weight: 500;
}
.fc-s-action {
  font-size: 12px;
  color: var(--text-secondary, #969799);
}
.fc-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 8px;
}
.fc-disclaimer {
  font-size: 11px;
  color: var(--van-text-color-3, #c8c9cc);
}
.section-empty {
  padding: 12px 0;
}
</style>
