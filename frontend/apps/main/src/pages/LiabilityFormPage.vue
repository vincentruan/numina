<template>
  <div class="liability-form-page">
    <PageHeader :title="isEdit ? t('liability.editLiability') : t('liability.addLiability')" />
    <LiabilityForm
      :initial-data="initialData"
      :is-edit="isEdit"
      :loading="submitting"
      @submit="onSubmit"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showSuccessToast, showFailToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { useLiabilityStore } from '@/stores/liability'
import type { LiabilityRequestPayload } from '@/types'
import PageHeader from '@/components/common/PageHeader.vue'
import LiabilityForm from '@/components/liability/LiabilityForm.vue'

const { t } = useI18n()

const route = useRoute()
const router = useRouter()
const liabilityStore = useLiabilityStore()
const submitting = ref(false)

const isEdit = computed(() => !!route.params.id)
const initialData = computed(() => isEdit.value ? liabilityStore.currentLiability || undefined : undefined)

async function onSubmit(data: LiabilityRequestPayload) {
  submitting.value = true
  try {
    if (isEdit.value) {
      await liabilityStore.updateLiability(route.params.id as string, data)
      showSuccessToast(t('toast.updateSuccess'))
    } else {
      await liabilityStore.createLiability(data)
      showSuccessToast(t('toast.addSuccess'))
    }
    if (!isEdit.value) {
      router.replace({ path: '/finance', query: { tab: 'liabilities' } })
    } else {
      router.back()
    }
  } catch {
    showFailToast(t('toast.operationFailed'))
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  if (isEdit.value) {
    liabilityStore.fetchLiability(route.params.id as string)
  }
})
</script>

<style scoped>
.liability-form-page {
  background: var(--bg-secondary);
  min-height: 100vh;
}
</style>
