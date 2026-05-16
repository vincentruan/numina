<template>
  <div class="ai-config-page">
    <PageHeader :title="t('aiConfig.pageTitle')" />

    <!-- Owner view -->
    <template v-if="isOwner">
      <div v-if="aiStore.configs.length === 0" class="empty-state">
        <van-icon name="setting-o" size="40" color="var(--text-secondary)" />
        <p>{{ t('aiConfig.noProviders') }}</p>
      </div>

      <div v-else class="provider-list">
        <div
          v-for="(cfg, index) in aiStore.configs"
          :key="cfg.id"
          class="provider-card"
        >
          <!-- Card top: index + name + circuit badge -->
          <div class="card-top">
            <span class="card-index">{{ t('aiConfig.providerIndex', { n: index + 1 }) }}</span>
            <span class="card-name">{{ cfg.provider_name }}</span>
            <span v-if="cfg.circuit_open" class="circuit-badge">⚠️</span>
          </div>

          <!-- Model rows -->
          <div class="model-rows">
            <template v-for="slot in [1, 2, 3]" :key="slot">
              <div v-if="getModelId(cfg, slot)" class="model-row">
                <span class="model-id">{{ getModelId(cfg, slot) }}</span>
                <div class="model-caps">
                  <span
                    v-for="cap in getCapabilities(cfg, slot)"
                    :key="cap"
                    class="cap-chip"
                    :class="`cap-chip--${cap}`"
                  >
                    <component :is="capIcon(cap)" class="cap-chip__icon" />
                    <span class="cap-chip__label">{{ capShortLabel(cap) }}</span>
                  </span>
                </div>
                <van-button
                  size="mini"
                  plain
                  :loading="testingKey === `${cfg.id}-${slot}`"
                  class="test-btn"
                  @click="onTestModel(cfg.id, slot)"
                >
                  {{ t('aiConfig.testModel') }}
                </van-button>
              </div>
            </template>
            <div v-if="!cfg.model_id && !cfg.model_2_id && !cfg.model_3_id" class="no-models">
              {{ t('aiConfig.noModels') }}
            </div>
          </div>

          <!-- Card actions -->
          <div class="card-actions">
            <van-button
              size="mini"
              plain
              icon="edit"
              @click="onEdit(cfg)"
            >
              {{ t('common.edit') }}
            </van-button>
            <van-button
              size="mini"
              type="danger"
              plain
              icon="delete-o"
              :loading="deletingId === cfg.id"
              @click="onDelete(cfg)"
            >
              {{ t('common.delete') }}
            </van-button>
            <van-button
              v-if="cfg.circuit_open"
              size="mini"
              type="warning"
              plain
              @click="onResetCircuit(cfg.id)"
            >
              {{ t('aiConfig.resetCircuit') }}
            </van-button>
          </div>
        </div>
      </div>

      <!-- Add provider button -->
      <div class="page-actions">
        <van-button block plain icon="plus" @click="onAdd">
          {{ t('aiConfig.addProvider') }}
        </van-button>
      </div>
    </template>

    <!-- Non-owner view -->
    <template v-else>
      <van-cell-group inset class="section">
        <van-cell
          v-for="cfg in aiStore.configs"
          :key="cfg.id"
          :title="cfg.provider_name"
          :value="cfg.circuit_open ? t('aiConfig.circuitOpen') : t('aiConfig.circuitNormal')"
        />
        <van-cell v-if="aiStore.configs.length === 0" :title="t('aiConfig.noProviders')" />
      </van-cell-group>
      <div class="tip">
        <van-icon name="info-o" />
        <span>{{ t('aiConfig.nonOwnerTip') }}</span>
      </div>
    </template>

    <!-- Test result toast is handled inline; no extra popup needed -->
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, defineComponent, h } from 'vue'
import { showToast, showConfirmDialog } from 'vant'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useAIStore } from '@/stores/ai'
import * as aiApi from '@/api/ai'
import type { ProviderConfig } from '@/api/ai'
import PageHeader from '@/components/common/PageHeader.vue'

const { t } = useI18n()
const router = useRouter()
const authStore = useAuthStore()
const aiStore = useAIStore()

const isOwner = computed(() => authStore.user?.role === 'owner')
const deletingId = ref<string | null>(null)
const testingKey = ref<string | null>(null)

// ── SVG capability icons ──────────────────────────────────────────────────────

const TextSvg = defineComponent({
  render: () =>
    h('svg', { width: 12, height: 12, viewBox: '0 0 28 28', fill: 'none' }, [
      h('rect', { x: 4, y: 6, width: 20, height: 3, rx: 1.5, fill: 'currentColor' }),
      h('rect', { x: 4, y: 12, width: 16, height: 3, rx: 1.5, fill: 'currentColor', opacity: 0.7 }),
      h('rect', { x: 4, y: 18, width: 12, height: 3, rx: 1.5, fill: 'currentColor', opacity: 0.4 }),
    ]),
})

const ThinkingSvg = defineComponent({
  render: () =>
    h('svg', { width: 12, height: 12, viewBox: '0 0 28 28', fill: 'none' }, [
      h('circle', { cx: 14, cy: 12, r: 7, stroke: 'currentColor', 'stroke-width': 2 }),
      h('path', { d: 'M10.5 12C10.5 10.067 12.067 8.5 14 8.5', stroke: 'currentColor', 'stroke-width': 2, 'stroke-linecap': 'round' }),
      h('circle', { cx: 14, cy: 12, r: 2, fill: 'currentColor' }),
      h('rect', { x: 11, y: 20, width: 6, height: 2, rx: 1, fill: 'currentColor' }),
      h('rect', { x: 12.5, y: 22, width: 3, height: 2, rx: 1, fill: 'currentColor' }),
    ]),
})

