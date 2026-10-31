<template>
  <div class="family-backup-page">
    <van-nav-bar :title="t('backup.title')" left-arrow @click-left="$router.back()" />

    <van-pull-refresh v-model="refreshing" @refresh="load">
      <!-- Status banner -->
      <van-cell-group inset class="section">
        <van-cell :title="t('backup.lastBackup')">
          <template #label>
            <template v-if="latest">
              <div>
                {{ formatDate(latest.backup_date) }}
                <van-tag :type="latest.status === 'success' ? 'success' : 'danger'">
                  {{ latest.status === 'success' ? t('backup.statusSuccess') : t('backup.statusFailed') }}
                </van-tag>
              </div>
              <div class="muted">{{ latest.trigger_type === 'scheduled' ? t('backup.triggerScheduled') : t('backup.triggerManual') }}</div>
            </template>
            <template v-else>
              <div class="muted">{{ t('backup.noRecords') }}</div>
              <div class="muted">{{ t('backup.noRecordsHint') }}</div>
            </template>
          </template>
        </van-cell>
      </van-cell-group>

      <!-- Manual backup -->
      <van-cell-group inset class="section">
        <van-button
          type="primary"
          block
          :loading="triggering"
          @click="onTrigger"
        >
          {{ t('backup.manualBackup') }}
        </van-button>
      </van-cell-group>

      <!-- Backup list -->
      <van-cell-group inset class="section">
        <van-empty v-if="!loading && backups.length === 0" :description="t('backup.noRecords')">
          <van-button type="primary" size="small" :loading="triggering" @click="onTrigger">
            {{ t('backup.createFirst') }}
          </van-button>
        </van-empty>

        <template v-else>
          <van-cell
            v-for="backup in backups"
            :key="backup.backup_run_id || backup.file_path"
            :title="formatDate(backup.backup_date)"
            :label="`${formatBytes(backup.file_size)} · ${backup.trigger_type === 'scheduled' ? t('backup.triggerScheduled') : t('backup.triggerManual')}`"
          >
            <template #right-icon>
              <van-button
                v-if="backup.status === 'success'"
                size="small"
                type="primary"
                plain
                :loading="restoringId === backup.backup_run_id"
                @click="onPreview(backup)"
              >
                {{ t('backup.restore') }}
              </van-button>
              <van-tag v-else type="default">{{ t('backup.statusFailed') }}</van-tag>
            </template>
          </van-cell>
        </template>
      </van-cell-group>
    </van-pull-refresh>

    <!-- Restore confirmation dialog -->
    <van-dialog
      v-model:show="showConfirm"
      :title="t('backup.confirmTitle')"
      :before-close="onConfirmClose"
      :show-cancel-button="true"
      :confirm-button-text="confirmEnabled ? t('backup.confirmButton') : t('backup.confirmHint')"
      :confirm-button-color="confirmEnabled ? '#1989fa' : '#c8c9cc'"
    >
      <div v-if="preview" class="confirm-body">
        <van-cell :title="t('backup.backupDate')" :value="formatDate(preview.backup_date)" />
        <van-cell :title="t('backup.backupVersion')" :value="preview.export_version" />

        <div class="preview-section">
          <div class="section-title">{{ t('backup.willReplace') }}</div>
          <div v-for="(count, table) in preview.delete" :key="table" class="preview-row">
            {{ tableName(table) }}: {{ t('backup.recordCount', { count }) }}
          </div>
        </div>

        <div class="preview-section">
          <div class="section-title">{{ t('backup.willRestore') }}</div>
          <div v-for="(count, table) in preview.insert" :key="table" class="preview-row">
            {{ tableName(table) }}: {{ t('backup.recordCount', { count }) }}
          </div>
        </div>

        <div class="warning">
          <van-icon name="warning-o" />
          {{ t('backup.irreversibleWarning') }}
        </div>

        <van-field
          v-model="confirmInput"
          :label="t('backup.typeToConfirm', { name: familyName })"
          :placeholder="t('backup.familyNamePlaceholder')"
          class="confirm-input"
        />
      </div>
    </van-dialog>

    <!-- Restore progress -->
    <van-dialog
      v-model:show="showProgress"
      :title="t('backup.progressingTitle')"
      :show-confirm-button="restoreDone"
      :show-cancel-button="!restoreDone"
    >
      <div class="progress-body">
        <van-loading v-if="!restoreDone" />
        <van-icon v-else name="checked" color="#07c160" />
        <p>{{ restoreMessage }}</p>
      </div>
    </van-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { showFailToast, showSuccessToast } from 'vant'
