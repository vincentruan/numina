<template>
  <div class="ai-disposal-page">
    <PageHeader title="闲置资产清仓" />

    <div v-if="loading" class="loading-state">
      <van-loading size="32" type="spinner" />
    </div>

    <div v-else-if="!suggestions.length" class="empty-state">
      <van-empty description="暂无处置建议">
        <template #image>
          <svg width="80" height="80" viewBox="0 0 80 80" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
            <circle cx="40" cy="40" r="36" fill="rgba(99,102,241,0.08)" />
            <circle cx="40" cy="40" r="28" fill="rgba(99,102,241,0.10)" />
            <rect x="24" y="28" width="32" height="24" rx="4" stroke="#6366f1" stroke-width="2.5" fill="none"/>
            <path d="M32 28v-4a8 8 0 0116 0v4" stroke="#6366f1" stroke-width="2.5" stroke-linecap="round" fill="none"/>
            <circle cx="40" cy="40" r="4" fill="#6366f1" opacity="0.6"/>
            <circle cx="56" cy="28" r="6" fill="#4ade80"/>
            <path d="M53 28l2 2 4-4" stroke="#fff" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </template>
      </van-empty>
      <div class="actions">
        <van-button plain block :loading="refreshing" @click="onRefresh">扫描闲置资产</van-button>
      </div>
    </div>

    <template v-else>
      <div class="summary-bar">
        <span>{{ suggestions.length }} 项待处置资产</span>
        <van-button size="mini" plain :loading="refreshing" @click="onRefresh">重新扫描</van-button>
      </div>

      <van-swipe-cell v-for="s in suggestions" :key="s.id" class="suggestion-item">
        <div class="suggestion-card">
          <div class="card-top">
            <div class="asset-info">
              <span class="asset-name">{{ s.asset_name }}</span>
              <span class="category-tag">{{ s.category_name }}</span>
            </div>
            <div class="score-badge" :class="scoreClass(s.inefficiency_score)">
              {{ s.inefficiency_score }}
            </div>
          </div>

          <div v-if="s.estimated_resale_range" class="resale-range">
            估算转售价：{{ s.estimated_resale_range }}
          </div>

          <div class="channel-row">
            <van-icon name="shop-o" size="14" />
            <span>推荐渠道：{{ s.suggested_channel }}</span>
          </div>

          <p v-if="s.suggestion" class="suggestion-text">{{ s.suggestion }}</p>

          <div v-if="s.daily_cost" class="daily-cost">
            持续损耗：¥{{ s.daily_cost.toFixed(1) }}/天
          </div>
        </div>
        <template #right>
          <van-button square type="warning" text="忽略" class="dismiss-btn" @click="onDismiss(s.id)" />
        </template>
      </van-swipe-cell>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { showToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { getDisposalSuggestions, refreshDisposalSuggestions, dismissDisposalSuggestion } from '@/api/ai'
import PageHeader from '@/components/common/PageHeader.vue'

interface DisposalSuggestion {
  id: number
  asset_name: string
  score: number
  reason: string
  resale_range?: string
  channels?: string[]
  [key: string]: unknown
}

const { t } = useI18n()

const loading = ref(false)
const refreshing = ref(false)
const suggestions = ref<DisposalSuggestion[]>([])

function scoreClass(score: number) {
  if (score >= 70) return 'score-high'
  if (score >= 40) return 'score-medium'
  return 'score-low'
}

async function loadSuggestions() {
  loading.value = true
  try {
    const res = await getDisposalSuggestions()
    suggestions.value = res.data
  } catch {
    showToast(t('toast.loadFailed'))
  } finally {
    loading.value = false
  }
}

async function onRefresh() {
  refreshing.value = true
  try {
    await refreshDisposalSuggestions()
    await loadSuggestions()
    showToast(t('toast.aiScanComplete'))
  } catch {
    showToast(t('toast.aiScanFailed'))
  } finally {
    refreshing.value = false
  }
}

async function onDismiss(id: string) {
  try {
    await dismissDisposalSuggestion(id)
    suggestions.value = suggestions.value.filter(s => s.id !== id)
  } catch {
    showToast(t('toast.operationFailed'))
  }
}

onMounted(loadSuggestions)
</script>

<style scoped>
.ai-disposal-page {
  background: var(--bg-secondary);
  min-height: 100vh;
  padding-bottom: 24px;
}
.loading-state { display: flex; justify-content: center; padding: 60px; }
.empty-state { padding: 40px 16px; min-height: 240px; display: flex; flex-direction: column; align-items: center; justify-content: center; }
.actions { padding: 12px 16px 0; width: 100%; }
.summary-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  font-size: 13px;
  color: var(--text-secondary);
}
.suggestion-item { margin: 8px 16px; border-radius: 12px; overflow: hidden; }
.suggestion-card { background: var(--bg-primary); padding: 14px 16px; }
.card-top { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px; }
.asset-info { display: flex; flex-direction: column; gap: 4px; }
.asset-name { font-size: 15px; font-weight: 600; color: var(--text-primary); }
.category-tag {
  font-size: 11px; padding: 2px 8px; border-radius: 10px;
  background: var(--bg-secondary); color: var(--text-secondary);
  align-self: flex-start;
}
.score-badge {
  width: 40px; height: 40px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 14px; font-weight: 700;
}
.score-high { background: #fce4ec; color: #c62828; }
.score-medium { background: #fff8e1; color: #92400e; }
.score-low { background: #e8f5e9; color: #2e7d32; }
.resale-range { font-size: 13px; color: var(--text-primary); font-weight: 500; margin-bottom: 6px; }
.channel-row {
  display: flex; align-items: center; gap: 4px;
  font-size: 12px; color: var(--text-secondary); margin-bottom: 6px;
}
.suggestion-text { font-size: 13px; color: var(--text-secondary); margin: 0 0 6px; line-height: 1.5; }
.daily-cost { font-size: 12px; color: #f44336; }
.dismiss-btn { height: 100%; }
</style>
