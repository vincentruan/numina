<template>
  <div class="extraction-circuit-section">
    <h3 class="section-title">{{ t('admin.extractionCircuit.title') }}</h3>
    <p class="section-desc">{{ t('admin.extractionCircuit.desc') }}</p>

    <div v-if="loading" class="loading-state">
      <van-loading size="20" type="spinner" />
    </div>

    <div v-else-if="!circuits.length" class="empty-state">
      <span class="empty-icon" aria-hidden="true">✅</span>
      <span>{{ t('admin.extractionCircuit.allOk') }}</span>
    </div>

    <div v-else class="circuit-list">
      <div v-for="c in circuits" :key="`${c.family_id}-${c.capability}`" class="circuit-card">
        <div class="circuit-info">
          <span class="circuit-capability">{{ c.capability }}</span>
          <span class="circuit-state" :class="`state--${c.state}`">{{ c.state }}</span>
          <span class="circuit-family">Family #{{ c.family_id }}</span>
        </div>
        <div class="circuit-meta">
          <span v-if="c.opened_at">{{ t('admin.extractionCircuit.openedAt') }}: {{ formatTime(c.opened_at) }}</span>
          <span v-if="c.opened_until">{{ t('admin.extractionCircuit.expiresAt') }}: {{ formatTime(c.opened_until) }}</span>
        </div>
        <van-button
          size="small"
          type="warning"
          :loading="resetting === `${c.family_id}-${c.capability}`"
          @click="onReset(c)"
        >
          {{ t('admin.extractionCircuit.reset') }}
        </van-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { showToast } from 'vant'
import http from '@/api'

interface CircuitRow {
  family_id: string
  capability: string
  state: string
  opened_at: string | null
  opened_until: string | null
  last_evaluated_at: string
  manually_reset_at: string | null
  reset_by_user_id: string | null
}

const { t } = useI18n()
const loading = ref(true)
const circuits = ref<CircuitRow[]>([])
const resetting = ref<string | null>(null)

async function loadCircuits() {
  loading.value = true
  try {
    const res = await http.get<{ rows: CircuitRow[] }>('/admin/ai-extraction-circuit')
    circuits.value = res.data.rows
  } catch {
    showToast(t('toast.loadFailed'))
  } finally {
    loading.value = false
  }
}

async function onReset(c: CircuitRow) {
  const key = `${c.family_id}-${c.capability}`
  resetting.value = key
  try {
    await http.post('/admin/ai-extraction-circuit/reset', {
      family_id: c.family_id,
      capability: c.capability,
    })
    circuits.value = circuits.value.filter(
      (r) => !(r.family_id === c.family_id && r.capability === c.capability),
    )
    showToast(t('admin.extractionCircuit.resetSuccess'))
  } catch {
    showToast(t('toast.operationFailed'))
  } finally {
    resetting.value = null
  }
}

function formatTime(iso: string | null): string {
  if (!iso) return '-'
  return new Date(iso).toLocaleString()
}

onMounted(loadCircuits)
</script>

<style scoped>
.extraction-circuit-section {
  padding: 16px;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 4px;
}

.section-desc {
  font-size: 13px;
  color: var(--text-secondary);
  margin: 0 0 16px;
}

.loading-state {
  display: flex;
  justify-content: center;
  padding: 24px;
}

.empty-state {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 16px;
  background: var(--bg-secondary);
  border-radius: 8px;
  font-size: 14px;
  color: var(--text-secondary);
}

.circuit-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.circuit-card {
  padding: 12px;
  background: var(--bg-secondary);
  border-radius: 8px;
  border-left: 3px solid #dc2626;
}

.circuit-info {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.circuit-capability {
  font-weight: 500;
  font-size: 14px;
}

.circuit-state {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 4px;
  font-weight: 500;
}

.state--rate_limited {
  background: rgba(234, 179, 8, 0.15);
  color: #a16207;
}

.state--circuit_open {
  background: rgba(220, 38, 38, 0.1);
  color: #dc2626;
}

.circuit-family {
  font-size: 12px;
  color: var(--text-secondary);
  margin-left: auto;
}

.circuit-meta {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 8px;
}
</style>