const VisionSvg = defineComponent({
  render: () =>
    h('svg', { width: 12, height: 12, viewBox: '0 0 28 28', fill: 'none' }, [
      h('path', { d: 'M4 14C4 14 7.5 7 14 7C20.5 7 24 14 24 14C24 14 20.5 21 14 21C7.5 21 4 14 4 14Z', stroke: 'currentColor', 'stroke-width': 2, 'stroke-linejoin': 'round' }),
      h('circle', { cx: 14, cy: 14, r: 3.5, stroke: 'currentColor', 'stroke-width': 2 }),
      h('circle', { cx: 14, cy: 14, r: 1.5, fill: 'currentColor' }),
    ]),
})

function capIcon(cap: string) {
  if (cap === 'text_generation') return TextSvg
  if (cap === 'deep_thinking') return ThinkingSvg
  return VisionSvg
}

function capShortLabel(cap: string): string {
  if (cap === 'text_generation') return t('aiConfig.capabilityText')
  if (cap === 'deep_thinking') return t('aiConfig.capabilityThinking')
  return t('aiConfig.capabilityVision')
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function getModelId(cfg: ProviderConfig, slot: number): string | null {
  if (slot === 1) return cfg.model_id
  if (slot === 2) return cfg.model_2_id
  if (slot === 3) return cfg.model_3_id
  return null
}

function getCapabilities(cfg: ProviderConfig, slot: number): string[] {
  if (slot === 1) return cfg.model_1_capabilities
  if (slot === 2) return cfg.model_2_capabilities
  return cfg.model_3_capabilities
}

// ── Actions ───────────────────────────────────────────────────────────────────

function onAdd() {
  router.push({ name: 'AIProviderCreate' })
}

function onEdit(cfg: ProviderConfig) {
  router.push({ name: 'AIProviderEdit', params: { id: cfg.id } })
}

async function onDelete(cfg: ProviderConfig) {
  try {
    await showConfirmDialog({
      title: t('aiConfig.deleteProvider'),
      message: t('aiConfig.confirmDeleteProvider', { name: cfg.provider_name }),
    })
    deletingId.value = cfg.id
    await aiApi.deleteAIConfig(cfg.id)
    await aiStore.fetchConfigs()
    showToast(t('toast.deleted'))
  } catch {
    // user cancelled
  } finally {
    deletingId.value = null
  }
}

async function onResetCircuit(id: string) {
  try {
    await aiStore.resetCircuit(id)
    showToast(t('toast.aiConfigSaved'))
  } catch {
    showToast(t('toast.operationFailed2'))
  }
}

async function onTestModel(configId: string, slot: number) {
  const key = `${configId}-${slot}`
  testingKey.value = key
  try {
    const res = await aiApi.testProviderConfig(configId)
    showToast(res.data.connected ? t('aiConfig.testSuccess') : `${t('aiConfig.testFailed')}: ${res.data.message ?? ''}`)
  } catch {
    showToast(t('aiConfig.testFailed'))
  } finally {
    testingKey.value = null
  }
}

onMounted(async () => {
  await aiStore.fetchConfigs()
})
</script>

<style scoped>
.ai-config-page {
  background: var(--bg-secondary);
  min-height: 100vh;
  padding-bottom: 24px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 48px 20px;
  color: var(--text-secondary);
  font-size: 14px;
}

.provider-list {
  padding: 12px 16px 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.provider-card {
  background: var(--bg-card);
  border-radius: 12px;
  border: 1px solid var(--border-light);
  overflow: hidden;
}

.card-top {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 14px 10px;
  border-bottom: 1px solid var(--border-light);
}

.card-index {
  font-size: 11px;
  font-weight: 600;
  color: var(--van-primary-color);
  background: color-mix(in srgb, var(--van-primary-color) 10%, transparent);
  padding: 2px 7px;
  border-radius: 4px;
  letter-spacing: 0.2px;
  flex-shrink: 0;
}

.card-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  flex: 1;
  letter-spacing: -0.2px;
}

.circuit-badge {
  font-size: 15px;
}

.model-rows {
  padding: 10px 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.model-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.model-id {
  font-size: 12px;
  color: var(--text-secondary);
  font-family: monospace;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.model-caps {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
}

.cap-chip {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
}

.cap-chip__icon {
  flex-shrink: 0;
}

.cap-chip__label {
  white-space: nowrap;
}

.cap-chip--text_generation {
  background: color-mix(in srgb, #4f8ef7 12%, transparent);
  color: #4f8ef7;
}

.cap-chip--deep_thinking {
  background: color-mix(in srgb, #9b59f7 12%, transparent);
  color: #9b59f7;
}

.cap-chip--vision_understanding {
  background: color-mix(in srgb, #2ec4b6 12%, transparent);
  color: #2ec4b6;
}

.test-btn {
  flex-shrink: 0;
}

.no-models {
  font-size: 13px;
  color: var(--text-secondary);
  padding: 4px 0;
}

.card-actions {
  display: flex;
  gap: 8px;
  padding: 10px 14px 12px;
  border-top: 1px solid var(--border-light);
  flex-wrap: wrap;
}

.page-actions {
  padding: 16px 16px 0;
}

.section {
  margin-top: 12px;
}

.tip {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 16px;
  color: var(--text-secondary);
  font-size: 13px;
}
</style>
