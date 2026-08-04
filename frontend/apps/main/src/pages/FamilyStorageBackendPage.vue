<template>
  <div class="family-storage-page">
    <van-nav-bar
      :title="t('storageBackend.title')"
      left-arrow
      @click-left="$router.back()"
    />

    <van-skeleton v-if="loading" :row="6" class="skeleton" />

    <template v-else>
      <!-- Status banner -->
      <van-cell-group inset class="section">
        <van-cell :label="t('storageBackend.description')">
          <template #title>
            <span>{{ t('storageBackend.title') }}</span>
            <van-tag
              v-if="existingBackend"
              :type="existingBackend.is_active ? 'success' : 'warning'"
              class="status-tag"
            >
              {{ existingBackend.is_active ? t('storageBackend.enabled') : t('storageBackend.disabled') }}
            </van-tag>
            <van-tag v-else type="default" class="status-tag">
              {{ t('storageBackend.notConfigured') }}
            </van-tag>
          </template>
        </van-cell>
      </van-cell-group>

      <!-- Existing backend info (read-only) -->
      <van-cell-group v-if="existingBackend && !editing" inset class="section">
        <van-cell
          :title="t('storageBackend.backendType')"
          :value="existingBackend.backend_type === 'github' ? t('storageBackend.github') : t('storageBackend.webdav')"
        />
        <van-cell
          v-if="existingBackend.display_name"
          :title="t('storageBackend.displayName')"
          :value="existingBackend.display_name"
        />
        <van-cell
          :title="t('storageBackend.configured')"
          :value="existingBackend.is_active ? t('storageBackend.enabled') : t('storageBackend.disabled')"
        />
        <div class="actions">
          <van-button size="small" type="primary" plain @click="editing = true">
            {{ t('storageBackend.update') }}
          </van-button>
          <van-button size="small" type="danger" plain @click="onDelete">
            {{ t('storageBackend.delete') }}
          </van-button>
        </div>
      </van-cell-group>

      <!-- Create/Edit form -->
      <van-cell-group v-if="!existingBackend || editing" inset class="section">
        <!-- Backend type selector (only for new) -->
        <van-cell
          v-if="!existingBackend"
          :title="t('storageBackend.backendType')"
          :value="form.backend_type === 'github' ? t('storageBackend.github') : t('storageBackend.webdav')"
          is-link
          @click="showTypePicker = true"
        />

        <!-- GitHub fields -->
        <template v-if="form.backend_type === 'github'">
          <van-field
            v-model="form.github.repo_owner"
            :label="t('storageBackend.repoOwner')"
            :placeholder="t('storageBackend.repoOwnerPlaceholder')"
          />
          <van-field
            v-model="form.github.repo_name"
            :label="t('storageBackend.repoName')"
            :placeholder="t('storageBackend.repoNamePlaceholder')"
          />
          <van-field
            v-model="form.github.branch"
            :label="t('storageBackend.branch')"
            :placeholder="t('storageBackend.branchPlaceholder')"
          />
          <van-field
            v-model="form.github.token"
            type="password"
            :label="t('storageBackend.token')"
            :placeholder="t('storageBackend.tokenPlaceholder')"
          />
        </template>

        <!-- WebDAV fields -->
        <template v-if="form.backend_type === 'webdav'">
          <van-field
            v-model="form.webdav.base_url"
            :label="t('storageBackend.baseUrl')"
            :placeholder="t('storageBackend.baseUrlPlaceholder')"
          />
          <van-field
            v-model="form.webdav.username"
            :label="t('storageBackend.username')"
            :placeholder="t('storageBackend.usernamePlaceholder')"
          />
          <van-field
            v-model="form.webdav.password"
            type="password"
            :label="t('storageBackend.password')"
            :placeholder="t('storageBackend.passwordPlaceholder')"
          />
        </template>

        <!-- Common fields -->
        <van-field
          v-model="form.display_name"
          :label="t('storageBackend.displayName')"
          :placeholder="t('storageBackend.displayNamePlaceholder')"
        />
        <van-cell :title="t('storageBackend.enabled')" center>
          <template #right-icon>
            <van-switch v-model="form.is_active" size="20" />
          </template>
        </van-cell>
      </van-cell-group>

      <!-- Save button -->
      <div v-if="!existingBackend || editing" class="save-action">
        <van-button
          block
          type="primary"
          :loading="saving"
          @click="onSave"
        >
          {{ existingBackend ? t('storageBackend.update') : t('storageBackend.save') }}
        </van-button>
      </div>
    </template>

    <!-- Backend type picker -->
    <van-popup v-model:show="showTypePicker" position="bottom" round destroy-on-close>
      <van-picker
        :columns="typeColumns"
        :model-value="[form.backend_type]"
        @confirm="onTypeConfirm"
        @cancel="showTypePicker = false"
      />
    </van-popup>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { showSuccessToast, showFailToast, showConfirmDialog } from 'vant'