import {
  executeRestore,
  listBackups,
  previewRestore,
  getRestoreProgress,
  restoreFiles,
  triggerBackup,
  type BackupRun,
  type RestorePreview,
} from '@/api/backup'
import { useFamilyStore } from '@/stores/family'

const { t } = useI18n()
const familyStore = useFamilyStore()

const refreshing = ref(false)
const loading = ref(true)
const backups = ref<BackupRun[]>([])
const triggering = ref(false)

const showConfirm = ref(false)
const preview = ref<RestorePreview | null>(null)
const pendingBackup = ref<BackupRun | null>(null)
const confirmInput = ref('')
const familyName = computed(
  () => familyStore.family?.custom_title || familyStore.family?.name || '',
)

const confirmEnabled = computed(
  () => familyName.value.length > 0 && confirmInput.value === familyName.value,
)

const showProgress = ref(false)
const restoreDone = ref(false)
const restoreMessage = ref('')
const restoringId = ref<string | null>(null)

const latest = computed(() => backups.value[0] ?? null)

// Table keys come from the backend payload; map each to its i18n key.
const TABLE_I18N: Record<string, string> = {
  users: 'users',
  assets: 'assets',
  liabilities: 'liabilities',
  categories: 'categories',
  tags: 'tags',
  wishes: 'wishes',
  chores: 'chores',
  coin_transactions: 'coinTransactions',
  milestones: 'milestones',
  rental_contracts: 'rentalContracts',
  asset_snapshots: 'assetSnapshots',
  trips: 'trips',
  itinerary_items: 'itineraryItems',
  expense_entries: 'expenseEntries',
  expense_categories: 'expenseCategories',
  cached_files: 'cachedFiles',
  file_remote_locations: 'fileRemoteLocations',
  storage_backends: 'storageBackends',
  learning_progress: 'learningProgress',
  learning_stats: 'learningStats',
  learning_sessions: 'learningSessions',
  notification_channels: 'notificationChannels',
  notification_configs: 'notificationConfigs',
  reminders: 'reminders',
  reminder_notifications: 'reminderNotifications',
  ai_provider_configs: 'aiProviderConfigs',
}

function tableName(key: string): string {
  const i18nKey = TABLE_I18N[key]
  return i18nKey ? t(`backup.table.${i18nKey}`) : key
}

function formatDate(ymd: string): string {
  if (!ymd || ymd.length !== 8) return ymd
  return `${ymd.slice(0, 4)}-${ymd.slice(4, 6)}-${ymd.slice(6, 8)}`
}

