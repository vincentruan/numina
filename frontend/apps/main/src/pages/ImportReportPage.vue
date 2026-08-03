<template>
  <div class="import-report-page">
    <PageHeader :title="t('importReport.pageTitle')" />

    <!-- Upload step -->
    <div v-if="step === 'upload'" class="upload-section">
      <van-cell-group inset class="upload-card">
        <div class="upload-hint">
          <p class="hint-title">{{ t('importReport.uploadTitle') }}</p>
          <p class="hint-desc">{{ t('importReport.uploadDesc') }}</p>
        </div>
        <van-uploader
          :after-read="handleFileRead"
          :accept="acceptTypes"
          :max-size="25 * 1024 * 1024"
          @oversize="showToast(t('importReport.fileTooLarge'))"
        >
          <van-button icon="plus" type="primary" block>{{ t('importReport.selectFile') }}</van-button>
        </van-uploader>
        <p class="paste-hint">{{ t('importReport.pasteHint') }}</p>
      </van-cell-group>

      <!-- R23: Recent imports history section -->
      <div class="history-section">
        <div class="section-header">
          <span>{{ t('importReport.recentImports') }}</span>
        </div>
        <van-loading v-if="historyLoading" size="24px" />
        <div v-else-if="historyItems.length === 0" class="history-empty">
          <p>{{ t('importReport.noImportHistory') }}</p>
        </div>
        <van-cell-group v-else inset>
          <van-cell
            v-for="h in historyItems"
            :key="h.id"
            :title="h.source_filename"
            :label="formatDate(h.created_at)"
            is-link
            @click="selectedHistory = h"
          >
            <template #value>
              <div class="history-meta">
                <van-tag :type="statusTagType(h.status)" size="medium">{{ statusText(h.status) }}</van-tag>
                <span class="history-count">{{ h.item_count }}{{ t('importReport.items') }}</span>
              </div>
            </template>
          </van-cell>
        </van-cell-group>
      </div>
    </div>

    <!-- Parsing step -->
    <div v-if="step === 'parsing'" class="parsing-section">
      <van-loading size="48px" vertical>
        {{ t('importReport.parsing') }}
      </van-loading>
      <p v-if="isLargeFile" class="large-file-hint">{{ t('importReport.largeFileHint') }}</p>
    </div>

    <!-- Preview step -->
    <div v-if="step === 'preview'" class="preview-section">
      <!-- Zero items message (R7a) -->
      <div v-if="editableItems.length === 0" class="empty-result">
        <van-empty :description="preview?.message || t('importReport.noItemsFound')" />
        <van-button type="primary" plain block @click="step = 'upload'">
          {{ t('importReport.reupload') }}
        </van-button>
      </div>

      <template v-else>
        <!-- Summary bar -->
        <div class="preview-summary">
          <span>{{ t('importReport.summaryLine', { total: editableItems.length, assets: assetItems.length, liabilities: liabilityItems.length }) }}</span>
        </div>

        <!-- Duplicate warning banner (R13) -->
        <van-cell-group v-if="duplicateCount > 0" inset class="duplicate-banner">
          <van-icon name="warning-o" />
          <span>{{ t('importReport.duplicateWarning', { count: duplicateCount }) }}</span>
        </van-cell-group>

        <!-- Asset section -->
        <div v-if="assetItems.length > 0" class="model-section">
          <div class="section-header">
            <van-icon name="gold-coin-o" />
            <span>{{ t('importReport.assetSection', { count: assetItems.length }) }}</span>
          </div>
          <PreviewItem
            v-for="item in sortedAssetItems"
            :key="item.temp_id"
            :item="item"
            @update="updateItem"
            @delete="deleteItem"
          />
        </div>

        <!-- Liability section -->
        <div v-if="liabilityItems.length > 0" class="model-section">
          <div class="section-header">
            <van-icon name="bill-o" />
            <span>{{ t('importReport.liabilitySection', { count: liabilityItems.length }) }}</span>
          </div>
          <PreviewItem
            v-for="item in sortedLiabilityItems"
            :key="item.temp_id"
            :item="item"
            @update="updateItem"
            @delete="deleteItem"
          />
        </div>

        <!-- Action bar -->
        <div class="action-bar">
          <van-button plain @click="step = 'upload'">{{ t('importReport.reupload') }}</van-button>
          <van-button type="primary" :loading="confirming" @click="handleConfirm">
            {{ t('importReport.confirm') }}
          </van-button>
        </div>
      </template>
    </div>

    <!-- Commit results step -->
    <div v-if="step === 'results'" class="results-section">
      <van-cell-group inset class="results-summary">
        <van-cell :title="t('importReport.resultCreated')" :value="String(confirmResult?.created ?? 0)" />
        <van-cell :title="t('importReport.resultUpdated')" :value="String(confirmResult?.updated ?? 0)" />
        <van-cell v-if="(confirmResult?.skipped ?? 0) > 0" :title="t('importReport.resultSkipped')" :value="String(confirmResult?.skipped)" />
      </van-cell-group>

      <van-cell-group inset class="results-list">
        <div
          v-for="r in confirmResult?.items ?? []"
          :key="r.temp_id"
          :class="['result-item', r.status === 'error' ? 'result-error' : '']"
        >
          <van-icon :name="r.status === 'error' ? 'cross' : 'success'" :color="r.status === 'error' ? '#ee0a24' : '#07c160'" />
          <span class="result-name">{{ r.name || r.temp_id }}</span>
          <span v-if="r.error" class="result-error-text">{{ r.error }}</span>
        </div>
      </van-cell-group>

      <div class="action-bar">
        <van-button type="primary" block @click="router.back()">{{ t('importReport.done') }}</van-button>
      </div>
    </div>

    <!-- R23: History detail popup with rollback -->
    <van-popup v-model:show="showHistoryDetail" position="bottom" round :style="{ maxHeight: '70vh' }">
      <div v-if="selectedHistory" class="history-detail">
        <div class="history-detail-header">
          <h3>{{ selectedHistory.source_filename }}</h3>
          <van-tag :type="statusTagType(selectedHistory.status)">{{ statusText(selectedHistory.status) }}</van-tag>
        </div>
        <p class="history-detail-date">{{ formatDate(selectedHistory.created_at) }} · {{ selectedHistory.item_count }}{{ t('importReport.items') }}</p>

        <van-button
          v-if="selectedHistory.can_rollback"
          type="danger"
          plain
          block
          @click="handleRollback"
        >
          {{ t('importReport.rollback') }}
        </van-button>
        <p v-else-if="selectedHistory.status === 'committed'" class="rollback-expired">
          {{ t('importReport.rollbackExpired') }}
        </p>
      </div>
    </van-popup>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { showToast, showSuccessToast, showFailToast } from 'vant'
