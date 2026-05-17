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
        <draggable
          v-model="draggableConfigs"
          item-key="id"
          handle=".drag-handle"
          animation="200"
          @end="onDragEnd"
        >
          <template #item="{ element: cfg, index }">
        <div
          class="provider-card"
        >
          <!-- Card header: logo + index + title + circuit -->
          <div class="card-header">
            <div class="drag-handle" :title="t('aiConfig.dragToReorder')">
              <van-icon name="wap-nav" size="18" />
            </div>
            <div class="card-logo" :class="`logo--${cfg.provider}`">
              <!-- anthropic -->
              <svg v-if="cfg.provider === 'anthropic'" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M13.827 3.52h3.603L24 20h-3.603l-6.57-16.48zm-3.654 0H6.57L0 20h3.603l1.378-3.504h6.875L13.234 20h3.603l-6.664-16.48zm-1.32 9.99 2.244-5.716 2.244 5.717H8.853z" fill="currentColor" />
              </svg>
              <!-- openai / openai_compatible -->
              <svg v-else-if="cfg.provider === 'openai' || cfg.provider === 'openai_compatible'" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M22.282 9.821a5.985 5.985 0 0 0-.516-4.91 6.046 6.046 0 0 0-6.51-2.9A6.065 6.065 0 0 0 4.981 4.18a5.985 5.985 0 0 0-3.998 2.9 6.046 6.046 0 0 0 .743 7.097 5.98 5.98 0 0 0 .51 4.911 6.051 6.051 0 0 0 6.515 2.9A5.985 5.985 0 0 0 13.26 24a6.056 6.056 0 0 0 5.772-4.206 5.99 5.99 0 0 0 3.997-2.9 6.056 6.056 0 0 0-.747-7.073zM13.26 22.43a4.476 4.476 0 0 1-2.876-1.04l.141-.081 4.779-2.758a.795.795 0 0 0 .392-.681v-6.737l2.02 1.168a.071.071 0 0 1 .038.052v5.583a4.504 4.504 0 0 1-4.494 4.494zM3.6 18.304a4.47 4.47 0 0 1-.535-3.014l.142.085 4.783 2.759a.771.771 0 0 0 .78 0l5.843-3.369v2.332a.08.08 0 0 1-.033.062L9.74 19.95a4.5 4.5 0 0 1-6.14-1.646zM2.34 7.896a4.485 4.485 0 0 1 2.366-1.973V11.6a.766.766 0 0 0 .388.676l5.815 3.355-2.02 1.168a.076.076 0 0 1-.071 0l-4.83-2.786A4.504 4.504 0 0 1 2.34 7.872zm16.597 3.855-5.833-3.387L15.119 7.2a.076.076 0 0 1 .071 0l4.83 2.791a4.494 4.494 0 0 1-.676 8.105v-5.678a.79.79 0 0 0-.407-.667zm2.01-3.023-.141-.085-4.774-2.782a.776.776 0 0 0-.785 0L9.409 9.23V6.897a.066.066 0 0 1 .028-.061l4.83-2.787a4.5 4.5 0 0 1 6.68 4.66zm-12.64 4.135-2.02-1.164a.08.08 0 0 1-.038-.057V6.075a4.5 4.5 0 0 1 7.375-3.453l-.142.08L8.704 5.46a.795.795 0 0 0-.393.681zm1.097-2.365 2.602-1.5 2.607 1.5v2.999l-2.597 1.5-2.607-1.5z" fill="currentColor" />
              </svg>
              <!-- generic -->
              <svg v-else viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.5" />
                <path d="M12 7v5l3 3" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
              </svg>
            </div>
            <div class="card-header-info">
              <div class="card-title-row">
                <span class="card-index">{{ t('aiConfig.providerIndex', { n: index + 1 }) }}</span>
                <span class="card-name">{{ cfg.name }}</span>
                <span class="card-provider-fmt">({{ cfg.provider }})</span>
                <span v-if="cfg.circuit_open" class="circuit-badge">⚠️</span>
              </div>
            </div>
          </div>

          <!-- API Key row -->
          <div v-if="cfg.ai_api_key_masked" class="api-key-row">
            <span class="api-key-label">{{ t('aiConfig.currentApiKey') }}</span>
            <span class="api-key-value">{{ revealedKeys[cfg.id] || cfg.ai_api_key_masked }}</span>
            <button class="icon-btn" :title="t('aiConfig.copyApiKey')" @click="onCopyKey(cfg)">
              <van-icon name="description" size="16" />
            </button>
            <button
              class="icon-btn"
              :title="revealedKeys[cfg.id] ? t('aiConfig.hideApiKey') : t('aiConfig.showApiKey')"
              :disabled="revealingId === cfg.id"
              @click="onToggleReveal(cfg)"
            >
              <van-icon
                v-if="revealingId === cfg.id"
                name="loading"
                size="16"
                class="icon-spinning"
              />
              <van-icon v-else :name="revealedKeys[cfg.id] ? 'eye-o' : 'closed-eye'" size="16" />
            </button>
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
                    :class="[`cap-chip--${cap}`, { 'cap-chip--untested': !testPassedKeys.has(`${cfg.id}-${slot}`) }]"
                    :title="capShortLabel(cap)"
                  >
                    <!-- text_generation -->
                    <svg v-if="cap === 'text_generation'" width="12" height="12" viewBox="0 0 28 28" fill="none">
                      <rect x="4" y="6" width="20" height="3" rx="1.5" fill="currentColor" />
                      <rect x="4" y="12" width="16" height="3" rx="1.5" fill="currentColor" opacity="0.7" />
                      <rect x="4" y="18" width="12" height="3" rx="1.5" fill="currentColor" opacity="0.4" />
                    </svg>
                    <!-- deep_thinking -->
                    <svg v-else-if="cap === 'deep_thinking'" width="12" height="12" viewBox="0 0 28 28" fill="none">
                      <circle cx="14" cy="12" r="7" stroke="currentColor" stroke-width="2" />
                      <path d="M10.5 12C10.5 10.067 12.067 8.5 14 8.5" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
                      <circle cx="14" cy="12" r="2" fill="currentColor" />
                      <rect x="11" y="20" width="6" height="2" rx="1" fill="currentColor" />
                      <rect x="12.5" y="22" width="3" height="2" rx="1" fill="currentColor" />
                    </svg>
                    <!-- vision_understanding -->
                    <svg v-else width="12" height="12" viewBox="0 0 28 28" fill="none">
                      <path d="M4 14C4 14 7.5 7 14 7C20.5 7 24 14 24 14C24 14 20.5 21 14 21C7.5 21 4 14 4 14Z" stroke="currentColor" stroke-width="2" stroke-linejoin="round" />
                      <circle cx="14" cy="14" r="3.5" stroke="currentColor" stroke-width="2" />
                      <circle cx="14" cy="14" r="1.5" fill="currentColor" />
                    </svg>
                  </span>
                </div>
                <button
                  class="test-btn"
                  :class="{ 'test-btn--testing': testingKey === `${cfg.id}-${slot}` }"
                  :disabled="testingKey === `${cfg.id}-${slot}`"
                  @click="onTestModel(cfg.id, slot)"
                >
                  <van-icon
                    :name="testingKey === `${cfg.id}-${slot}` ? 'loading' : 'play-circle-o'"
                    size="15"
                    class="test-btn__icon"
                    :class="{ 'test-btn__icon--spinning': testingKey === `${cfg.id}-${slot}` }"
                  />
                  <span>{{ t('aiConfig.testModel') }}</span>
                </button>
              </div>
            </template>
            <div v-if="!cfg.model_id && !cfg.model_2_id && !cfg.model_3_id" class="no-models">
              {{ t('aiConfig.noModels') }}
            </div>
          </div>

          <!-- Card actions: edit / delete / reset circuit — FamilyPage style -->
          <div class="card-actions">
            <button class="action-btn action-btn--edit" @click="onEdit(cfg)">
              <van-icon name="edit" size="18" />
              <span>{{ t('common.edit') }}</span>
            </button>
            <button
              class="action-btn action-btn--danger"
              :disabled="deletingId === cfg.id"
              @click="onDelete(cfg)"
            >
              <van-icon :name="deletingId === cfg.id ? 'loading' : 'delete-o'" size="18" />
              <span>{{ t('common.delete') }}</span>
            </button>
            <button
              v-if="cfg.circuit_open"
              class="action-btn action-btn--warn"
              @click="onResetCircuit(cfg.id)"
            >
              <van-icon name="replay" size="18" />
              <span>{{ t('aiConfig.resetCircuit') }}</span>
            </button>
          </div>
        </div>
          </template>
        </draggable>
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
          :title="cfg.name"
          :value="cfg.circuit_open ? t('aiConfig.circuitOpen') : t('aiConfig.circuitNormal')"
        />
        <van-cell v-if="aiStore.configs.length === 0" :title="t('aiConfig.noProviders')" />
      </van-cell-group>
      <div class="tip">
        <van-icon name="info-o" />
        <span>{{ t('aiConfig.nonOwnerTip') }}</span>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { showToast, showConfirmDialog } from 'vant'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import draggable from 'vuedraggable'
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
const testPassedKeys = ref<Set<string>>(new Set())
const revealedKeys = ref<Record<string, string>>({})
const revealingId = ref<string | null>(null)