function formatBytes(bytes: number | null): string {
  if (bytes === null || bytes === undefined) return t('backup.unknownSize')
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

async function load() {
  loading.value = true
  try {
    const res = await listBackups()
    backups.value = res.data?.items ?? []
  } catch {
    showFailToast(t('backup.loadFailed'))
  } finally {
    loading.value = false
    refreshing.value = false
  }
}

async function onTrigger() {
  triggering.value = true
  try {
    await triggerBackup()
    showSuccessToast(t('backup.backupSuccess'))
    await load()
  } catch (e: unknown) {
    showFailToast(
      (e as { response?: { data?: { message?: string } } })?.response?.data?.message ??
        t('backup.backupFailed'),
    )
  } finally {
    triggering.value = false
  }
}

async function onPreview(backup: BackupRun) {
  restoringId.value = backup.backup_run_id
  try {
    if (!backup.backup_run_id) return
    const previewRes = await previewRestore({ backup_run_id: backup.backup_run_id })
    preview.value = previewRes.data
    pendingBackup.value = backup
    confirmInput.value = ''
    showConfirm.value = true
  } catch (e: unknown) {
    showFailToast(
      (e as { response?: { data?: { message?: string } } })?.response?.data?.message ??
        t('backup.previewFailed'),
    )
  } finally {
    restoringId.value = null
  }
}

async function onConfirmClose(action: string, done: () => void): Promise<boolean> {
  if (action !== 'confirm') {
    done()
    return true
  }
  if (!confirmEnabled.value) {
    done()
    return false
  }
  showConfirm.value = false
  showProgress.value = true
  restoreDone.value = false
  restoreMessage.value = t('backup.restoringData')
  let result: boolean
  try {
    const runId = pendingBackup.value?.backup_run_id
    if (!runId) throw new Error('missing backup_run_id')
    await executeRestore({ backup_run_id: runId })
    restoreMessage.value = t('backup.restoringFiles')
    try {
      const taskRes = await restoreFiles()
      if (taskRes.data?.task_id) {
        await pollProgress(taskRes.data.task_id)
        result = true
      } else {
        restoreDone.value = true
        restoreMessage.value = t('backup.restoreSuccess')
        showSuccessToast(t('backup.restoreSuccess'))
        await load()
        result = true
      }
    } catch {
      restoreDone.value = true
      restoreMessage.value = t('backup.restoreDataOnly')
      await load()
      result = true
    }
  } catch (e: unknown) {
    restoreDone.value = true
    restoreMessage.value = (e as { response?: { data?: { message?: string } } })?.response?.data?.message ?? t('backup.restoreFailed')
    showFailToast(restoreMessage.value)
    result = false
  } finally {
    done()
  }
  return result
}

async function pollProgress(taskId: string) {
  // Poll until the file restore task settles; show a final message either way.
  for (let i = 0; i < 120; i += 1) {
    await new Promise((r) => setTimeout(r, 1000))
    try {
      const progressRes = await getRestoreProgress(taskId)
      const body = progressRes.data
      if (body.status === 'running') {
        restoreMessage.value = t('backup.restoringFilesProgress', { done: body.files_completed, total: body.files_total })
        continue
      }
      if (body.status === 'completed') {
        restoreMessage.value = t('backup.restoreFilesDone')
        showSuccessToast(t('backup.restoreSuccess'))
      } else if (body.status === 'partial_success') {
        restoreMessage.value = t('backup.restoreFilesPartial', { failed: body.files_failed })
      } else {
        restoreMessage.value = t('backup.restoreFilesFailed')
      }
      restoreDone.value = true
      await load()
      return
    } catch {
      // Transient — keep polling.
    }
  }
  restoreDone.value = true
  restoreMessage.value = t('backup.restoreTimeout')
}

onMounted(load)
</script>

<style scoped>
.family-backup-page {
  padding-bottom: 24px;
}
.section {
  margin-top: 12px;
}
.section + .section {
  margin-top: 12px;
}
.muted {
  color: var(--van-text-color-2, #969799);
  font-size: 12px;
}
.confirm-body {
  padding: 12px;
}
.preview-section {
  margin: 12px 0;
}
.section-title {
  font-weight: 600;
  margin-bottom: 4px;
}
.preview-row {
  padding: 2px 0;
  color: var(--van-text-color-2, #969799);
}
.warning {
  background: #fff7e6;
  color: #ed6a0c;
  padding: 8px 12px;
  border-radius: 4px;
  margin: 12px 0;
  font-size: 13px;
}
.confirm-input {
  margin-top: 8px;
}
.progress-body {
  padding: 24px;
  text-align: center;
}
.progress-body p {
  margin-top: 12px;
  color: var(--van-text-color-2, #969799);
}
</style>
