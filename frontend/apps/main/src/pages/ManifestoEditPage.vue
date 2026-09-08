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
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { showLoadingToast, closeToast } from 'vant'
import BlockEditor from '@/components/manifesto/BlockEditor.vue'
import { useManifestoWizard } from '@/composables/useManifestoWizard'
import { getCurrentManifesto } from '@/api/manifesto'

const { t } = useI18n()
const router = useRouter()
const { state } = useManifestoWizard()

const isLoading = ref(false)

onMounted(async () => {
  // Only load from API if sessionStorage is empty (fresh session)
  const hasLocalData = state.value.title || state.value.body || state.value.blocks.some(b => b.trim())

  if (!hasLocalData) {
    isLoading.value = true
    showLoadingToast({ message: t('common.loading'), forbidClick: true, duration: 0 })

    try {
      const res = await getCurrentManifesto()
      const manifesto = res.data

      // If there's an active manifesto with version data, populate wizard state
      if (manifesto?.current_version) {
        const version = manifesto.current_version
        state.value.selectedTemplateId = version.template_id
        state.value.title = version.title
        state.value.body = version.body
        state.value.blocks = version.body.split('\n\n')
        state.value.trackableIndices = version.trackable_clause_indices || []
        state.value.signingDeadline = manifesto.signing_deadline
          ? manifesto.signing_deadline.slice(0, 10)
          : null
      }
    } catch (error) {
      // Silently fail - user might be creating a new manifesto
      console.error('Failed to load manifesto:', error)
    } finally {
      isLoading.value = false
      closeToast()
    }
  }
})

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