const draggableConfigs = computed({
  get: () => aiStore.configs,
  set: (val: ProviderConfig[]) => {
    aiStore.configs = val
  },
})

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

async function onDragEnd() {
  try {
    await aiStore.reorderConfigs(aiStore.configs.map((c) => c.id))
    showToast(t('aiConfig.saveOrder'))
  } catch {
    showToast(t('toast.operationFailed2'))
  }
}

// ── Actions ───────────────────────────────────────────────────────────────────

async function onCopyKey(cfg: ProviderConfig) {
  const text = revealedKeys.value[cfg.id] || cfg.ai_api_key_masked || ''
  try {
    await navigator.clipboard.writeText(text)
    showToast(t('toast.copied'))
  } catch {
    showToast(t('toast.operationFailed2'))
  }
}

async function onToggleReveal(cfg: ProviderConfig) {
  if (revealedKeys.value[cfg.id]) {
    delete revealedKeys.value[cfg.id]
    return
  }
  revealingId.value = cfg.id
  try {
    const res = await aiApi.revealAIKey(cfg.id)
    revealedKeys.value[cfg.id] = res.data.api_key
  } catch {
    showToast(t('aiConfig.revealFailed'))
  } finally {
    revealingId.value = null
  }
}

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
    if (res.data.connected) {
      testPassedKeys.value = new Set([...testPassedKeys.value, key])
      showToast(t('aiConfig.testSuccess'))
    } else {
      testPassedKeys.value.delete(key)
      showToast(`${t('aiConfig.testFailed')}: ${res.data.message ?? ''}`)
    }
  } catch {
    testPassedKeys.value.delete(key)
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

/* ── Drag handle ── */
.drag-handle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  color: var(--text-tertiary);
  cursor: grab;
  flex-shrink: 0;
  touch-action: none;
}

