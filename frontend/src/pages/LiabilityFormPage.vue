<template>
  <div class="liability-form-page">
    <PageHeader :title="isEdit ? '编辑负债' : '添加负债'" />
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
import { showToast } from 'vant'
import { useLiabilityStore } from '@/stores/liability'
import type { Liability } from '@/types'
import PageHeader from '@/components/common/PageHeader.vue'
import LiabilityForm from '@/components/liability/LiabilityForm.vue'

const route = useRoute()
const router = useRouter()
const liabilityStore = useLiabilityStore()
const submitting = ref(false)

const isEdit = computed(() => !!route.params.id)
const initialData = computed(() => isEdit.value ? liabilityStore.currentLiability || undefined : undefined)

async function onSubmit(data: Partial<Liability>) {
  submitting.value = true
  try {
    if (isEdit.value) {
      await liabilityStore.updateLiability(route.params.id as string, data)
      showToast('修改成功')
    } else {
      await liabilityStore.createLiability(data)
      showToast('添加成功')
    }
    router.back()
  } catch {
    // Error handled by interceptor
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
