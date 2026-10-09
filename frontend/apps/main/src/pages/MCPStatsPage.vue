<template>
  <div class="mcp-stats-page">
    <PageHeader :title="t('mcp.stats.title')" />

    <van-tabs v-model:active="activeRange" @change="onRangeChange">
      <van-tab :title="t('mcp.stats.range7d')" name="7d" />
      <van-tab :title="t('mcp.stats.range30d')" name="30d" />
    </van-tabs>

    <van-cell-group inset class="section">
      <van-cell :title="t('mcp.stats.totalCalls')" :value="String(stats?.total_calls ?? 0)" />
      <van-cell
        :title="t('mcp.stats.successRate')"
        :value="stats ? `${Math.round(stats.success_rate * 100)}%` : '—'"
      />
      <van-cell
        :title="t('mcp.stats.failures')"
        :value="String((stats?.failure_count ?? 0) + (stats?.error_count ?? 0))"
      />
    </van-cell-group>

    <van-cell-group inset :title="t('mcp.stats.trendTitle')" class="section">
      <div class="chart-wrap">
        <MCPUsageTrendChart :data="stats?.hourly_buckets ?? []" />
      </div>
    </van-cell-group>

    <van-cell-group inset :title="t('mcp.stats.toolTitle')" class="section">
      <div class="chart-wrap">
        <MCPToolDistributionChart :data="stats?.tool_breakdown ?? []" />
      </div>
    </van-cell-group>

    <van-cell-group inset :title="t('mcp.stats.ipTitle')" class="section">
      <van-cell
        v-for="ip in stats?.ip_breakdown ?? []"
        :key="ip.client_ip"
        :title="ip.client_ip"
        :label="ip.user_agent ?? ''"
        :value="String(ip.count)"
      />
      <van-cell v-if="(stats?.ip_breakdown ?? []).length === 0" :title="t('mcp.stats.empty')" />
    </van-cell-group>

    <van-cell-group inset :title="t('mcp.stats.recentEvents')" class="section">
      <van-cell
        v-for="entry in logs"
        :key="entry.id"
        :title="eventLabel(entry)"
        :label="formatDateTime(entry.created_at, locale)"
      >
        <template #value>
          <van-tag :type="statusTagType(entry.status)">
            {{ entry.status }}
          </van-tag>
        </template>
      </van-cell>
      <van-cell v-if="logs.length === 0" :title="t('mcp.stats.empty')" />
    </van-cell-group>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import PageHeader from '@/components/common/PageHeader.vue'
import MCPUsageTrendChart from '@/components/charts/MCPUsageTrendChart.vue'
import MCPToolDistributionChart from '@/components/charts/MCPToolDistributionChart.vue'
import {
  getMCPStats,
  getMCPAccessLogs,
  type MCPStatsData,
  type MCPAccessLogEntry,
} from '@/api/mcp-token'
import { formatDateTime } from '@/utils/format'

const { t, locale } = useI18n()

const activeRange = ref('7d')
const stats = ref<MCPStatsData | null>(null)
const logs = ref<MCPAccessLogEntry[]>([])

function rangeStart(days: number): string {
  const d = new Date()
  d.setDate(d.getDate() - days)
  return d.toISOString()
}

async function load() {
  const days = activeRange.value === '30d' ? 30 : 7
  const date_from = rangeStart(days)
  try {
    const [statsRes, logsRes] = await Promise.all([
      getMCPStats({ date_from }),
      getMCPAccessLogs({ date_from, page: 1, page_size: 50 }),
    ])
    stats.value = statsRes.data
    logs.value = logsRes.data.items
  } catch {
    stats.value = null
    logs.value = []
  }
}

function onRangeChange() {
  void load()
}

function eventLabel(entry: MCPAccessLogEntry): string {
  if (entry.event_type === 'tool_call') {
    return `${t('mcp.stats.eventToolCall')}: ${entry.tool_name ?? '—'}`
  }
  if (entry.event_type === 'connect') return t('mcp.stats.eventConnect')
  if (entry.event_type === 'disconnect') return t('mcp.stats.eventDisconnect')
  return entry.event_type
}

function statusTagType(status: string): 'success' | 'danger' | 'warning' | 'default' {
  if (status === 'success') return 'success'
  if (status === 'error') return 'danger'
  if (status === 'failure' || status === 'permission_denied') return 'warning'
  return 'default'
}

onMounted(load)
</script>

<style scoped>
.mcp-stats-page {
  min-height: 100vh;
  background: var(--van-background);
  padding-bottom: 24px;
}
.section {
  margin-top: 12px;
}
.chart-wrap {
  padding: 12px 8px;
}
</style>
