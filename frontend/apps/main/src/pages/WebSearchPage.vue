<!-- frontend/apps/main/src/pages/WebSearchPage.vue -->
<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { showToast, showConfirmDialog } from 'vant'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@numina/auth'
import {
  getWebSearchTemplates,
  getWebSearchProviders,
  enableWebSearchProvider,
  disableWebSearchProvider,
  deleteWebSearchProvider,
  testWebSearchProvider,
} from '@/api/webSearch'
import type { WebSearchProvider, WebSearchProviderTemplate } from '@/types/webSearch'

const { t } = useI18n()
const router = useRouter()
const authStore = useAuthStore()
const isOwner = computed(() => authStore.user?.role === 'owner')

const templates = ref<WebSearchProviderTemplate[]>([])
const providers = ref<WebSearchProvider[]>([])
const loading = ref(false)

const enabledCount = computed(() => providers.value.filter((p) => p.is_enabled).length)

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
  } catch (e: any) {
    showToast(e?.response?.data?.detail || t('webSearch.noApiKeyWarning'))
  }
}

async function handleDelete(provider: WebSearchProvider) {
  try {
    await showConfirmDialog({
      title: t('webSearch.deleteBtn'),
      message: t('webSearch.confirmDelete', { name: provider.display_name || provider.provider_name }),
    })
    await deleteWebSearchProvider(provider.id)
    showToast(t('webSearch.deleteSuccess'))
    await load()
  } catch {
    // User cancelled
  }
}

async function handleTest(provider: WebSearchProvider) {
  try {
    const result = await testWebSearchProvider(provider.id)
    if (result.success) {
      showToast(t('webSearch.testSuccess'))
    } else {
      showToast(t('webSearch.testFailed'))
    }
  } catch {
    showToast(t('webSearch.testFailed'))
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

    <van-cell-group :title="t('webSearch.subtitle')">
      <van-cell
        v-for="provider in providers"
        :key="provider.id"
        :title="provider.display_name || provider.provider_name"
        :label="getTemplate(provider.provider_name)?.note"
        is-link
        @click="goToForm(undefined, provider.id)"
      >
        <template #right-icon>
          <div class="provider-actions">
            <span
              class="circuit-badge"
              :style="{ color: getCircuitColor(provider.circuit_state) }"
            >
              {{ getCircuitLabel(provider.circuit_state) }}
            </span>
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

.provider-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.circuit-badge {
  font-size: 12px;
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