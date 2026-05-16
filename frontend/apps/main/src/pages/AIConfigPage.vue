<template>
  <div class="ai-config-page">
    <PageHeader :title="t('aiConfig.pageTitle')" />

    <!-- Owner view -->
    <template v-if="isOwner">
      <!-- Provider list -->
      <div v-if="aiStore.configs.length === 0" class="empty-state">
        <van-icon name="info-o" size="40" />
        <p>{{ t('aiConfig.noProviders') }}</p>
      </div>

      <draggable
        v-else
        v-model="localConfigs"
        item-key="id"
        handle=".drag-handle"
        ghost-class="ghost"
        @end="onDragEnd"
      >
        <template #item="{ element: cfg }">
          <div class="provider-card">
            <!-- Card header -->
            <div class="card-header">
              <span class="drag-handle">⠿</span>
              <span class="provider-name">{{ cfg.provider_name }}</span>
              <span v-if="cfg.circuit_open" class="circuit-badge">⚠️</span>
              <van-button
                size="mini"
                type="danger"
                plain
                :loading="deletingId === cfg.id"
                @click="onDeleteProvider(cfg)"
              >
                {{ t('common.delete') }}
              </van-button>
            </div>

            <!-- Card body -->
            <div class="card-body">
              <!-- Provider type -->
              <van-cell-group inset>
                <van-cell :title="t('aiConfig.aiProvider')" :value="providerLabel(cfg.provider)" />
                <van-cell :title="t('aiConfig.apiKey')" :value="cfg.ai_api_key_masked || '—'" />
                <van-cell :title="t('aiConfig.baseUrl')" :value="cfg.base_url || '—'" />
              </van-cell-group>

              <!-- Model slots -->
              <div class="model-slots">
                <div v-for="slot in [1, 2, 3]" :key="slot" class="model-slot">
                  <div class="slot-header">
                    <span class="slot-label">{{ t('aiConfig.modelN', { n: slot }) }}</span>
                    <span class="slot-model-id">{{ getModelId(cfg, slot) || t('aiConfig.emptySlot') }}</span>
                  </div>
                  <div class="capability-badges">
                    <span
                      class="cap-badge"
                      :class="hasCapability(cfg, slot, 'text_generation') ? 'active' : 'inactive'"
                      :aria-label="t('aiConfig.capabilityText')"
                    >📝</span>
                    <span
                      class="cap-badge"
                      :class="hasCapability(cfg, slot, 'deep_thinking') ? 'active' : 'inactive'"
                      :aria-label="t('aiConfig.capabilityThinking')"
                    >🧠</span>
                    <span
                      class="cap-badge"
                      :class="hasCapability(cfg, slot, 'vision_understanding') ? 'active' : 'inactive'"
                      :aria-label="t('aiConfig.capabilityVision')"
                    >🖼️</span>
                  </div>
                </div>
              </div>

              <!-- Circuit status + actions -->
              <div class="card-footer">
                <div class="status-row">
                  <span class="circuit-status">
                    {{ cfg.circuit_open ? t('aiConfig.circuitOpen') : t('aiConfig.circuitNormal') }}
                  </span>
                  <span v-if="cfg.failure_count > 0" class="failure-count">
                    {{ t('aiConfig.failureCount', { count: cfg.failure_count }) }}
                  </span>
                </div>
                <van-button
                  v-if="cfg.circuit_open"
                  size="mini"
                  type="warning"
                  plain
                  @click="onResetCircuit(cfg.id)"
                >
                  {{ t('aiConfig.resetCircuit') }}
                </van-button>
                <van-button
                  size="mini"
                  plain
                  :loading="testingId === cfg.id"
                  @click="onTestProvider(cfg.id)"
                >
                  {{ t('aiConfig.testConnection') }}
                </van-button>
                <van-button
                  size="mini"
                  plain
                  @click="openEditProvider(cfg)"
                >
                  {{ t('common.edit') }}
                </van-button>
              </div>
            </div>
          </div>
        </template>
      </draggable>

      <!-- Save order button -->
      <div v-if="orderChanged" class="actions">
        <van-button block type="primary" :loading="savingOrder" @click="onSaveOrder">
          {{ t('aiConfig.saveOrder') }}
        </van-button>
      </div>

      <!-- Add provider button -->
      <div class="actions">
        <van-button block plain icon="plus" @click="openAddProvider">
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

    <!-- Add/Edit Provider Popup -->
    <van-popup
      v-model:show="showProviderForm"
      round
      position="bottom"
      :style="{ height: '90%' }"
    >
      <div class="provider-form">
        <div class="form-header">
          <h3>{{ editingConfig ? t('aiConfig.editProvider') : t('aiConfig.addProvider') }}</h3>
          <van-icon name="cross" size="20" @click="showProviderForm = false" />
        </div>

        <van-cell-group inset>
          <van-field
            v-model="form.provider_name"
            :label="t('aiConfig.providerName')"
            :placeholder="t('aiConfig.providerNamePlaceholder')"
          />
          <van-cell
            :title="t('aiConfig.aiProvider')"
            :value="providerLabel(form.provider)"
            is-link
            @click="showProviderPicker = true"
          />
          <van-field
            v-model="form.api_key"
            :label="t('aiConfig.apiKey')"
            :placeholder="editingConfig ? t('aiConfig.apiKeyPlaceholder') : t('aiConfig.apiKeyPlaceholder')"
            type="password"
            autocomplete="off"
          />
          <van-field
            v-model="form.base_url"
            :label="t('aiConfig.baseUrl')"
            :placeholder="t('aiConfig.baseUrlPlaceholderOpenAI')"
            clearable
          />
          <van-field
            v-model="form.timeout_seconds"
            :label="t('aiConfig.apiTimeout')"
            :placeholder="t('aiConfig.timeoutPlaceholder')"
            type="digit"
          />
        </van-cell-group>

        <!-- Model slots -->
        <div v-for="slot in [1, 2, 3]" :key="slot" class="model-slot-form">
          <div class="slot-title">{{ t('aiConfig.modelN', { n: slot }) }}</div>
          <van-cell-group inset>
            <van-field
              v-model="formModels[slot - 1].id"
              :label="t('aiConfig.modelId')"
              :placeholder="t('aiConfig.modelIdPlaceholder')"
              clearable
            />
            <van-cell :title="t('aiConfig.capabilities')">
              <template #value>
                <div class="cap-checkboxes">
                  <van-checkbox
                    v-model="formModels[slot - 1].cap_text"
                    shape="square"
                    icon-size="18px"
                  >📝</van-checkbox>
                  <van-checkbox
                    v-model="formModels[slot - 1].cap_thinking"
                    shape="square"
                    icon-size="18px"
                  >🧠</van-checkbox>
                  <van-checkbox
                    v-model="formModels[slot - 1].cap_vision"
                    shape="square"
                    icon-size="18px"
                  >🖼️</van-checkbox>
                </div>
              </template>
            </van-cell>
          </van-cell-group>
        </div>

        <div class="form-actions">
          <van-button block type="primary" :loading="formSaving" @click="onSaveProvider">
            {{ t('common.save') }}
          </van-button>
        </div>
      </div>
    </van-popup>

    <!-- Provider type picker -->
    <van-popup v-model:show="showProviderPicker" round position="bottom">
      <van-picker
        :columns="providerOptions"
        @confirm="onProviderConfirm"
        @cancel="showProviderPicker = false"
      />
    </van-popup>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { showToast, showConfirmDialog } from 'vant'
