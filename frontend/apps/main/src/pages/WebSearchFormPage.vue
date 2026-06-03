<!-- frontend/apps/main/src/pages/WebSearchFormPage.vue -->
<script setup lang="ts">
import { ref, onMounted, computed, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@numina/auth'
import {
  getWebSearchTemplates,
  getWebSearchProviders,
  createWebSearchProvider,
  updateWebSearchProvider,
  testWebSearchProvider,
  revealWebSearchKey,
} from '@/api/webSearch'
import type { WebSearchProvider, WebSearchProviderTemplate } from '@/types/webSearch'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const isOwner = computed(() => authStore.user?.role === 'owner')

const isEdit = computed(() => !!route.query.id)
const providerId = computed(() => route.query.id as string | undefined)
const providerNameParam = computed(() => route.query.provider as string | undefined)

const template = ref<WebSearchProviderTemplate | null>(null)
const existingProvider = ref<WebSearchProvider | null>(null)

const form = ref({
  provider_name: '',
  display_name: '',
  api_key: '',
  max_results: 5,
})

const loading = ref(false)
const saving = ref(false)
const testing = ref(false)

// API key reveal state (like AIProviderFormPage)
const revealedKey = ref<string | null>(null)
const revealing = ref(false)

const pageTitle = computed(() =>
  isEdit.value ? t('webSearch.formEditTitle') : t('webSearch.formTitle'),
)

const maskedKey = computed(() => existingProvider.value?.api_key_masked ?? null)
const hasApiKey = computed(() => existingProvider.value?.has_api_key ?? false)

async function load() {
  loading.value = true
  try {
    const templates = await getWebSearchTemplates()

    if (isEdit.value && providerId.value) {
      const providers = await getWebSearchProviders()
      existingProvider.value = providers.find((p) => p.id === providerId.value) || null
      if (existingProvider.value) {
        template.value =
          templates.find((t) => t.provider_name === existingProvider.value!.provider_name) || null
        form.value.provider_name = existingProvider.value.provider_name
        form.value.display_name = existingProvider.value.display_name || ''
        form.value.max_results = existingProvider.value.max_results
        form.value.api_key = ''
      }
    } else if (providerNameParam.value) {
      template.value = templates.find((t) => t.provider_name === providerNameParam.value) || null
      if (template.value) {
        form.value.provider_name = template.value.provider_name
        form.value.display_name = template.value.display_name
        form.value.max_results = template.value.config_fields.find((f) => f.key === 'max_results')?.default as number ?? 5
      }
    }
  } finally {
    loading.value = false
  }
}

async function onCopyKey() {
  try {
    let text = revealedKey.value
    if (!text && providerId.value) {
      const res = await revealWebSearchKey(providerId.value)
      text = res.api_key
    }
    if (!text) return
    await navigator.clipboard.writeText(text)
    showToast(t('toast.copied'))
  } catch {
    showToast(t('toast.operationFailed2'))
  }
}

async function onToggleReveal() {
  if (revealedKey.value) {
    revealedKey.value = null
    return
  }
  if (!providerId.value) return
  revealing.value = true
  try {
    const res = await revealWebSearchKey(providerId.value)
    revealedKey.value = res.api_key
  } catch {
    showToast(t('webSearch.revealFailed'))
  } finally {
    revealing.value = false
  }
}

async function handleSave() {
  if (!template.value) return

  if (template.value.requires_api_key && !form.value.api_key && !isEdit.value) {
    showToast(t('webSearch.noApiKeyWarning'))
    return
  }

  // For edit: if provider already has API key and user didn't enter new one, that's OK
  if (isEdit.value && template.value.requires_api_key && !form.value.api_key && !hasApiKey.value) {
    showToast(t('webSearch.noApiKeyWarning'))
    return
  }

  saving.value = true
  try {
    if (isEdit.value && providerId.value) {
      const payload: Record<string, unknown> = {
        display_name: form.value.display_name || undefined,
        max_results: form.value.max_results,
      }
      if (form.value.api_key) {
        payload.api_key = form.value.api_key
      }
      await updateWebSearchProvider(providerId.value, payload)
    } else {
      await createWebSearchProvider({
        provider_name: form.value.provider_name,
        display_name: form.value.display_name || undefined,
        api_key: form.value.api_key || undefined,
        max_results: form.value.max_results,
      })
    }
    showToast(t('webSearch.saveSuccess'))
    router.back()
  } catch (e: unknown) {
    const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    showToast(detail || t('webSearch.saveFailed'))
  } finally {
    saving.value = false
  }
}

async function handleTest() {
  if (!providerId.value) return
  testing.value = true
  try {
    const result = await testWebSearchProvider(providerId.value)
    if (result.success) {
      showToast(t('webSearch.testSuccess'))
    } else {
      showToast(t('webSearch.testFailedWithMsg', { msg: result.message }))
    }
  } catch (e: unknown) {
    const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    showToast(detail || t('webSearch.testFailed'))
  } finally {
    testing.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="web-search-form-page">
    <van-nav-bar :title="pageTitle" left-arrow @click-left="router.back()" />

    <van-form @submit="handleSave">
      <van-cell-group inset>
        <van-field
          v-model="form.display_name"
          :label="t('webSearch.providerName')"
          :placeholder="template?.display_name"
        />

        <!-- Edit mode: show masked key with copy/eye toggle -->
        <template v-if="isEdit && template?.requires_api_key">
          <van-cell v-if="maskedKey" :title="t('webSearch.currentApiKey')">
            <template #value>
              <div class="key-reveal-row">
                <span class="key-reveal-value">{{ revealedKey || maskedKey }}</span>
                <button class="key-icon-btn" :title="t('webSearch.copyApiKey')" @click.stop="onCopyKey">
                  <van-icon name="description" size="16" />
                </button>
                <button
                  class="key-icon-btn"
                  :title="revealedKey ? t('webSearch.hideApiKey') : t('webSearch.showApiKey')"
                  :disabled="revealing"
                  @click.stop="onToggleReveal"
                >
                  <van-icon
                    v-if="revealing"
                    name="loading"
                    size="16"
                    class="key-icon-spinning"
                  />
                  <van-icon v-else :name="revealedKey ? 'eye-o' : 'closed-eye'" size="16" />
                </button>
              </div>
            </template>
          </van-cell>
          <van-cell v-else-if="!hasApiKey" :title="t('webSearch.currentApiKey')">
            <template #value>
              <span class="key-empty">{{ t('webSearch.noApiKeyConfigured') }}</span>
            </template>
          </van-cell>
          <!-- New API key input (optional update) -->
          <van-field
            v-model="form.api_key"
            :label="t('webSearch.newApiKey')"
            :placeholder="t('webSearch.apiKeyUpdatePlaceholder')"
            autocomplete="off"
          />
        </template>

        <!-- Create mode: simple password field -->
        <van-field
          v-else-if="template?.requires_api_key"
          v-model="form.api_key"
          :label="t('webSearch.apiKey')"
          :placeholder="t('webSearch.apiKeyPlaceholder')"
          type="password"
          autocomplete="off"
        />

        <van-field
          v-model.number="form.max_results"
          :label="t('webSearch.maxResults')"
          type="digit"
        />
      </van-cell-group>

      <div class="form-actions">
        <van-button
          v-if="isOwner"
          type="primary"
          block
          native-type="submit"
          :loading="saving"
        >
          {{ t('webSearch.saveBtn') }}
        </van-button>

        <van-button
          v-if="isEdit && isOwner"
          plain
          block
          :loading="testing"
          @click="handleTest"
        >
          {{ t('webSearch.testBtn') }}
        </van-button>
      </div>

      <div v-if="template" class="provider-info">
        <p>{{ template.note }}</p>
        <a :href="template.docs_url" target="_blank" rel="noopener">{{ template.docs_url }}</a>
      </div>
    </van-form>
  </div>
</template>

<style scoped>
.web-search-form-page {
  padding-bottom: 20px;
}

.form-actions {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.provider-info {
  padding: 12px 16px;
  font-size: 12px;
  color: var(--text-secondary);
}

.provider-info a {
  color: var(--van-primary-color);
}

.key-reveal-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.key-reveal-value {
  flex: 1;
  min-width: 0;
  font-size: 12px;
  font-family: monospace;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.key-empty {
  font-size: 12px;
  color: var(--text-tertiary);
}

.key-icon-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 6px;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  flex-shrink: 0;
  -webkit-tap-highlight-color: transparent;
  transition: background 0.15s;
}

.key-icon-btn:active {
  background: rgba(0, 0, 0, 0.05);
}

[data-theme='dark'] .key-icon-btn:active {
  background: rgba(255, 255, 255, 0.08);
}

.key-icon-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.key-icon-spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to   { transform: rotate(360deg); }
}
</style>