import {
  createStorageBackend,
  deleteStorageBackend,
  getStorageBackend,
  updateStorageBackend,
  type StorageBackendResponse,
} from '@/api/storageBackend'

defineOptions({ name: 'FamilyStorageBackend' })

const { t } = useI18n()

const loading = ref(true)
const saving = ref(false)
const editing = ref(false)
const existingBackend = ref<StorageBackendResponse | null>(null)
const showTypePicker = ref(false)

const form = reactive({
  backend_type: 'github' as 'github' | 'webdav',
  display_name: '',
  is_active: true,
  github: {
    repo_owner: '',
    repo_name: '',
    branch: 'main',
    token: '',
  },
  webdav: {
    base_url: '',
    username: '',
    password: '',
  },
})

const typeColumns = computed(() => [
  { text: t('storageBackend.github'), value: 'github' },
  { text: t('storageBackend.webdav'), value: 'webdav' },
])

function onTypeConfirm({ selectedOptions }: { selectedOptions: { value: string }[] }) {
  form.backend_type = selectedOptions[0]?.value as 'github' | 'webdav'
  showTypePicker.value = false
}

async function loadBackend() {
  loading.value = true
  try {
    const res = await getStorageBackend()
    existingBackend.value = res.data ?? null
  } catch {
    showFailToast(t('storageBackend.loadFailed'))
  } finally {
    loading.value = false
  }
}

async function onSave() {
  saving.value = true
  try {
    const config = form.backend_type === 'github' ? form.github : form.webdav
    const payload = {
      backend_type: form.backend_type,
      config,
      display_name: form.display_name || null,
      is_active: form.is_active,
    }

    if (existingBackend.value) {
      await updateStorageBackend(existingBackend.value.id, {
        config,
        display_name: form.display_name || null,
        is_active: form.is_active,
      })
      showSuccessToast(t('storageBackend.updateSuccess'))
    } else {
      await createStorageBackend(payload)
      showSuccessToast(t('storageBackend.saveSuccess'))
    }
    editing.value = false
    await loadBackend()
  } catch {
    showFailToast(t('storageBackend.saveFailed'))
  } finally {
    saving.value = false
  }
}

async function onDelete() {
  if (!existingBackend.value) return
  try {
    await showConfirmDialog({
      title: t('storageBackend.delete'),
      message: t('storageBackend.deleteConfirm'),
    })
    await deleteStorageBackend(existingBackend.value.id)
    showSuccessToast(t('storageBackend.deleteSuccess'))
    existingBackend.value = null
  } catch {
    // User cancelled or delete failed
  }
}

onMounted(loadBackend)
</script>

<style scoped>
.family-storage-page {
  padding-bottom: env(safe-area-inset-bottom);
}

.skeleton {
  padding: 16px;
}

.section {
  margin-top: 12px;
}

.status-tag {
  margin-left: 8px;
}

.actions {
  display: flex;
  gap: 12px;
  padding: 12px 16px;
}

.save-action {
  padding: 16px;
}
</style>
