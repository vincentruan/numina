<template>
  <div class="family-backup-page">
    <van-nav-bar title="备份与恢复" left-arrow @click-left="$router.back()" />

    <van-pull-refresh v-model="refreshing" @refresh="load">
      <!-- Status banner -->
      <van-cell-group inset class="section">
        <van-cell title="最近一次备份">
          <template #label>
            <template v-if="latest">
              <div>
                {{ formatDate(latest.backup_date) }}
                <van-tag :type="latest.status === 'success' ? 'success' : 'danger'">
                  {{ latest.status === 'success' ? '成功' : '失败' }}
                </van-tag>
              </div>
              <div class="muted">{{ latest.trigger_type === 'scheduled' ? '自动备份' : '手动备份' }}</div>
            </template>
            <template v-else>
              <div class="muted">暂无备份记录</div>
              <div class="muted">点击下方按钮创建第一个备份</div>
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
          手动备份
        </van-button>
      </van-cell-group>

      <!-- Backup list -->
      <van-cell-group inset class="section">
        <van-empty v-if="!loading && backups.length === 0" description="暂无备份记录">
          <van-button type="primary" size="small" :loading="triggering" @click="onTrigger">
            创建第一个备份
          </van-button>
        </van-empty>

        <template v-else>
          <van-cell
            v-for="backup in backups"
            :key="backup.backup_run_id || backup.file_path"
            :title="formatDate(backup.backup_date)"
            :label="`${formatBytes(backup.file_size)} · ${backup.trigger_type === 'scheduled' ? '自动' : '手动'}`"
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
                恢复
              </van-button>
              <van-tag v-else type="default">失败</van-tag>
            </template>
          </van-cell>
        </template>
      </van-cell-group>
    </van-pull-refresh>

    <!-- Restore confirmation dialog -->
    <van-dialog
      v-model:show="showConfirm"
      title="确认恢复"
      :before-close="onConfirmClose"
      :show-cancel-button="true"
      :confirm-button-text="confirmEnabled ? '恢复' : '请先输入家庭名称'"
      :confirm-button-color="confirmEnabled ? '#1989fa' : '#c8c9cc'"
    >
      <div class="confirm-body" v-if="preview">
        <van-cell title="备份日期" :value="formatDate(preview.backup_date)" />
        <van-cell title="备份版本" :value="preview.export_version" />

        <div class="preview-section">
          <div class="section-title">将被替换的数据</div>
          <div v-for="(count, table) in preview.delete" :key="table" class="preview-row">
            {{ tableName(table) }}: {{ count }} 条
          </div>
        </div>

        <div class="preview-section">
          <div class="section-title">将从备份恢复的数据</div>
          <div v-for="(count, table) in preview.insert" :key="table" class="preview-row">
            {{ tableName(table) }}: {{ count }} 条
          </div>
        </div>

        <div class="warning">
          <van-icon name="warning-o" />
          此操作不可撤销，会替换当前所有家庭数据。
        </div>

        <van-field
          v-model="confirmInput"
          :label="`请输入「${familyName}」以确认`"
          placeholder="家庭名称"
          class="confirm-input"
        />
      </div>
    </van-dialog>

    <!-- Restore progress -->
    <van-dialog
      v-model:show="showProgress"
      title="正在恢复"
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
import { showToast, showFailToast, showSuccessToast } from 'vant'
import {
  executeRestore,
  listBackups,
  previewRestore,
  restoreFiles,
  triggerBackup,
  type BackupRun,
  type RestorePreview,
} from '@/api/backup'
import { useFamilyStore } from '@/stores/family'

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

const TABLE_NAMES: Record<string, string> = {
  assets: '资产',
  liabilities: '负债',
  categories: '分类',
  tags: '标签',
  wishes: '心愿',
  chores: '家务',
  coin_transactions: '金币记录',
  milestones: '里程碑',
  rental_contracts: '租房合同',
  asset_snapshots: '资产快照',
  trips: '行程',
  itinerary_items: '行程项目',
  expense_entries: '支出',
  expense_categories: '支出分类',
  cached_files: '缓存文件',
  file_remote_locations: '远程文件',
  storage_backends: '存储后端',
  learning_progress: '学习进度',
  learning_stats: '学习统计',
  learning_sessions: '学习会话',
  notification_channels: '通知渠道',
  notification_configs: '通知配置',
  reminders: '提醒',
  reminder_notifications: '提醒通知',
  ai_provider_configs: 'AI 配置',
  users: '用户',
}

function tableName(key: string): string {
  return TABLE_NAMES[key] ?? key
}

function formatDate(ymd: string): string {
  if (!ymd || ymd.length !== 8) return ymd
  return `${ymd.slice(0, 4)}-${ymd.slice(4, 6)}-${ymd.slice(6, 8)}`
}

function formatBytes(bytes: number | null): string {
  if (bytes === null || bytes === undefined) return '未知大小'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

async function load() {
  loading.value = true
  try {
    const res = await listBackups()
    backups.value = (res as any)?.items ?? []
  } catch {
    showFailToast('加载备份列表失败')
  } finally {
    loading.value = false
    refreshing.value = false
  }
}

async function onTrigger() {
  triggering.value = true
  try {
    await triggerBackup()
    showSuccessToast('备份完成')
    await load()
  } catch (e: any) {
    showFailToast(e?.response?.data?.message ?? '备份失败')
  } finally {
    triggering.value = false
  }
}

async function onPreview(backup: BackupRun) {
  restoringId.value = backup.backup_run_id
  try {
    preview.value = (await previewRestore({ backup_run_id: backup.backup_run_id! })) as any
    pendingBackup.value = backup
    confirmInput.value = ''
    showConfirm.value = true
  } catch (e: any) {
    showFailToast(e?.response?.data?.message ?? '预览备份失败')
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
  restoreMessage.value = '正在恢复数据...'
  let result: boolean
  try {
    await executeRestore({ backup_run_id: pendingBackup.value?.backup_run_id! })
    restoreMessage.value = '数据已恢复，正在恢复文件（如有）...'
    try {
      const task = (await restoreFiles()) as { task_id?: string }
      if (task?.task_id) {
        await pollProgress(task.task_id)
        result = true
      } else {
        restoreDone.value = true
        restoreMessage.value = '数据恢复成功'
        showSuccessToast('恢复成功')
        await load()
        result = true
      }
    } catch {
      restoreDone.value = true
      restoreMessage.value = '数据已恢复（文件恢复未开始）'
      await load()
      result = true
    }
  } catch (e: unknown) {
    restoreDone.value = true
    restoreMessage.value = (e as { response?: { data?: { message?: string } } })?.response?.data?.message ?? '恢复失败'
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
      const body = (await (await import('@/api/backup')).getRestoreProgress(taskId)) as any
      if (body.status === 'running') {
        restoreMessage.value = `恢复文件中 ${body.files_completed}/${body.files_total}`
        continue
      }
      if (body.status === 'completed') {
        restoreMessage.value = '数据和文件均已恢复'
        showSuccessToast('恢复成功')
      } else if (body.status === 'partial_success') {
        restoreMessage.value = `数据已恢复，${body.files_failed} 个文件失败`
      } else {
        restoreMessage.value = '数据已恢复，但文件恢复失败'
      }
      restoreDone.value = true
      await load()
      return
    } catch {
      // Transient — keep polling.
    }
  }
  restoreDone.value = true
  restoreMessage.value = '恢复超时，数据已提交'
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