import { useI18n } from 'vue-i18n'
import draggable from 'vuedraggable'
import { useAuthStore } from '@/stores/auth'
import { useAIStore } from '@/stores/ai'
import * as aiApi from '@/api/ai'
import type { ProviderConfig } from '@/api/ai'
import PageHeader from '@/components/common/PageHeader.vue'

const { t } = useI18n()
const authStore = useAuthStore()
const aiStore = useAIStore()

const isOwner = computed(() => authStore.user?.role === 'owner')

// Local copy of configs for drag-and-drop
const localConfigs = ref<ProviderConfig[]>([])
const originalOrder = ref<string[]>([])
const orderChanged = computed(() => {
  const current = localConfigs.value.map((c) => c.id)
  return current.length === originalOrder.value.length && current.some((id, i) => id !== originalOrder.value[i])
})

const savingOrder = ref(false)
const deletingId = ref<string | null>(null)
const testingId = ref<string | null>(null)

// Provider form state
const showProviderForm = ref(false)
const editingConfig = ref<ProviderConfig | null>(null)
const formSaving = ref(false)
const showProviderPicker = ref(false)

const form = reactive({
  provider_name: '',
  provider: 'anthropic',
  api_key: '',
  base_url: '',
  timeout_seconds: '60',
})

const formModels = reactive([
  { id: '', cap_text: true, cap_thinking: false, cap_vision: false },
  { id: '', cap_text: false, cap_thinking: false, cap_vision: false },
  { id: '', cap_text: false, cap_thinking: false, cap_vision: false },
])

