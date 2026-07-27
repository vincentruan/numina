<template>
  <div class="tag-selector">
    <div class="selected-tags">
      <van-tag
        v-for="tag in selectedTags"
        :key="tag.id"
        closeable
        type="primary"
        size="medium"
        @close="removeTag(tag.id)"
      >
        {{ tag.name }}
      </van-tag>
      <van-tag plain type="primary" @click="showPopup = true">{{ t('tagSelector.addTag') }}</van-tag>
    </div>

    <van-popup v-model:show="showPopup" position="bottom" round :style="{ height: '60%' }">
      <div class="popup-header">
        <span class="popup-title">{{ t('tagSelector.selectTag') }}</span>
        <van-icon name="cross" @click="showPopup = false" />
      </div>

      <div class="popup-create">
        <van-field
          v-model="newTagName"
          :placeholder="t('tagSelector.createPlaceholder')"
          clearable
        >
          <template #right-icon>
            <van-icon
              v-if="newTagName.trim()"
              name="plus"
              style="cursor:pointer;color:var(--van-primary-color)"
              @click="createTag"
            />
          </template>
        </van-field>
      </div>

      <div class="tag-list">
        <div
          v-for="tag in tags"
          :key="tag.id"
          class="tag-option"
          :class="{ selected: modelValue.includes(tag.id) }"
          @click="toggleTag(tag.id)"
        >
          <span>{{ tag.name }}</span>
          <van-icon v-if="modelValue.includes(tag.id)" name="success" />
        </div>
        <div v-if="!tags.length" class="tag-empty">{{ t('tagSelector.empty') }}</div>
      </div>
    </van-popup>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { showSuccessToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { createTag as apiCreateTag } from '@/api/tags'
import type { Tag } from '@/types'

const { t } = useI18n()

const props = defineProps<{
  modelValue: string[]
  tags: Tag[]
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string[]]
  'tag-created': [tag: Tag]
}>()

const showPopup = ref(false)
const newTagName = ref('')

const selectedTags = computed(() =>
  props.tags.filter(t => props.modelValue.includes(t.id))
)

function toggleTag(id: string) {
  const current = [...props.modelValue]
  const idx = current.indexOf(id)
  if (idx === -1) current.push(id)
  else current.splice(idx, 1)
  emit('update:modelValue', current)
}

function removeTag(id: string) {
  emit('update:modelValue', props.modelValue.filter(t => t !== id))
}

async function createTag() {
  const name = newTagName.value.trim()
  if (!name) return
  try {
    const res = await apiCreateTag({ name, color: '#1989fa' })
    emit('tag-created', res.data)
    emit('update:modelValue', [...props.modelValue, res.data.id])
    newTagName.value = ''
    showSuccessToast(t('toast.tagCreated'))
  } catch {
    // error handled by interceptor
  }
}
</script>

<style scoped>
.tag-selector { padding: 4px 0; }
.selected-tags { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.popup-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  border-bottom: 1px solid var(--van-border-color);
}
.popup-title { font-size: 16px; font-weight: 600; }
.popup-create { padding: 8px 0; }
.tag-list { padding: 0 16px; overflow-y: auto; }
.tag-option {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 0;
  border-bottom: 1px solid var(--van-border-color);
  cursor: pointer;
  font-size: 14px;
}
.tag-option.selected { color: var(--van-primary-color); }
.tag-empty {
  padding: 24px 0;
  text-align: center;
  color: var(--van-text-color-3);
  font-size: 13px;
}
</style>
