<template>
  <div class="category-manage-page">
    <PageHeader title="分类管理">
      <template #right>
        <van-icon name="plus" size="20" @click="showAddDialog" />
      </template>
    </PageHeader>

    <van-tabs v-model:active="activeTab" sticky @change="onTabChange">
      <van-tab title="实物" name="physical" />
      <van-tab title="金融" name="financial" />
    </van-tabs>

    <van-cell-group inset>
      <van-swipe-cell v-for="cat in categoryStore.categories" :key="cat.id">
        <van-cell :label="cat.is_system ? '系统分类' : '自定义'">
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
          <van-button square type="primary" text="编辑" class="swipe-btn" @click="showEditDialog(cat)" />
          <van-button square type="danger" text="删除" class="swipe-btn" @click="onDelete(cat)" />
        </template>
      </van-swipe-cell>
    </van-cell-group>

    <!-- Add/Edit Dialog -->
    <van-dialog
      v-model:show="dialogVisible"
      :title="editingId ? '编辑分类' : '添加分类'"
      show-cancel-button
      @confirm="onDialogConfirm"
    >
      <van-form ref="dialogForm" class="dialog-form">
        <van-field v-model="formData.name" label="名称" placeholder="请输入分类名称" />
        <van-field v-model="formData.icon" label="图标" placeholder="输入emoji图标" />
        <van-field v-model="formData.color" label="颜色" placeholder="#1989fa">
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
import { useCategoryStore } from '@/stores/category'
import type { Category } from '@/types'
import PageHeader from '@/components/common/PageHeader.vue'

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
    showToast('⚠️ 请输入名称')
    return
  }
  try {
    if (editingId.value) {
      await categoryStore.updateCategory(editingId.value, {
        name: formData.value.name,
        icon: formData.value.icon,
        color: formData.value.color
      })
      showToast('✅ 修改成功')
    } else {
      await categoryStore.createCategory({
        name: formData.value.name,
        icon: formData.value.icon,
        color: formData.value.color,
        asset_type: activeTab.value as 'physical' | 'financial'
      })
      showToast('✅ 添加成功')
    }
  } catch {
    // Error handled by interceptor
  }
}

async function onDelete(cat: Category) {
  try {
    await showConfirmDialog({ title: '确认删除', message: `确定要删除「${cat.name}」吗？` })
    await categoryStore.deleteCategory(cat.id)
    showToast('🗑️ 已删除')
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