.drag-handle:active {
  cursor: grabbing;
}

/* ── Card ── */
.provider-card {
  background: var(--bg-card, var(--card-bg));
  border-radius: 16px;
  border: 1px solid var(--border-light);
  overflow: hidden;
}

/* ── Card header ── */
.card-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 14px 12px;
  border-bottom: 1px solid var(--border-light);
}

.card-logo {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: rgba(0, 0, 0, 0.05);
  color: var(--text-primary);
}
.card-logo svg {
  width: 26px;
  height: 26px;
}
.logo--anthropic {
  background: color-mix(in srgb, #d97706 10%, transparent);
  color: #d97706;
}
.logo--openai,
.logo--openai_compatible {
  background: color-mix(in srgb, #10a37f 10%, transparent);
  color: #10a37f;
}
[data-theme='dark'] .logo--anthropic {
  background: rgba(217, 119, 6, 0.15);
  color: #fbbf24;
}
[data-theme='dark'] .logo--openai,
[data-theme='dark'] .logo--openai_compatible {
  background: rgba(16, 163, 127, 0.15);
  color: #34d399;
}

.card-header-info {
  flex: 1;
  min-width: 0;
}

.card-title-row {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.card-index {
  font-size: 18px;
  font-weight: 800;
  color: var(--van-primary-color);
  letter-spacing: -0.5px;
  flex-shrink: 0;
  line-height: 1;
}

.card-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  letter-spacing: -0.2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-provider-fmt {
  font-size: 12px;
  color: var(--text-tertiary);
  font-family: monospace;
  flex-shrink: 0;
}

.circuit-badge {
  font-size: 15px;
  flex-shrink: 0;
}

/* ── API Key row ── */
.api-key-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-bottom: 1px solid var(--border-light);
}

.api-key-label {
  font-size: 12px;
  color: var(--text-secondary);
  flex-shrink: 0;
}

.api-key-value {
  flex: 1;
  min-width: 0;
  font-size: 12px;
  font-family: monospace;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.icon-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 6px;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  flex-shrink: 0;
  -webkit-tap-highlight-color: transparent;
  transition: background 0.15s;
}

.icon-btn:active {
  background: rgba(0, 0, 0, 0.05);
}

[data-theme='dark'] .icon-btn:active {
  background: rgba(255, 255, 255, 0.08);
}

.icon-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.icon-spinning {
  animation: spin 1s linear infinite;
}

/* ── Model rows ── */
.model-rows {
  padding: 10px 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.model-row {
  display: flex;
  align-items: center;
  gap: 8px;
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
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 6px;
  flex-shrink: 0;
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
.cap-chip--untested {
  background: color-mix(in srgb, #999 10%, transparent);
  color: #999;
}

/* ── Test button ── */
.test-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 8px 14px;
  min-height: 36px;
  border-radius: 8px;
  border: 1px solid var(--van-primary-color);
  background: transparent;
  color: var(--van-primary-color);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  flex-shrink: 0;
  transition: background 0.15s, opacity 0.15s;
  -webkit-tap-highlight-color: transparent;
}
.test-btn:active {
  background: color-mix(in srgb, var(--van-primary-color) 10%, transparent);
}
.test-btn--testing {
  opacity: 0.5;
  cursor: not-allowed;
  border-color: var(--text-tertiary);
  color: var(--text-tertiary);
}
.test-btn__icon--spinning {
  animation: spin 1s linear infinite;
}
@keyframes spin {
  from { transform: rotate(0deg); }
  to   { transform: rotate(360deg); }
}

.no-models {
  font-size: 13px;
  color: var(--text-secondary);
  padding: 4px 0;
}

/* ── Card actions — FamilyPage child-mgmt-actions style ── */
.card-actions {
  display: flex;
  border-top: 1px solid rgba(0, 0, 0, 0.06);
  margin: 0;
  border-radius: 0 0 16px 16px;
  overflow: hidden;
}

[data-theme='dark'] .card-actions {
  border-color: rgba(255, 255, 255, 0.08);
}

.action-btn {
  flex: 1;
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: center;
  gap: 5px;
  padding: 10px 4px;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  font-size: 12px;
  cursor: pointer;
  transition: background 0.15s;
  position: relative;
  -webkit-tap-highlight-color: transparent;
}

.action-btn + .action-btn::before {
  content: '';
  position: absolute;
  left: 0;
  top: 20%;
  height: 60%;
  width: 1px;
  background: rgba(0, 0, 0, 0.06);
}

[data-theme='dark'] .action-btn + .action-btn::before {
  background: rgba(255, 255, 255, 0.08);
}

.action-btn:active {
  background: rgba(0, 0, 0, 0.04);
}

[data-theme='dark'] .action-btn:active {
  background: rgba(255, 255, 255, 0.06);
}

.action-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.action-btn--edit {
  color: #4f46e5;
}

[data-theme='dark'] .action-btn--edit {
  color: #818cf8;
}

.action-btn--danger {
  color: #ee0a24;
}

.action-btn--warn {
  color: #ff976a;
}

/* ── Page actions ── */
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
