<template>
  <div class="asset-form-page">
    <PageHeader :title="isEdit ? '编辑资产' : '添加资产'" />
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
import { showToast } from 'vant'
import { useAssetStore } from '@/stores/asset'
import { useCategoryStore } from '@/stores/category'
import { useDashboardStore } from '@/stores/dashboard'
import type { Asset } from '@/types'
import PageHeader from '@/components/common/PageHeader.vue'
import AssetForm from '@/components/asset/AssetForm.vue'

const route = useRoute()
const router = useRouter()
const assetStore = useAssetStore()
const categoryStore = useCategoryStore()
const dashboardStore = useDashboardStore()
const submitting = ref(false)

const isEdit = computed(() => !!route.params.id)
const initialData = computed(() => isEdit.value ? assetStore.currentAsset || undefined : undefined)

async function onSubmit(data: Partial<Asset>) {
  submitting.value = true
  try {
    if (isEdit.value) {
      await assetStore.updateAsset(route.params.id as string, data)
      showToast('修改成功')
    } else {
      await assetStore.createAsset(data)
      showToast('添加成功')
    }
    await dashboardStore.fetchAll()
    router.back()
  } catch {
    // Error handled by interceptor
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
  background: #f7f8fa;
  min-height: 100vh;
}
</style>
