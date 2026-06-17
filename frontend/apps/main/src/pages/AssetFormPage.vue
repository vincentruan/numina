<template>
  <div class="asset-form-page">
    <PageHeader :title="isEdit ? t('asset.editAsset') : t('asset.addAsset')" />
    <AssetForm
      :initial-data="initialData"
      :categories="categoryStore.categories"
      :is-edit="isEdit"
      :loading="submitting"
      @submit="onSubmit"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showToast, showSuccessToast, showFailToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { useAssetStore } from '@/stores/asset'
import { useCategoryStore } from '@/stores/category'
import type { Asset } from '@/types'
import PageHeader from '@/components/common/PageHeader.vue'
import AssetForm from '@/components/asset/AssetForm.vue'

const { t } = useI18n()

const route = useRoute()
const router = useRouter()
const assetStore = useAssetStore()
const categoryStore = useCategoryStore()
const submitting = ref(false)

const isEdit = computed(() => !!route.params.id)
const initialData = computed(() => isEdit.value ? assetStore.currentAsset || undefined : undefined)

async function onSubmit(data: Partial<Asset>) {
  submitting.value = true
  try {
    if (isEdit.value) {
      await assetStore.updateAsset(route.params.id as string, data)
      showSuccessToast(t('toast.updateSuccess'))
    } else {
      await assetStore.createAsset(data)
      showSuccessToast(t('toast.addSuccess'))
    }
    // Dashboard refreshes naturally via staleness guard (2 min TTL)
    // invalidateDashboard() already called by asset store methods
    router.back()
  } catch {
    showFailToast(t('toast.operationFailed'))
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  categoryStore.fetchCategories()
  if (isEdit.value) {
    assetStore.fetchAsset(route.params.id as string)
  }
})
</script>

<style scoped>
.asset-form-page {
  background: var(--bg-secondary);
  min-height: 100vh;
}
</style>
