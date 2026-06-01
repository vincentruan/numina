<!-- frontend/apps/main/src/pages/WebSearchFormPage.vue -->
<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
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

const pageTitle = computed(() =>
  isEdit.value ? t('webSearch.formEditTitle') : t('webSearch.formTitle'),
)

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
      }
    }
  } finally {
    loading.value = false
  }
}

async function handleSave() {
  if (!template.value) return

  if (template.value.requires_api_key && !form.value.api_key && !isEdit.value) {
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
  try {
    const result = await testWebSearchProvider(providerId.value)
    showToast(result.success ? t('webSearch.testSuccess') : t('webSearch.testFailed'))
  } catch {
    showToast(t('webSearch.testFailed'))
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

        <van-field
          v-if="template?.requires_api_key"
          v-model="form.api_key"
          :label="t('webSearch.apiKey')"
          :placeholder="
            isEdit && existingProvider?.has_api_key
              ? '••••••••（已配置，留空不修改）'
              : t('webSearch.apiKeyPlaceholder')
          "
          type="password"
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
</style>