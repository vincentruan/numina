<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getFinanceCoach } from '@/api/ai'
import type { FinanceSuggestion } from '@/types'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
const router = useRouter()
const suggestions = ref<FinanceSuggestion[]>([])
const loading = ref(true)
const visible = ref(false)
const refreshing = ref(false)

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
    refreshing.value = false
  }
}

function onCta(s: FinanceSuggestion) {
  // CTA navigates to the target entity (A1b-style passive entry).
  if (s.target_type === 'liability') router.push(`/liabilities/${s.target_id}`)
  else if (s.target_type === 'asset') router.push(`/assets/${s.target_id}`)
  else if (s.target_type === 'wish') router.push(`/wishes/${s.target_id}`)
}

onMounted(() => load(false))
</script>

<template>
  <van-skeleton v-if="loading" title :row="3" />
  <div v-else-if="visible" class="finance-coach-card" data-test="finance-coach-card">
    <div class="fc-header">
      <span class="fc-title">{{ t('dashboard.financeCoach.title') }}</span>
      <van-button size="mini" plain :loading="refreshing" @click="load(true)">
        {{ t('dashboard.financeCoach.refresh') }}
      </van-button>
    </div>
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
    <div class="fc-disclaimer">{{ t('dashboard.financeCoach.disclaimer') }}</div>
  </div>
  <!-- v-else: silent hide (empty / failure) -->
</template>

<style scoped>
.finance-coach-card {
  background: var(--card-bg, #fff);
  border-radius: 12px;
  padding: 12px;
  margin: 8px 12px;
}
.fc-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.fc-title {
  font-weight: 600;
}
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
.fc-disclaimer {
  font-size: 11px;
  color: var(--van-text-color-3, #c8c9cc);
  margin-top: 8px;
}
</style>
