<script setup lang="ts">
import { computed, ref, onMounted, onBeforeUnmount } from 'vue'
import { showConfirmDialog, showSuccessToast, showFailToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import {
  getMCPToken,
  generateMCPToken,
  updateMCPToken,
  getMCPTools,
  getMCPStats,
  type MCPTokenData,
  type MCPToolCatalogItem,
  type MCPStatsData,
} from '@/api/mcp-token'
import { formatDateTime } from '@/utils/format'

const { t, locale } = useI18n()
const router = useRouter()
const authStore = useAuthStore()
const isOwner = computed(() => authStore.user?.role === 'owner')

const token = ref<MCPTokenData | null>(null)
const plaintext = ref('')
const reveal = ref(false)
const busy = ref(false)
let revealTimer: ReturnType<typeof setTimeout> | null = null

// Tool permissions
const showToolPicker = ref(false)
const toolCatalog = ref<MCPToolCatalogItem[]>([])
const selectedTools = ref<string[]>([])
const toolsSaving = ref(false)

// Usage summary
const stats = ref<MCPStatsData | null>(null)

// Expiration picker (presets + never + custom)
const showExpirePicker = ref(false)
const showCustomDatePicker = ref(false)
const customDateModel = ref<string[]>([])
const expireOptions = computed(() => [
  { text: t('mcp.token.expire30d'), value: '30d' },
  { text: t('mcp.token.expire90d'), value: '90d' },
  { text: t('mcp.token.expire180d'), value: '180d' },
  { text: t('mcp.token.expire1y'), value: '365d' },
  { text: t('mcp.token.expireCustom'), value: 'custom' },
  { text: t('mcp.token.expireNever'), value: 'never' },
])

function fmtDate(s: string | null): string {
  if (!s) return t('mcp.token.expireNever')
  return formatDateTime(s, locale.value)
}

/** Tools visible in the picker — write tools only when allow_write is on. */
const visibleTools = computed(() =>
  toolCatalog.value.filter(tool => !tool.requires_write || token.value?.allow_write)
)

/** Summary line for the tool permission row. */
const toolsSummary = computed(() => {
  if (!token.value) return ''
  if (token.value.allowed_tools === null) return t('mcp.token.tools.allAvailable')
  const total = visibleTools.value.length
  const enabled = token.value.allowed_tools.filter(
    n => visibleTools.value.some(tool => tool.name === n)
  ).length
  return t('mcp.token.tools.countSummary', { enabled, total })
})

const usageSummary = computed(() => {
  if (!stats.value || stats.value.total_calls === 0) return t('mcp.token.usage.noUsage')
  return t('mcp.token.usage.summary', {
    count: stats.value.total_calls,
    rate: Math.round(stats.value.success_rate * 100),
  })
})

async function load() {
  try {
    const res = await getMCPToken()
    token.value = res.data
  } catch {
    token.value = null
  }
  if (token.value) {
    void loadStats()
  }
}

async function loadStats() {
  try {
    const start = new Date()
    start.setHours(0, 0, 0, 0)
    const res = await getMCPStats({ date_from: start.toISOString() })
    stats.value = res.data
  } catch {
    stats.value = null
  }
}

async function loadToolCatalog() {
  if (toolCatalog.value.length > 0) return
  try {
    const res = await getMCPTools()
    toolCatalog.value = res.data.tools
  } catch {
    toolCatalog.value = []
  }
}

async function onOpenToolPicker() {
  if (!isOwner.value || !token.value) return
  await loadToolCatalog()
  // null = all available → pre-check every visible tool
  selectedTools.value =
    token.value.allowed_tools === null
      ? visibleTools.value.map(tool => tool.name)
      : [...token.value.allowed_tools]
  showToolPicker.value = true
}

function onEnableAll() {
  selectedTools.value = visibleTools.value.map(tool => tool.name)
}

function onClearAll() {
  selectedTools.value = []
}

async function onSaveTools() {
  if (!token.value) return
  toolsSaving.value = true
  try {
    // Only keep tools that are currently visible (write tools hidden when allow_write is off)
    const visibleNames = new Set(visibleTools.value.map(t => t.name))
    const effectiveSelection = selectedTools.value.filter(n => visibleNames.has(n))
    // All visible tools selected → store null (unrestricted)
    const allSelected =
      visibleTools.value.length > 0 &&
      visibleTools.value.every(tool => effectiveSelection.includes(tool.name))
    const res = await updateMCPToken({
      allowed_tools: allSelected ? null : [...effectiveSelection],
    })
    token.value = res.data
    showToolPicker.value = false
    showSuccessToast(t('toast.saved'))
  } catch {
    showFailToast(t('toast.saveFailed'))
  } finally {
    toolsSaving.value = false
  }
}

function onOpenStats() {
  void router.push('/settings/ai/mcp/stats')
}

onMounted(load)

onBeforeUnmount(() => {
  if (revealTimer) clearTimeout(revealTimer)
})

function maskedToken(): string {
  const last4 = token.value?.token_last4 ?? ''
  return `mcp_••••••••••••${last4}`
}

function displayToken(): string {
  return reveal.value && plaintext.value ? plaintext.value : maskedToken()
}

function armAutoRemask(ms: number) {
  if (revealTimer) clearTimeout(revealTimer)
  revealTimer = setTimeout(() => {
    reveal.value = false
  }, ms)
}

async function onRevealToggle() {
  if (!plaintext.value) return
  reveal.value = !reveal.value
  if (reveal.value) armAutoRemask(10_000)
  else if (revealTimer) {
    clearTimeout(revealTimer)
    revealTimer = null
  }
}

async function onCopy() {
  if (!plaintext.value) return
  try {
    await navigator.clipboard.writeText(plaintext.value)
    showSuccessToast(t('toast.copied'))
  } catch {
    showFailToast(t('toast.copyFailed'))
  }
}

async function onGenerate() {
  const rotating = token.value !== null
  await showConfirmDialog({
    title: rotating ? t('mcp.token.rotateTitle') : t('mcp.token.generateTitle'),
    message: rotating ? t('mcp.token.rotateWarning') : t('mcp.token.generateWarning'),
    confirmButtonText: t('common.confirm'),
    cancelButtonText: t('common.cancel'),
  })
  busy.value = true
  try {
    const res = await generateMCPToken()
    token.value = res.data
    plaintext.value = res.data.token
    reveal.value = true
    armAutoRemask(30_000)
    showSuccessToast(t('mcp.token.generated'))
    void loadStats()
  } finally {
    busy.value = false
  }
}

async function onToggleExternal(on: boolean) {
  await showConfirmDialog({
    title: t('mcp.token.allowExternal'),
    message: t('mcp.token.allowExternalWarning'),
    confirmButtonText: t('common.confirm'),
    cancelButtonText: t('common.cancel'),
  })
  const res = await updateMCPToken({ allow_external: on })
  token.value = res.data
  showSuccessToast(on ? t('toast.enabled') : t('toast.disabled'))
}

async function onToggleWrite(on: boolean) {
  await showConfirmDialog({
    title: t('mcp.token.allowWrite'),
    message: t('mcp.token.allowWriteWarning'),
    confirmButtonText: t('common.confirm'),
    cancelButtonText: t('common.cancel'),
  })
  const res = await updateMCPToken({ allow_write: on })
  token.value = res.data
  showSuccessToast(on ? t('toast.enabled') : t('toast.disabled'))
}

async function onExpireConfirm({ selectedValues }: { selectedValues: string[] }) {
  showExpirePicker.value = false
  const choice = selectedValues[0]
  if (!choice || !token.value) return
  if (choice === 'custom') {
    const today = new Date()
    customDateModel.value = [
      String(today.getFullYear()),
      String(today.getMonth() + 1).padStart(2, '0'),
      String(today.getDate()).padStart(2, '0'),
    ]
    showCustomDatePicker.value = true
    return
  }
  if (choice === 'never') {
    const res = await updateMCPToken({ expires_at: null })
    token.value = res.data
    showSuccessToast(t('toast.saved'))
    return
  }
  const days = parseInt(choice, 10)
  const d = new Date()
  d.setDate(d.getDate() + days)
  const res = await updateMCPToken({ expires_at: d.toISOString() })
  token.value = res.data
  showSuccessToast(t('toast.saved'))
}

function onCustomDateConfirm({ selectedValues }: { selectedValues: string[] }) {
  showCustomDatePicker.value = false
  if (selectedValues.length !== 3 || !token.value) return
  const dateStr = `${selectedValues[0]}-${selectedValues[1]}-${selectedValues[2]}`
  const d = new Date(`${dateStr}T00:00:00Z`)
  if (isNaN(d.getTime())) return
  updateMCPToken({ expires_at: d.toISOString() }).then(res => {
    token.value = res.data
    showSuccessToast(t('toast.saved'))
  }).catch(() => showFailToast(t('toast.saveFailed')))
}
</script>

<template>
  <van-cell-group inset class="backend-mcp-card">
    <template #title>
      <span class="card-title">
        {{ t('mcp.token.title') }}
        <van-tag type="primary" size="medium" style="margin-left: 6px">
          {{ t('mcp.token.builtIn') }}
        </van-tag>
      </span>
    </template>

    <!-- No token yet -->
    <template v-if="!token">
      <van-cell :title="t('mcp.token.notGenerated')" />
      <van-cell v-if="isOwner">
        <template #title>
          <van-button
            round
            type="primary"
            block
            icon="plus"
            :loading="busy"
            @click="onGenerate"
          >
            {{ t('mcp.token.generate') }}
          </van-button>
        </template>
      </van-cell>
    </template>

    <!-- Token exists -->
    <template v-else>
      <van-cell :title="t('mcp.token.tokenLabel')">
        <template #value>
          <div class="token-display">
            <code class="token-text">{{ displayToken() }}</code>
            <van-icon
              v-if="plaintext"
              :name="reveal ? 'eye-o' : 'eye-closed'"
              class="token-action"
              @click="onRevealToggle"
            />
            <van-icon
              v-if="plaintext && isOwner"
              name="description"
              class="token-action"
              @click="onCopy"
            />
          </div>
        </template>
      </van-cell>

      <van-cell
        v-if="reveal && plaintext"
        :title="t('mcp.token.copyNotice')"
        class="warn-row"
      />

      <van-cell :title="t('mcp.token.allowExternal')">
        <template #value>
          <van-switch
            :model-value="token.allow_external"
            size="20px"
            :disabled="!isOwner"
            @change="(v: boolean) => onToggleExternal(v)"
          />
        </template>
      </van-cell>

      <van-cell :title="t('mcp.token.allowWrite')">
        <template #value>
          <van-switch
            :model-value="token.allow_write"
            size="20px"
            :disabled="!isOwner || !token.allow_external"
            @change="(v: boolean) => onToggleWrite(v)"
          />
        </template>
      </van-cell>

      <van-cell
        :title="t('mcp.token.tools.label')"
        :value="toolsSummary"
        is-link
        :class="{ 'cell-disabled': !isOwner }"
        @click="onOpenToolPicker"
      />

      <van-cell
        :title="t('mcp.token.usage.label')"
        :value="usageSummary"
        is-link
        @click="onOpenStats"
      >
        <template #label>
          <span v-if="stats && stats.error_count + stats.failure_count > 0" class="anomaly-flag">
            {{ t('mcp.token.usage.anomalyFlag') }}
          </span>
        </template>
      </van-cell>

      <van-cell v-if="isOwner" :title="t('mcp.token.expiration')">
        <template #value>
          <van-field
            :model-value="fmtDate(token.expires_at)"
            readonly
            is-link
            class="expire-field"
            @click="showExpirePicker = true"
          />
        </template>
      </van-cell>

      <van-cell :title="t('mcp.token.lastUsedAt')" :label="token.last_used_at ? formatDateTime(token.last_used_at, locale) : '—'" />
      <van-cell :title="t('mcp.token.createdAt')" :label="formatDateTime(token.created_at, locale)" />

      <van-cell v-if="isOwner">
        <template #title>
          <van-button
            round
            plain
            type="danger"
            block
            icon="replay"
            :loading="busy"
            @click="onGenerate"
          >
            {{ t('mcp.token.regenerate') }}
          </van-button>
        </template>
      </van-cell>
    </template>
  </van-cell-group>

  <van-popup v-model:show="showExpirePicker" position="bottom" round destroy-on-close>
    <van-picker
      :columns="expireOptions"
      :title="t('mcp.token.expireTitle')"
      @confirm="onExpireConfirm"
      @cancel="showExpirePicker = false"
    />
  </van-popup>

  <van-popup v-model:show="showCustomDatePicker" position="bottom" round destroy-on-close>
    <van-date-picker
      v-model="customDateModel"
      @confirm="onCustomDateConfirm"
      @cancel="showCustomDatePicker = false"
    />
  </van-popup>

  <!-- Tool permission picker -->
  <van-popup v-model:show="showToolPicker" position="bottom" round destroy-on-close class="tool-picker">
    <div class="tool-picker-header">
      <span class="tool-picker-title">{{ t('mcp.token.tools.title') }}</span>
      <div class="tool-picker-actions">
        <van-button size="small" plain type="primary" @click="onEnableAll">
          {{ t('mcp.token.tools.enableAll') }}
        </van-button>
        <van-button size="small" plain @click="onClearAll">
          {{ t('mcp.token.tools.clear') }}
        </van-button>
      </div>
    </div>
    <p class="tool-picker-warning">{{ t('mcp.token.tools.warning') }}</p>

    <div v-if="visibleTools.length === 0" class="tool-picker-empty">
      {{ t('mcp.token.tools.noTools') }}
    </div>

    <van-checkbox-group v-else v-model="selectedTools" class="tool-list">
      <van-cell
        v-for="tool in visibleTools"
        :key="tool.name"
        :title="tool.name"
        :label="tool.description"
        clickable
        @click="
          selectedTools.includes(tool.name)
            ? (selectedTools = selectedTools.filter(n => n !== tool.name))
            : selectedTools.push(tool.name)
        "
      >
        <template #right-icon>
          <van-checkbox :name="tool.name" @click.stop />
          <van-tag v-if="tool.requires_write" type="warning" class="write-tag">
            {{ t('mcp.token.tools.writeBadge') }}
          </van-tag>
        </template>
      </van-cell>
    </van-checkbox-group>

    <div class="tool-picker-footer">
      <van-button round block type="primary" :loading="toolsSaving" @click="onSaveTools">
        {{ t('mcp.token.tools.save') }}
      </van-button>
    </div>
  </van-popup>
</template>

<style scoped>
.backend-mcp-card {
  margin-top: 12px;
}
.card-title {
  display: inline-flex;
  align-items: center;
  font-weight: 600;
}
.token-display {
  display: flex;
  align-items: center;
  gap: 8px;
}
.token-text {
  font-family: monospace;
  font-size: 13px;
  color: var(--text-primary);
  word-break: break-all;
}
.token-action {
  font-size: 16px;
  cursor: pointer;
  color: var(--text-secondary);
}
.warn-row {
  color: var(--van-danger-color);
}
.expire-field {
  max-width: 160px;
}
.cell-disabled {
  opacity: 0.6;
}
.anomaly-flag {
  color: var(--van-danger-color);
}
.tool-picker {
  max-height: 80vh;
  display: flex;
  flex-direction: column;
}
.tool-picker-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 16px 8px;
}
.tool-picker-title {
  font-weight: 600;
  color: var(--text-primary);
}
.tool-picker-actions {
  display: flex;
  gap: 8px;
}
.tool-picker-warning {
  margin: 0 16px 8px;
  font-size: 12px;
  color: var(--van-danger-color);
}
.tool-picker-empty {
  padding: 32px 16px;
  text-align: center;
  color: var(--text-secondary);
}
.tool-list {
  flex: 1;
  overflow-y: auto;
}
.write-tag {
  margin-left: 8px;
}
.tool-picker-footer {
  padding: 12px 16px calc(12px + env(safe-area-inset-bottom));
}
</style>