const providerOptions = [
  { text: `💬 ${t('aiConfig.providerAnthropic')}`, value: 'anthropic' },
  { text: `🤖 ${t('aiConfig.providerOpenAI')}`, value: 'openai' },
  { text: `🔌 ${t('aiConfig.providerOpenAICompatible')}`, value: 'openai_compatible' },
]

function providerLabel(provider: string): string {
  if (provider === 'anthropic') return `💬 ${t('aiConfig.providerAnthropic')}`
  if (provider === 'openai') return `🤖 ${t('aiConfig.providerOpenAI')}`
  if (provider === 'openai_compatible') return `🔌 ${t('aiConfig.providerOpenAICompatible')}`
  return provider
}

function getModelId(cfg: ProviderConfig, slot: number): string | null {
  if (slot === 1) return cfg.model_id
  if (slot === 2) return cfg.model_2_id
  if (slot === 3) return cfg.model_3_id
  return null
}

function hasCapability(cfg: ProviderConfig, slot: number, cap: string): boolean {
  const caps = slot === 1 ? cfg.model_1_capabilities : slot === 2 ? cfg.model_2_capabilities : cfg.model_3_capabilities
  return caps.includes(cap)
}

function onProviderConfirm({ selectedOptions }: { selectedOptions: Array<{ text: string; value: string }> }) {
  form.provider = selectedOptions[0].value
  showProviderPicker.value = false
}

function openAddProvider() {
  editingConfig.value = null
  form.provider_name = ''
  form.provider = 'anthropic'
  form.api_key = ''
  form.base_url = ''
  form.timeout_seconds = '60'
  formModels.forEach((m) => {
    m.id = ''
    m.cap_text = false
    m.cap_thinking = false
    m.cap_vision = false
  })
  formModels[0].cap_text = true
  showProviderForm.value = true
}

function openEditProvider(cfg: ProviderConfig) {
  editingConfig.value = cfg
  form.provider_name = cfg.provider_name
  form.provider = cfg.provider
  form.api_key = ''
  form.base_url = cfg.base_url || ''
  form.timeout_seconds = String(cfg.timeout_seconds)
  formModels[0].id = cfg.model_id || ''
  formModels[0].cap_text = cfg.model_1_capabilities.includes('text_generation')
  formModels[0].cap_thinking = cfg.model_1_capabilities.includes('deep_thinking')
  formModels[0].cap_vision = cfg.model_1_capabilities.includes('vision_understanding')
  formModels[1].id = cfg.model_2_id || ''
  formModels[1].cap_text = cfg.model_2_capabilities.includes('text_generation')
  formModels[1].cap_thinking = cfg.model_2_capabilities.includes('deep_thinking')
  formModels[1].cap_vision = cfg.model_2_capabilities.includes('vision_understanding')
  formModels[2].id = cfg.model_3_id || ''
  formModels[2].cap_text = cfg.model_3_capabilities.includes('text_generation')
  formModels[2].cap_thinking = cfg.model_3_capabilities.includes('deep_thinking')
  formModels[2].cap_vision = cfg.model_3_capabilities.includes('vision_understanding')
  showProviderForm.value = true
}

async function onSaveProvider() {
  formSaving.value = true
  try {
    const caps1: string[] = []
    if (formModels[0].cap_text) caps1.push('text_generation')
    if (formModels[0].cap_thinking) caps1.push('deep_thinking')
    if (formModels[0].cap_vision) caps1.push('vision_understanding')
    const caps2: string[] = []
    if (formModels[1].cap_text) caps2.push('text_generation')
    if (formModels[1].cap_thinking) caps2.push('deep_thinking')
    if (formModels[1].cap_vision) caps2.push('vision_understanding')
    const caps3: string[] = []
    if (formModels[2].cap_text) caps3.push('text_generation')
    if (formModels[2].cap_thinking) caps3.push('deep_thinking')
    if (formModels[2].cap_vision) caps3.push('vision_understanding')

    if (editingConfig.value) {
      const payload: aiApi.ProviderConfigUpdate = {
        provider_name: form.provider_name,
        provider: form.provider,
        base_url: form.base_url || null,
        timeout_seconds: parseInt(form.timeout_seconds) || 60,
        model_id: formModels[0].id || null,
        model_2_id: formModels[1].id || null,
        model_3_id: formModels[2].id || null,
        model_1_capabilities: caps1,
        model_2_capabilities: caps2,
        model_3_capabilities: caps3,
      }
      if (form.api_key.trim()) payload.ai_api_key = form.api_key.trim()
      await aiApi.updateProviderConfig(editingConfig.value.id, payload)
      showToast(t('toast.aiConfigSaved'))
    } else {
      const payload: aiApi.ProviderConfigCreate = {
        name: form.provider_name,
        provider: form.provider,
        ai_api_key: form.api_key.trim() || undefined,
        base_url: form.base_url || undefined,
        timeout_seconds: parseInt(form.timeout_seconds) || 60,
        model_id: formModels[0].id || undefined,
        model_2_id: formModels[1].id || undefined,
        model_3_id: formModels[2].id || undefined,
        model_1_capabilities: caps1,
        model_2_capabilities: caps2,
        model_3_capabilities: caps3,
      }
      await aiApi.createAIConfig(payload)
      showToast(t('toast.aiConfigSaved'))
    }
    await aiStore.fetchConfigs()
    showProviderForm.value = false
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : t('toast.saveFailedGeneric')
    showToast(msg)
  } finally {
    formSaving.value = false
  }
}

