<template>
  <div class="manifesto-preview-page">
    <van-nav-bar
      :title="t('manifesto.preview')"
      left-arrow
      @click-left="router.back()"
    />
    <div v-if="templateId" class="preview-content">
      <ManifestoViewer
        :template-id="templateId"
        :title="state.title"
        :body="body"
        :signatures="signatures"
        :members="members"
      />

      <div class="actions">
        <van-button type="primary" block :loading="publishing" @click="onPublish">
          {{ t('manifesto.publish') }}
        </van-button>
      </div>
    </div>

    <van-action-sheet
      v-model:show="showChangeTypeSheet"
      :title="t('manifesto.changeTypeTitle')"
      :actions="changeTypeActions"
      @select="onChangeTypeSelect"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { showSuccessToast, showFailToast } from 'vant'
import ManifestoViewer from '@/components/manifesto/ManifestoViewer.vue'
import { useManifestoWizard } from '@/composables/useManifestoWizard'
import { useFamilyStore } from '@/stores/family'
import * as manifestoApi from '@/api/manifesto'

const { t } = useI18n()
const router = useRouter()
const { state, reset } = useManifestoWizard()
const familyStore = useFamilyStore()

const publishing = ref(false)
const showChangeTypeSheet = ref(false)
const existingManifestoId = ref<string | null>(null)

onMounted(async () => {
  if (!state.value.selectedTemplateId) {
    router.replace('/manifesto/template-select')
    return
  }
  if (familyStore.members.length === 0) {
    try {
      await familyStore.fetchFamily()
    } catch {
      // ignore — preview still works with empty members
    }
  }
  // Check if a manifesto already exists (edit vs create)
  try {
    const res = await manifestoApi.getCurrentManifesto()
    existingManifestoId.value = res.data.id
  } catch {
    existingManifestoId.value = null
  }
})

const templateId = computed(() => state.value.selectedTemplateId ?? '')

const body = computed(() => {
  if (state.value.body) return state.value.body
  return state.value.blocks.filter((b: string) => b.trim()).join('\n\n')
})

const signatures = computed(() =>
  familyStore.members.map(m => ({ name: m.display_name, data: null })),
)

const members = computed(() =>
  familyStore.members.map(m => ({ name: m.display_name, role: m.role })),
)

const changeTypeActions = computed(() => [
  {
    name: t('manifesto.minorUpdate'),
    subname: t('manifesto.minorHint'),
    value: 'minor',
  },
  {
    name: t('manifesto.majorUpdate'),
    subname: t('manifesto.majorHint'),
    value: 'major',
  },
])

function onPublish() {
  if (existingManifestoId.value) {
    showChangeTypeSheet.value = true
  } else {
    doCreate()
  }
}

async function doCreate() {
  publishing.value = true
  try {
    await manifestoApi.createManifesto({
      template_id: templateId.value,
      title: state.value.title,
      body: body.value,
      change_type: 'initial',
      trackable_clause_indices: state.value.trackableIndices.length > 0 ? state.value.trackableIndices : null,
      signing_deadline: state.value.signingDeadline,
    })
    reset()
    router.replace('/settings')
    showSuccessToast(t('manifesto.publishSuccess'))
  } catch {
    showFailToast(t('manifesto.publishFailed'))
  } finally {
    publishing.value = false
  }
}

async function onChangeTypeSelect(action: { value: string }) {
  showChangeTypeSheet.value = false
  publishing.value = true
  try {
    await manifestoApi.publishUpdate({
      template_id: templateId.value,
      title: state.value.title,
      body: body.value,
      change_type: action.value as 'minor' | 'major',
      trackable_clause_indices: state.value.trackableIndices.length > 0 ? state.value.trackableIndices : null,
      signing_deadline: state.value.signingDeadline,
    })
    reset()
    router.replace('/settings')
    showSuccessToast(t('manifesto.publishSuccess'))
  } catch {
    showFailToast(t('manifesto.publishFailed'))
  } finally {
    publishing.value = false
  }
}
</script>

<style scoped>
.manifesto-preview-page {
  min-height: 100vh;
  background: var(--bg-primary, #fff);
}

.preview-content {
  padding: 16px;
}

.actions {
  margin-top: 24px;
}
</style>