import type { UploaderFileListItem } from 'vant'
import PageHeader from '@/components/common/PageHeader.vue'
import PreviewItem from '@/components/import/PreviewItem.vue'
import { parseFile, confirmImport, getImportHistory, rollbackImport } from '@/api/importReport'
import type { ImportPreview, ImportPreviewItem, ConfirmResponse, HistoryItem } from '@/api/importReport'

defineOptions({ name: 'ImportReportPage' })

const { t } = useI18n()
const router = useRouter()

const step = ref<'upload' | 'parsing' | 'preview' | 'results'>('upload')
const preview = ref<ImportPreview | null>(null)
const editableItems = ref<ImportPreviewItem[]>([])
const confirming = ref(false)
const confirmResult = ref<ConfirmResponse | null>(null)
const currentFile = ref<File | null>(null)
const draftId = ref<string | null>(null)

// History state (R23).
const historyItems = ref<HistoryItem[]>([])
const historyLoading = ref(false)
const showHistoryDetail = ref(false)
const selectedHistory = ref<HistoryItem | null>(null)

function formatDate(iso: string): string {
  if (!iso) return ''
  const d = new Date(iso)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function statusTagType(status: string): 'default' | 'primary' | 'success' | 'warning' | 'danger' {
  if (status === 'committed') return 'success'
  if (status === 'rolled_back') return 'warning'
  return 'default'
}

function statusText(status: string): string {
  if (status === 'committed') return t('importReport.statusCommitted')
  if (status === 'rolled_back') return t('importReport.statusRolledBack')
  return t('importReport.statusPending')
}

async function loadHistory() {
  historyLoading.value = true
  try {
    historyItems.value = await getImportHistory()
  } catch {
    // Silent fail — history is non-critical.
  } finally {
    historyLoading.value = false
  }
}

async function handleRollback() {
  if (!selectedHistory.value) return
  const { showConfirmDialog } = await import('vant')
  try {
    await showConfirmDialog({
      title: t('importReport.rollbackConfirmTitle'),
      message: t('importReport.rollbackConfirmMsg', {
        filename: selectedHistory.value.source_filename,
        count: selectedHistory.value.item_count,
      }),
    })
    const result = await rollbackImport(selectedHistory.value.id)
    showSuccessToast(t('importReport.rollbackSuccess', { count: result.archived_count }))
    showHistoryDetail.value = false
    loadHistory()
  } catch {
    // User cancelled or API error.
  }
}

// R1: accepted file types.
const acceptTypes = 'application/pdf,image/png,image/jpeg,.xlsx,.xls,.csv'

const assetItems = computed(() => editableItems.value.filter((i) => i.target_model === 'asset'))
const liabilityItems = computed(() => editableItems.value.filter((i) => i.target_model === 'liability'))

// R10: sort low-confidence items to top of each section.
const sortedAssetItems = computed(() =>
  [...assetItems.value].sort((a, b) => (a.confidence ?? 1) - (b.confidence ?? 1))
)
const sortedLiabilityItems = computed(() =>
  [...liabilityItems.value].sort((a, b) => (a.confidence ?? 1) - (b.confidence ?? 1))
)

const duplicateCount = computed(() =>
  editableItems.value.filter((i) => i.matched_asset_id).length
)

const isLargeFile = computed(() => (currentFile.value?.size ?? 0) > 5 * 1024 * 1024)

function updateItem(tempId: string, updates: Partial<ImportPreviewItem>) {
  const idx = editableItems.value.findIndex((i) => i.temp_id === tempId)
  if (idx >= 0) {
    editableItems.value[idx] = { ...editableItems.value[idx], ...updates }
  }
}

function deleteItem(tempId: string) {
  editableItems.value = editableItems.value.filter((i) => i.temp_id !== tempId)
}

async function handleFileRead(file: UploaderFileListItem | UploaderFileListItem[]) {
  const item = Array.isArray(file) ? file[0] : file
  if (!item.file) return
  currentFile.value = item.file
  await doParse(item.file)
}

async function doParse(file: File) {
  step.value = 'parsing'
  try {
    const result = await parseFile(file)
    preview.value = result
    draftId.value = result.draft_id
    editableItems.value = result.items.map((i) => ({ ...i }))
    step.value = 'preview'
  } catch (err: unknown) {
    step.value = 'upload'
    const axiosErr = err as { response?: { data?: { message?: string } } }
    const msg = axiosErr?.response?.data?.message || t('importReport.parseFailed')
    showFailToast(msg)
  }
}

// R2: clipboard paste handler.
function handlePaste(e: ClipboardEvent) {
  if (step.value !== 'upload') return
  const files = e.clipboardData?.files
  if (!files || files.length === 0) return
  for (const f of files) {
    if (f.type.startsWith('image/')) {
      currentFile.value = f
      doParse(f)
      return
    }
  }
}

onMounted(() => {
  document.addEventListener('paste', handlePaste)
  loadHistory()
})
onUnmounted(() => {
  document.removeEventListener('paste', handlePaste)
})

async function handleConfirm() {
  confirming.value = true
  try {
    const result = await confirmImport(editableItems.value, draftId.value)
    confirmResult.value = result
    step.value = 'results'
    showSuccessToast(t('importReport.importSuccess', { update: result.updated, create: result.created }))
  } catch {
    showFailToast(t('importReport.importFailed'))
  } finally {
    confirming.value = false
  }
}
</script>

<style scoped>
.import-report-page {
  min-height: 100vh;
  background: var(--van-background);
  padding-bottom: calc(60px + env(safe-area-inset-bottom));
}
.upload-section,
.parsing-section,
.preview-section,
.results-section {
  padding: 16px;
}
.upload-card {
  padding: 24px 16px;
}
.upload-hint {
  text-align: center;
  margin-bottom: 20px;
}
.hint-title {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 8px;
}
.hint-desc {
  font-size: 13px;
  color: var(--van-text-color-2);
  line-height: 1.5;
}
.paste-hint {
  text-align: center;
  font-size: 12px;
  color: var(--van-text-color-3);
  margin-top: 12px;
}
.parsing-section {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  min-height: 60vh;
}
.large-file-hint {
  margin-top: 12px;
  font-size: 13px;
  color: var(--van-text-color-2);
}
.empty-result {
  padding: 40px 16px;
  text-align: center;
}
.preview-summary {
  padding: 8px 16px;
  font-size: 14px;
  color: var(--van-text-color-2);
}
.duplicate-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  margin-bottom: 8px;
  background: var(--van-warning-color-light, #fffbe6);
  border-radius: 8px;
  font-size: 13px;
  color: var(--van-warning-color, #ff976a);
}
.model-section {
  margin-bottom: 12px;
}
.section-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  font-size: 14px;
  font-weight: 600;
  color: var(--van-text-color);
}
.action-bar {
  display: flex;
  gap: 12px;
  padding: 16px;
  position: sticky;
  bottom: 0;
  background: var(--van-background);
}
.action-bar .van-button {
  flex: 1;
}
.results-summary {
  margin-bottom: 12px;
}
.result-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  border-bottom: 1px solid var(--van-border-color);
}
.result-item.result-error {
  background: var(--van-danger-color-light, #fff0f0);
}
.result-name {
  flex: 1;
  font-size: 14px;
}
.result-error-text {
  font-size: 12px;
  color: var(--van-danger-color, #ee0a24);
}
</style>