async function onDeleteProvider(cfg: ProviderConfig) {
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
    // user cancelled or error
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

async function onTestProvider(id: string) {
  testingId.value = id
  try {
    const res = await aiApi.testAIConfig(id)
    const connected = res.data.connected
    showToast(connected ? t('toast.aiConnectionSuccess') : `❌ ${res.data.message || t('toast.aiConnectionFailed')}`)
  } catch {
    showToast(t('toast.aiTestFailed'))
  } finally {
    testingId.value = null
  }
}

function onDragEnd() {
  // Local order updated, user needs to click save
}

async function onSaveOrder() {
  savingOrder.value = true
  try {
    const order = localConfigs.value.map((c) => c.id)
    await aiStore.reorderConfigs(order)
    showToast(t('toast.aiConfigSaved'))
  } catch {
    showToast(t('toast.operationFailed2'))
  } finally {
    savingOrder.value = false
  }
}

onMounted(async () => {
  await aiStore.fetchConfigs()
  localConfigs.value = [...aiStore.configs]
  originalOrder.value = aiStore.configs.map((c) => c.id)
})

watch(() => aiStore.configs, (newConfigs) => {
  localConfigs.value = [...newConfigs]
  originalOrder.value = newConfigs.map((c) => c.id)
})
</script>

<style scoped>
.ai-config-page {
  background: var(--bg-secondary);
  min-height: 100vh;
  padding-bottom: 20px;
}

.section {
  margin-top: 12px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 40px 20px;
  color: var(--text-secondary);
  font-size: 14px;
}

.provider-card {
  background: var(--bg-card);
  border-radius: 12px;
  margin: 12px 16px;
  overflow: hidden;
  border: 1px solid var(--border-light);
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: var(--bg-primary);
  border-bottom: 1px solid var(--border-light);
}

.drag-handle {
  cursor: grab;
  font-size: 20px;
  color: var(--text-secondary);
  padding: 8px;
  user-select: none;
}

.provider-name {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  flex: 1;
}

.circuit-badge {
  font-size: 16px;
}

.card-body {
  padding: 12px 0;
}

.model-slots {
  padding: 0 16px;
  margin-top: 8px;
}

.model-slot {
  padding: 8px 0;
  border-bottom: 1px solid var(--border-light);
}

.model-slot:last-child {
  border-bottom: none;
}

.slot-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.slot-label {
  font-size: 14px;
  color: var(--text-secondary);
}

.slot-model-id {
  font-size: 14px;
  color: var(--text-primary);
  word-break: break-all;
}

.capability-badges {
  display: flex;
  gap: 8px;
}

.cap-badge {
  font-size: 18px;
  transition: opacity 0.2s, filter 0.2s;
}

.cap-badge.active {
  opacity: 1;
}

.cap-badge.inactive {
  opacity: 0.4;
  filter: grayscale(100%);
}

.card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-top: 1px solid var(--border-light);
}

.status-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.circuit-status {
  font-size: 14px;
  color: var(--text-primary);
}

.failure-count {
  font-size: 12px;
  color: var(--text-secondary);
}

.actions {
  padding: 16px 16px 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.tip {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 16px;
  color: var(--text-secondary);
  font-size: 13px;
}

/* Provider form popup */
.provider-form {
  padding: 20px;
  max-height: 90vh;
  overflow-y: auto;
}

.form-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.form-header h3 {
  font-size: 18px;
  font-weight: 600;
}

.model-slot-form {
  margin-top: 16px;
}

.slot-title {
  font-size: 15px;
  font-weight: 500;
  margin-bottom: 8px;
  padding-left: 16px;
}

.cap-checkboxes {
  display: flex;
  gap: 12px;
}

.form-actions {
  margin-top: 24px;
}

/* Ghost class for drag */
.ghost {
  opacity: 0.5;
  background: var(--bg-secondary);
}
</style>