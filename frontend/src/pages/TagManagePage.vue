<template>
  <div class="tag-manage-page">
    <PageHeader title="标签管理">
      <template #right>
        <van-icon name="plus" size="20" @click="showAddDialog" />
      </template>
    </PageHeader>

    <van-cell-group inset>
      <van-swipe-cell v-for="tag in tags" :key="tag.id">
        <van-cell :title="tag.name">
          <template #icon>
            <van-tag :color="tag.color" size="medium" class="tag-preview">{{ tag.name }}</van-tag>
          </template>
        </van-cell>
        <template #right>
          <van-button square type="primary" text="编辑" class="swipe-btn" @click="showEditDialog(tag)" />
          <van-button square type="danger" text="删除" class="swipe-btn" @click="onDelete(tag)" />
        </template>
      </van-swipe-cell>
      <van-empty v-if="!tags.length" description="暂无标签，快来创建第一个吧">
        <template #bottom>
          <van-button type="primary" round size="small" @click="showAddDialog">
            ＋ 添加标签
          </van-button>
        </template>
      </van-empty>
    </van-cell-group>

    <!-- Add/Edit Dialog -->
    <van-dialog
      v-model:show="dialogVisible"
      :title="editingId ? '编辑标签' : '添加标签'"
      show-cancel-button
      @confirm="onDialogConfirm"
    >
      <van-form class="dialog-form">
        <van-field v-model="formData.name" label="名称" placeholder="请输入标签名称" />
        <van-field v-model="formData.color" label="颜色" placeholder="#1989fa">
          <template #right-icon>
            <div class="color-preview" :style="{ background: formData.color }" />
          </template>
        </van-field>
        <div class="color-presets">
          <div
            v-for="color in presetColors"
            :key="color"
            class="preset-dot"
            :class="{ active: formData.color === color }"
            :style="{ background: color }"
            @click="formData.color = color"
          />
        </div>
      </van-form>
    </van-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { showConfirmDialog, showToast } from 'vant'
import { useI18n } from 'vue-i18n'
import * as tagApi from '@/api/tags'
import type { Tag } from '@/types'
import PageHeader from '@/components/common/PageHeader.vue'

const { t } = useI18n()

const tags = ref<Tag[]>([])
const dialogVisible = ref(false)
const editingId = ref<string | null>(null)

const formData = ref({
  name: '',
  color: '#1989fa'
})

const presetColors = [
  '#1989fa', '#07c160', '#ff976a', '#ee0a24', '#7232dd',
  '#f2826a', '#4fc08d', '#1cbbb4', '#6149f6', '#ff6034'
]

async function fetchTags() {
  const res = await tagApi.getTags()
  tags.value = res.data
}

function showAddDialog() {
  editingId.value = null
  formData.value = { name: '', color: '#1989fa' }
  dialogVisible.value = true
}

function showEditDialog(tag: Tag) {
  editingId.value = tag.id
  formData.value = { name: tag.name, color: tag.color }
  dialogVisible.value = true
}

async function onDialogConfirm() {
  if (!formData.value.name) {
    showToast(t('toast.nameRequired'))
    return
  }
  try {
    if (editingId.value) {
      await tagApi.updateTag(editingId.value, formData.value)
      showToast(t('toast.updateSuccess'))
    } else {
      await tagApi.createTag(formData.value)
      showToast(t('toast.addSuccess'))
    }
    await fetchTags()
  } catch {
    // Error handled by interceptor
  }
}

async function onDelete(tag: Tag) {
  try {
    await showConfirmDialog({ title: t('common.confirm'), message: t('toast.confirmDelete', { name: tag.name }) })
    await tagApi.deleteTag(tag.id)
    showToast(t('toast.deleteSuccess'))
    await fetchTags()
  } catch {
    // cancelled
  }
}

onMounted(() => {
  fetchTags()
})
</script>

<style scoped>
.tag-manage-page {
  background: var(--bg-secondary);
  min-height: 100vh;
}
.tag-preview {
  margin-right: 8px;
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
.color-presets {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 8px 16px;
}
.preset-dot {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  cursor: pointer;
  border: 2px solid transparent;
  transition: border-color 0.2s;
}
.preset-dot.active {
  border-color: var(--text-primary);
}
</style>
