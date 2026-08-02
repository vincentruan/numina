<template>
  <div class="import-report-page">
    <PageHeader :title="t('settings.importReport')" />

    <!-- 上传区域 -->
    <div v-if="step === 'upload'" class="upload-section">
      <van-cell-group inset class="upload-card">
        <div class="upload-hint">
          <p class="hint-title">{{ t('importReport.uploadTitle') }}</p>
          <p class="hint-desc">{{ t('importReport.uploadDesc') }}</p>
        </div>
        <van-uploader
          :after-read="handleFileRead"
          accept="application/pdf"
          :max-size="10 * 1024 * 1024"
          @oversize="showToast(t('importReport.fileTooLarge'))"
        >
          <van-button icon="plus" type="primary" block>{{ t('importReport.selectFile') }}</van-button>
        </van-uploader>
      </van-cell-group>
    </div>

    <!-- 解析中 -->
    <div v-if="step === 'parsing'" class="parsing-section">
      <van-loading size="48px" vertical>{{ t('importReport.parsing') }}</van-loading>
    </div>

    <!-- 预览确认 -->
    <div v-if="step === 'preview'" class="preview-section">
      <van-cell-group inset>
        <van-cell :title="t('importReport.source')" :value="preview!.source || t('importReport.unknown')" />
        <van-cell :title="t('importReport.reportDate')" :value="preview!.report_date || t('importReport.unknown')" />
      </van-cell-group>

      <div class="preview-summary">
        {{ t('importReport.summary', { update: updateCount, create: createCount }) }}
      </div>

      <van-cell-group inset class="preview-list">
        <div
          v-for="item in editableItems"
          :key="item.temp_id"
          :class="['preview-item', item.warning ? 'has-warning' : '']"
        >
          <div class="item-row">
            <van-field
              v-model="item.name"
              :label="t('importReport.assetName')"
              :placeholder="t('importReport.assetName')"
            />
            <van-field
              :model-value="item.current_value ?? undefined"
              :label="t('importReport.currentValue')"
              type="number"
              :placeholder="t('importReport.enterValue')"
              @update:model-value="(v) => (item.current_value = v === '' ? null : Number(v))"
            />
          </div>
          <div class="item-meta">
            <van-tag :type="item.action === 'update' ? 'primary' : 'success'">
              {{ item.action === 'update' ? t('importReport.actionUpdate') : t('importReport.actionCreate') }}
            </van-tag>
            <span v-if="item.matched_asset_name" class="matched-name">
              → {{ item.matched_asset_name }}
            </span>
            <span v-if="item.warning" class="warning-text">⚠ {{ warningText(item.warning) }}</span>
          </div>
        </div>
      </van-cell-group>

      <div class="action-bar">
        <van-button plain @click="step = 'upload'">{{ t('importReport.reupload') }}</van-button>
        <van-button type="primary" :loading="confirming" @click="handleConfirm">
          {{ t('importReport.confirm') }}
        </van-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { showToast, showSuccessToast, showFailToast } from 'vant'
import type { UploaderFileListItem } from 'vant'
import PageHeader from '@/components/common/PageHeader.vue'
import { parseReport, confirmImport } from '@/api/importReport'
import type { ImportPreview, ImportPreviewItem } from '@/api/importReport'

const { t } = useI18n()

const step = ref<'upload' | 'parsing' | 'preview'>('upload')
const preview = ref<ImportPreview | null>(null)
const editableItems = ref<ImportPreviewItem[]>([])
const confirming = ref(false)

const updateCount = computed(() => editableItems.value.filter((i) => i.action === 'update').length)
const createCount = computed(() => editableItems.value.filter((i) => i.action === 'create').length)

const WARNING_MAP: Record<string, string> = {
  amount_not_recognized: 'importReport.warningAmountMissing',
}
function warningText(code: string): string {
  const key = WARNING_MAP[code]
  return key ? t(key) : code
}

async function handleFileRead(file: UploaderFileListItem | UploaderFileListItem[]) {
  const item = Array.isArray(file) ? file[0] : file
  if (!item.file) return
  step.value = 'parsing'
  try {
    const result = await parseReport(item.file)
    preview.value = result
    editableItems.value = result.items.map((i) => ({ ...i }))
    step.value = 'preview'
  } catch (err: unknown) {
    step.value = 'upload'
    const axiosErr = err as { response?: { data?: { message?: string } } }
    const msg = axiosErr?.response?.data?.message || t('importReport.parseFailed')
    showFailToast(msg)
  }
}

async function handleConfirm() {
  confirming.value = true
  try {
    const result = await confirmImport(editableItems.value)
    showSuccessToast(t('importReport.importSuccess', { update: result.updated, create: result.created }))
    history.back()
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
}
.upload-section,
.parsing-section,
.preview-section {
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
.parsing-section {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 60vh;
}
.preview-summary {
  padding: 12px 16px;
  font-size: 14px;
  color: var(--van-text-color-2);
}
.preview-item {
  padding: 12px 16px;
  border-bottom: 1px solid var(--van-border-color);
}
.preview-item.has-warning {
  background: var(--van-warning-color-light, #fffbe6);
}
.item-row {
  display: flex;
  gap: 8px;
}
.item-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 6px;
  font-size: 12px;
}
.matched-name {
  color: var(--van-text-color-2);
}
.warning-text {
  color: var(--van-warning-color, #ff976a);
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
</style>
