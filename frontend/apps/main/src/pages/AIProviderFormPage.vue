<template>
  <div class="provider-form-page">
    <PageHeader
      :title="isEdit ? t('aiConfig.editProviderTitle') : t('aiConfig.addProviderTitle')"
    />

    <van-cell-group inset class="section">
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
        :placeholder="t('aiConfig.apiKeyPlaceholder')"
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
    <div v-for="slot in [1, 2, 3]" :key="slot" class="model-section">
      <div class="model-section__title">{{ t('aiConfig.modelN', { n: slot }) }}</div>
      <van-cell-group inset>
        <van-field
          v-model="formModels[slot - 1].id"
          :label="t('aiConfig.modelId')"
          :placeholder="t('aiConfig.modelIdPlaceholder')"
          clearable
        />
        <van-cell
          :title="t('aiConfig.capabilities')"
          is-link
          @click="openCapPicker(slot - 1)"
        >
          <template #value>
            <div class="cap-preview">
              <span
                v-if="formModels[slot - 1].capabilities.length === 0"
                class="cap-preview__empty"
              >{{ t('aiConfig.emptySlot') }}</span>
              <template v-else>
                <span
                  v-for="cap in formModels[slot - 1].capabilities"
                  :key="cap"
                  class="cap-preview__badge"
                  :class="`cap-preview__badge--${cap}`"
                >{{ capLabel(cap) }}</span>
              </template>
            </div>
          </template>
        </van-cell>
      </van-cell-group>
    </div>

    <div class="form-actions">
      <van-button block type="primary" :loading="saving" @click="onSave">
        {{ t('common.save') }}
      </van-button>
    </div>

    <!-- Provider type picker -->
    <van-popup v-model:show="showProviderPicker" round position="bottom">
      <van-picker
        :columns="providerOptions"
        @confirm="onProviderConfirm"
        @cancel="showProviderPicker = false"
      />
    </van-popup>

    <!-- Capability picker sheet -->
    <CapabilityPickerSheet
      v-model:show="showCapPicker"
      :model-value="activeSlotCaps"
      @update:model-value="onCapsUpdate"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { useAIStore } from '@/stores/ai'
import * as aiApi from '@/api/ai'
import type { ProviderConfig } from '@/api/ai'
import PageHeader from '@/components/common/PageHeader.vue'
import CapabilityPickerSheet from '@/components/ai/CapabilityPickerSheet.vue'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const aiStore = useAIStore()

const configId = computed(() => {
  const v = route.params.id
  return Array.isArray(v) ? v[0] : v
})
const isEdit = computed(() => !!configId.value)

const saving = ref(false)
const showProviderPicker = ref(false)
const showCapPicker = ref(false)
const activeSlotIndex = ref(0)

interface ModelSlot {
  id: string
  capabilities: string[]
}

const form = reactive({
  provider_name: '',
  provider: 'openai_compatible',
  api_key: '',
  base_url: '',
  timeout_seconds: '60',
})

const formModels = reactive<ModelSlot[]>([
  { id: '', capabilities: ['text_generation'] },
  { id: '', capabilities: [] },
  { id: '', capabilities: [] },
])

const activeSlotCaps = computed(() => formModels[activeSlotIndex.value].capabilities)

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

function capLabel(cap: string): string {
  if (cap === 'text_generation') return t('aiConfig.capabilityText')
  if (cap === 'deep_thinking') return t('aiConfig.capabilityThinking')
  if (cap === 'vision_understanding') return t('aiConfig.capabilityVision')
  return cap
}

function openCapPicker(slotIndex: number) {
  activeSlotIndex.value = slotIndex
  showCapPicker.value = true
}

function onCapsUpdate(caps: string[]) {
  formModels[activeSlotIndex.value].capabilities = caps
}

function onProviderConfirm({ selectedOptions }: { selectedOptions: Array<{ text: string; value: string }> }) {
  form.provider = selectedOptions[0].value
  showProviderPicker.value = false
}

function loadConfig(cfg: ProviderConfig) {
  form.provider_name = cfg.provider_name
  form.provider = cfg.provider
  form.api_key = ''
  form.base_url = cfg.base_url || ''
  form.timeout_seconds = String(cfg.timeout_seconds)
  formModels[0].id = cfg.model_id || ''
  formModels[0].capabilities = [...cfg.model_1_capabilities]
  formModels[1].id = cfg.model_2_id || ''
  formModels[1].capabilities = [...cfg.model_2_capabilities]
  formModels[2].id = cfg.model_3_id || ''
  formModels[2].capabilities = [...cfg.model_3_capabilities]
}

async function onSave() {
  if (!form.provider_name.trim()) {
    showToast(t('aiConfig.providerNamePlaceholder'))
    return
  }

  saving.value = true
  try {
    if (isEdit.value && configId.value) {
      const payload: aiApi.ProviderConfigUpdate = {
        provider_name: form.provider_name,
        provider: form.provider,
        base_url: form.base_url || null,
        timeout_seconds: parseInt(form.timeout_seconds) || 60,
        model_id: formModels[0].id || null,
        model_2_id: formModels[1].id || null,
        model_3_id: formModels[2].id || null,
        model_1_capabilities: formModels[0].capabilities,
        model_2_capabilities: formModels[1].capabilities,
        model_3_capabilities: formModels[2].capabilities,
      }
      if (form.api_key.trim()) payload.ai_api_key = form.api_key.trim()
      await aiApi.updateProviderConfig(configId.value, payload)
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
        model_1_capabilities: formModels[0].capabilities,
        model_2_capabilities: formModels[1].capabilities,
        model_3_capabilities: formModels[2].capabilities,
      }
      await aiApi.createAIConfig(payload)
    }
    showToast(t('toast.aiConfigSaved'))
    await aiStore.fetchConfigs()
    router.back()
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : t('toast.saveFailedGeneric')
    showToast(msg)
  } finally {
    saving.value = false
  }
}

let unmounted = false
onUnmounted(() => { unmounted = true })

onMounted(async () => {
  if (isEdit.value && configId.value) {
    let cfg = aiStore.configs.find((c) => c.id === configId.value)
    if (!cfg) {
      await aiStore.fetchConfigs()
      if (unmounted) return
      cfg = aiStore.configs.find((c) => c.id === configId.value)
    }
    if (cfg) {
      loadConfig(cfg)
    } else {
      showToast(t('toast.operationFailed2'))
      router.replace({ name: 'AIConfig' })
    }
  }
})
</script>

<style scoped>
.provider-form-page {
  background: var(--bg-secondary);
  min-height: 100vh;
  padding-bottom: 32px;
}

.section {
  margin-top: 12px;
}

.model-section {
  margin-top: 16px;
}

.model-section__title {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
  padding: 0 32px 6px;
  letter-spacing: 0.2px;
  text-transform: uppercase;
}

.cap-preview {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  justify-content: flex-end;
}

.cap-preview__empty {
  font-size: 13px;
  color: var(--text-secondary);
}

.cap-preview__badge {
  font-size: 11px;
  font-weight: 500;
  padding: 2px 7px;
  border-radius: 4px;
  letter-spacing: 0.1px;
}

.cap-preview__badge--text_generation {
  background: color-mix(in srgb, #4f8ef7 15%, transparent);
  color: #4f8ef7;
}

.cap-preview__badge--deep_thinking {
  background: color-mix(in srgb, #9b59f7 15%, transparent);
  color: #9b59f7;
}

.cap-preview__badge--vision_understanding {
  background: color-mix(in srgb, #2ec4b6 15%, transparent);
  color: #2ec4b6;
}

.form-actions {
  padding: 24px 16px 0;
}
</style>
