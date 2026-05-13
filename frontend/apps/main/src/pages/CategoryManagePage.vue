<template>
  <div class="category-manage-page">
    <PageHeader :title="t('settings.categoryManageTitle')">
      <template #right>
        <van-icon name="plus" size="20" @click="showAddDialog" />
      </template>
    </PageHeader>

    <van-tabs v-model:active="activeTab" sticky @change="onTabChange">
      <van-tab :title="t('settings.categoryTabPhysical')" name="physical" />
      <van-tab :title="t('settings.categoryTabFinancial')" name="financial" />
    </van-tabs>

    <van-cell-group inset>
      <van-swipe-cell v-for="cat in categoryStore.categories" :key="cat.id">
        <van-cell :label="cat.is_system ? t('settings.categorySystemLabel') : t('settings.categoryCustomLabel')">
          <template #title>
            <div class="cat-title">
              <div v-if="cat.icon.startsWith('icon-')" class="cat-icon-wrap" :style="{ background: cat.color }">
                <svg class="cat-icon-svg" aria-hidden="true">
                  <use :href="`#${cat.icon}`" />
                </svg>
              </div>
              <span v-else class="cat-icon-emoji">{{ cat.icon }}</span>
              <span>{{ cat.name }}</span>
            </div>
          </template>
          <template #value>
            <div class="color-dot" :style="{ background: cat.color }" />
          </template>
        </van-cell>
        <template v-if="!cat.is_system" #right>
          <van-button square type="primary" :text="t('settings.categoryEditBtn')" class="swipe-btn" @click="showEditDialog(cat)" />
          <van-button square type="danger" :text="t('settings.categoryDeleteBtn')" class="swipe-btn" @click="onDelete(cat)" />
        </template>
      </van-swipe-cell>
    </van-cell-group>

    <!-- Add/Edit Dialog -->
    <van-dialog
      v-model:show="dialogVisible"
      :title="editingId ? t('settings.categoryEditDialogTitle') : t('settings.categoryAddDialogTitle')"
      show-cancel-button
      @confirm="onDialogConfirm"
    >
      <van-form ref="dialogForm" class="dialog-form">
        <van-field v-model="formData.name" :label="t('settings.categoryFieldName')" :placeholder="t('settings.categoryNamePlaceholder')" />
        <van-field v-model="formData.icon" :label="t('settings.categoryFieldIcon')" :placeholder="t('settings.categoryIconPlaceholder')" />
        <van-field v-model="formData.color" :label="t('settings.categoryFieldColor')" :placeholder="t('settings.categoryColorPlaceholder')">
          <template #right-icon>
            <div class="color-preview" :style="{ background: formData.color }" />
          </template>
        </van-field>
      </van-form>
    </van-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { showConfirmDialog, showToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { useCategoryStore } from '@/stores/category'
import type { Category } from '@/types'
import PageHeader from '@/components/common/PageHeader.vue'

const { t } = useI18n()

const categoryStore = useCategoryStore()
const activeTab = ref('physical')
const dialogVisible = ref(false)
const editingId = ref<string | null>(null)

const formData = ref({
  name: '',
  icon: '',
  color: '#1989fa'
})

function onTabChange() {
  categoryStore.fetchCategories(activeTab.value)
}

function showAddDialog() {
  editingId.value = null
  formData.value = { name: '', icon: '📦', color: '#1989fa' }
  dialogVisible.value = true
}

function showEditDialog(cat: Category) {
  editingId.value = cat.id
  formData.value = { name: cat.name, icon: cat.icon, color: cat.color }
  dialogVisible.value = true
}

async function onDialogConfirm() {
  if (!formData.value.name) {
    showToast(t('toast.nameRequired'))
    return
  }
  try {
    if (editingId.value) {
      await categoryStore.updateCategory(editingId.value, {
        name: formData.value.name,
        icon: formData.value.icon,
        color: formData.value.color
      })
      showToast(t('toast.updateSuccess'))
    } else {
      await categoryStore.createCategory({
        name: formData.value.name,
        icon: formData.value.icon,
        color: formData.value.color,
        asset_type: activeTab.value as 'physical' | 'financial'
      })
      showToast(t('toast.addSuccess'))
    }
  } catch {
    // Error handled by interceptor
  }
}

async function onDelete(cat: Category) {
  try {
    await showConfirmDialog({ title: t('common.confirm'), message: t('toast.confirmDelete', { name: cat.name }) })
    await categoryStore.deleteCategory(cat.id)
    showToast(t('toast.deleteSuccess'))
  } catch {
    // cancelled
  }
}

onMounted(() => {
  categoryStore.fetchCategories(activeTab.value)
})
</script>

<style scoped>
.category-manage-page {
  background: var(--bg-secondary);
  min-height: 100vh;
}
.color-dot {
  width: 16px;
  height: 16px;
  border-radius: 50%;
}
.cat-title {
  display: flex;
  align-items: center;
  gap: 8px;
}
.cat-icon-wrap {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.cat-icon-svg {
  width: 16px;
  height: 16px;
  fill: white;
  color: white;
}
.cat-icon-emoji {
  font-size: 20px;
  line-height: 1;
}
.swipe-btn {
  height: 100%;
}
.dialog-form {
  padding: 16px;
}
.color-preview {
  width: 20px;
  height: 20px;
  border-radius: 4px;
  border: 1px solid var(--separator);
}
</style>
