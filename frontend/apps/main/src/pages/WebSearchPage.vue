<!-- frontend/apps/main/src/pages/WebSearchPage.vue -->
<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { showToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@numina/auth'
import draggable from 'vuedraggable'
import {
  getWebSearchTemplates,
  getWebSearchProviders,
  enableWebSearchProvider,
  disableWebSearchProvider,
  updateWebSearchProvider,
} from '@/api/webSearch'
import type { WebSearchProvider, WebSearchProviderTemplate } from '@/types/webSearch'

const { t } = useI18n()
const router = useRouter()
const authStore = useAuthStore()
const isOwner = computed(() => authStore.user?.role === 'owner')

const templates = ref<WebSearchProviderTemplate[]>([])
const providers = ref<WebSearchProvider[]>([])
const loading = ref(false)
const isReordering = ref(false)

const enabledCount = computed(() => providers.value.filter((p) => p.is_enabled).length)

const enabledProviders = computed({
  get: () =>
    providers.value.filter((p) => p.is_enabled).sort((a, b) => a.display_order - b.display_order),
  set: (newList: WebSearchProvider[]) => {
    // Sync the reordered enabled list back into the source array
    const enabledIds = new Set(newList.map((p) => p.id))
    const disabled = providers.value.filter((p) => !enabledIds.has(p.id))
    providers.value = [...newList, ...disabled]
  },
})

const disabledProviders = computed(() => providers.value.filter((p) => !p.is_enabled))

// Snapshot of enabled provider IDs before drag — used to detect actual order changes
let preDragOrder: string[] = []

function getTemplate(providerName: string) {
  return templates.value.find((t) => t.provider_name === providerName)
}

function getCircuitLabel(state: string) {
  if (state === 'open') return t('webSearch.circuitOpen')
  if (state === 'half_open') return t('webSearch.circuitHalfOpen')
  return t('webSearch.circuitClosed')
}

function getCircuitColor(state: string) {
  if (state === 'open') return 'var(--van-danger-color)'
  if (state === 'half_open') return 'var(--van-warning-color)'
  return 'var(--van-success-color)'
}

function getCircuitReasonLabel(reason: string | null) {
  if (!reason) return ''
  if (reason === 'transient') return t('webSearch.circuitReasonTransient')
  if (reason === 'api_error') return t('webSearch.circuitReasonApiError')
  if (reason === 'timeout') return t('webSearch.circuitReasonTimeout')
  return reason
}

async function load() {
  loading.value = true
  try {
    const [tmpl, provs] = await Promise.all([getWebSearchTemplates(), getWebSearchProviders()])
    templates.value = tmpl
    providers.value = provs
  } finally {
    loading.value = false
  }
}

function goToForm(providerName?: string, providerId?: string) {
  if (providerId) {
    router.push({ name: 'WebSearchForm', query: { id: providerId } })
  } else if (providerName) {
    router.push({ name: 'WebSearchForm', query: { provider: providerName } })
  }
}

async function handleToggle(provider: WebSearchProvider) {
  try {
    if (provider.is_enabled) {
      await disableWebSearchProvider(provider.id)
      showToast(t('webSearch.disableSuccess'))
    } else {
      await enableWebSearchProvider(provider.id)
      showToast(t('webSearch.enableSuccess'))
    }
    await load()
  } catch {
    showToast(t('webSearch.noApiKeyWarning'))
  }
}

function onDragStart() {
  // Snapshot current order before vuedraggable mutates v-model
  preDragOrder = enabledProviders.value.map((p) => p.id)
}

async function onDragEnd() {
  const newOrder = enabledProviders.value.map((p) => p.id)

  if (JSON.stringify(newOrder) === JSON.stringify(preDragOrder)) {
    return // No change, skip API calls
  }

  isReordering.value = true
  try {
    // Batch update display_order (index = new order)
    const updates = enabledProviders.value.map((p, index) =>
      updateWebSearchProvider(p.id, { display_order: index }),
    )
    await Promise.all(updates)
    showToast(t('webSearch.reorderSuccess'))
    await load() // Refresh to confirm
  } catch {
    showToast(t('webSearch.reorderFailed'))
    await load() // Reload to restore correct state
  } finally {
    isReordering.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="web-search-page">
    <van-nav-bar :title="t('webSearch.title')" left-arrow @click-left="router.back()" />

    <div class="status-bar">
      <span v-if="enabledCount > 0" class="status-enabled">
        {{ t('webSearch.statusEnabled', { count: enabledCount }) }}
      </span>
      <span v-else class="status-disabled">{{ t('webSearch.statusDisabled') }}</span>
    </div>

    <!-- Enabled providers (draggable) -->
    <van-cell-group v-if="enabledProviders.length > 0" :title="t('webSearch.enabledGroup')">
      <div class="drag-hint">{{ t('webSearch.dragHint') }}</div>
      <draggable
        v-model="enabledProviders"
        :item-key="'id'"
        :disabled="!isOwner"
        handle=".drag-handle"
        ghost-class="ghost-item"
        @start="onDragStart"
        @end="onDragEnd"
      >
        <template #item="{ element: provider }">
          <van-cell
            :title="provider.display_name || provider.provider_name"
            :label="getTemplate(provider.provider_name)?.note"
            is-link
            @click="goToForm(undefined, provider.id)"
          >
            <template #icon>
              <van-icon v-if="isOwner" name="wap-nav" class="drag-handle" />
            </template>
            <template #right-icon>
              <div class="provider-actions">
                <div class="health-dot" :style="{ background: getCircuitColor(provider.circuit_state) }" />
                <div class="status-info">
                  <span
                    class="circuit-badge"
                    :style="{ color: getCircuitColor(provider.circuit_state) }"
                  >
                    {{ getCircuitLabel(provider.circuit_state) }}
                  </span>
                  <span v-if="provider.circuit_reason" class="circuit-reason">
                    {{ getCircuitReasonLabel(provider.circuit_reason) }}
                  </span>
                </div>
                <van-switch
                  v-if="isOwner"
                  :model-value="provider.is_enabled"
                  size="20px"
                  @click.stop
                  @update:model-value="handleToggle(provider)"
                />
              </div>
            </template>
          </van-cell>
        </template>
      </draggable>
    </van-cell-group>

    <!-- Disabled providers (static list) -->
    <van-cell-group
      v-if="disabledProviders.length > 0"
      :title="t('webSearch.disabledGroup')"
    >
      <van-cell
        v-for="provider in disabledProviders"
        :key="provider.id"
        :title="provider.display_name || provider.provider_name"
        :label="getTemplate(provider.provider_name)?.note"
        is-link
        @click="goToForm(undefined, provider.id)"
      >
        <template #right-icon>
          <div class="provider-actions">
            <div class="health-dot" :style="{ background: getCircuitColor(provider.circuit_state) }" />
            <div class="status-info">
              <span
                class="circuit-badge"
                :style="{ color: getCircuitColor(provider.circuit_state) }"
              >
                {{ getCircuitLabel(provider.circuit_state) }}
              </span>
              <span v-if="provider.circuit_reason" class="circuit-reason">
                {{ getCircuitReasonLabel(provider.circuit_reason) }}
              </span>
            </div>
            <van-switch
              v-if="isOwner"
              :model-value="provider.is_enabled"
              size="20px"
              @click.stop
              @update:model-value="handleToggle(provider)"
            />
          </div>
        </template>
      </van-cell>
    </van-cell-group>

    <!-- Unconfigured templates -->
    <van-cell-group v-if="isOwner" :title="t('webSearch.addProvider')">
      <template v-for="tmpl in templates" :key="tmpl.provider_name">
        <van-cell
          v-if="!providers.some((p) => p.provider_name === tmpl.provider_name)"
          :title="tmpl.display_name"
          :label="tmpl.note"
          is-link
          @click="goToForm(tmpl.provider_name)"
        >
          <template #right-icon>
            <van-button size="small" type="primary" plain>
              {{ t('webSearch.configBtn') }}
            </van-button>
          </template>
        </van-cell>
      </template>
    </van-cell-group>

    <div class="mcp-hint">
      <van-icon name="info-o" />
      <span>{{ t('webSearch.mcpHint') }}</span>
    </div>
  </div>
</template>

<style scoped>
.web-search-page {
  padding-bottom: 20px;
}

.status-bar {
  padding: 12px 16px;
  font-size: 14px;
}

.status-enabled {
  color: var(--van-success-color);
}

.status-disabled {
  color: var(--text-secondary);
}

.drag-hint {
  padding: 8px 16px;
  font-size: 12px;
  color: var(--text-secondary);
}

.drag-handle {
  cursor: grab;
  margin-right: 12px;
  color: var(--text-secondary);
}

.ghost-item {
  opacity: 0.5;
}

.health-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.provider-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-info {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
}

.circuit-badge {
  font-size: 12px;
}

.circuit-reason {
  font-size: 11px;
  color: var(--text-secondary);
}

.mcp-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 12px 16px;
  font-size: 12px;
  color: var(--text-secondary);
}
</style>