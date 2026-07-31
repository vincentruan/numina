<template>
  <div class="manifesto-edit-page">
    <van-nav-bar
      :title="t('manifesto.editTitle')"
      left-arrow
      @click-left="router.back()"
    />
    <div class="edit-content">
      <van-cell-group inset>
        <van-field
          :model-value="state.title"
          :label="t('manifesto.title')"
          :placeholder="t('manifesto.titlePlaceholder')"
          maxlength="100"
          show-word-limit
          @update:model-value="state.title = $event"
        />
      </van-cell-group>

      <div class="section-label">{{ t('manifesto.addBlock') }}</div>
      <div class="editor-wrapper">
        <BlockEditor
          :model-value="editorValue"
          @update:model-value="onEditorUpdate"
        />
      </div>

      <van-cell-group inset class="deadline-group">
        <van-cell
          is-link
          :title="t('manifesto.signingDeadline')"
          :value="deadlineDisplay"
          @click="showDeadlinePicker = true"
        />
      </van-cell-group>

      <van-popup v-model:show="showDeadlinePicker" position="bottom" round>
        <van-date-picker
          v-model="deadlinePickerValue"
          :title="t('manifesto.signingDeadline')"
          :min-date="minDate"
          @confirm="onDeadlineConfirm"
          @cancel="showDeadlinePicker = false"
        />
      </van-popup>

      <van-cell-group inset>
        <van-cell
          is-link
          :title="t('manifesto.switchTemplate')"
          @click="router.push('/manifesto/template-select')"
        />
      </van-cell-group>

      <div class="actions">
        <van-button type="primary" block @click="goPreview">
          {{ t('manifesto.preview') }}
        </van-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import BlockEditor from '@/components/manifesto/BlockEditor.vue'
import { useManifestoWizard } from '@/composables/useManifestoWizard'

const { t } = useI18n()
const router = useRouter()
const { state } = useManifestoWizard()

const showDeadlinePicker = ref(false)

const editorValue = computed(() => ({
  blocks: state.value.blocks,
  trackableIndices: state.value.trackableIndices,
}))

function onEditorUpdate(val: { blocks: string[]; trackableIndices: number[] }) {
  state.value.blocks = val.blocks
  state.value.trackableIndices = val.trackableIndices
}

const deadlineDisplay = computed(() => {
  if (!state.value.signingDeadline) return t('manifesto.noDeadline')
  return state.value.signingDeadline
})

const deadlinePickerValue = ref<string[]>([])

const minDate = new Date()

function onDeadlineConfirm({ selectedValues }: { selectedValues: string[] }) {
  state.value.signingDeadline = selectedValues.join('-')
  showDeadlinePicker.value = false
}

function goPreview() {
  if (!state.value.selectedTemplateId) {
    router.push('/manifesto/template-select')
    return
  }
  // Sync body from blocks
  state.value.body = state.value.blocks.filter((b: string) => b.trim()).join('\n\n')
  router.push('/manifesto/preview')
}
</script>

<style scoped>
.manifesto-edit-page {
  min-height: 100vh;
  background: var(--bg-primary, #fff);
}

.edit-content {
  padding-bottom: 24px;
}

.section-label {
  padding: 16px 16px 8px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary, #0a0a0a);
}

.editor-wrapper {
  padding: 0 16px;
}

.deadline-group {
  margin-top: 12px;
}

.actions {
  padding: 24px 16px 0;
}
</style>
