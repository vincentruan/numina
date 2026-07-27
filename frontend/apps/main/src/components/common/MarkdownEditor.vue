<script setup lang="ts">
import { computed } from 'vue'
import { Editor } from '@bytemd/vue-next'
import gfm from '@bytemd/plugin-gfm'
import highlight from '@bytemd/plugin-highlight'
import { uploadImage } from '@/api/upload'
import 'bytemd/dist/index.css'
import 'highlight.js/styles/github.css'

defineProps<{
  modelValue: string
  placeholder?: string
  disabled?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const plugins = computed(() => [gfm(), highlight()])

function handleChange(v: string) {
  emit('update:modelValue', v)
}

async function handleUploadImages(files: File[]) {
  const results: { title: string; url: string }[] = []
  for (const file of files) {
    try {
      const res = await uploadImage(file)
      results.push({ title: file.name, url: res.data.url })
    } catch {
      // skip failed uploads silently — user sees no insertion
    }
  }
  return results
}
</script>

<template>
  <div class="md-editor" :class="{ 'md-editor--disabled': disabled }">
    <Editor
      :value="modelValue"
      :plugins="plugins"
      :placeholder="placeholder"
      :disabled="disabled"
      @change="handleChange"
      @upload-images="handleUploadImages"
    />
  </div>
</template>

<style scoped>
.md-editor {
  border: 1px solid var(--van-cell-border-color, #ebedf0);
  border-radius: 8px;
  overflow: hidden;
}

.md-editor--disabled {
  opacity: 0.6;
  pointer-events: none;
}

/* prevent double scrollbar — editor fills container height */
.md-editor :deep(.bytemd) {
  height: auto;
  min-height: 200px;
  border: none;
  border-radius: 0;
}

.md-editor :deep(.bytemd-editor) {
  overflow: visible;
}

.md-editor :deep(.CodeMirror) {
  height: auto;
  min-height: 180px;
  /* 16px prevents iOS auto-zoom on focus */
  font-size: 16px;
  font-family: 'SF Mono', 'Menlo', 'Monaco', monospace;
}

.md-editor :deep(.CodeMirror-scroll) {
  overflow: visible !important;
  min-height: 180px;
}

/* mobile-friendly toolbar: 44px touch targets */
.md-editor :deep(.bytemd-toolbar) {
  position: sticky;
  top: 0;
  z-index: 10;
  background: var(--van-background-2, #f7f8fa);
  border-bottom: 1px solid var(--van-cell-border-color, #ebedf0);
  flex-wrap: wrap;
  padding: 4px 8px;
  overflow-x: auto;
}

.md-editor :deep(.bytemd-toolbar-icon) {
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  color: var(--van-text-color, #323233);
}

.md-editor :deep(.bytemd-toolbar-icon:hover),
.md-editor :deep(.bytemd-toolbar-icon.bytemd-tippy-active) {
  background: var(--van-primary-color-light, rgba(100, 101, 241, 0.1));
  color: var(--van-primary-color, #6366f1);
}

/* preview pane */
.md-editor :deep(.bytemd-preview) {
  font-size: 15px;
  line-height: 1.6;
  padding: 16px;
}

/* mobile: full-screen preview when preview mode active */
@media (max-width: 767px) {
  .md-editor :deep(.bytemd[data-mode='split']) {
    flex-direction: column;
  }

  .md-editor :deep(.bytemd[data-mode='split'] .bytemd-editor-area) {
    display: none;
  }

  .md-editor :deep(.bytemd[data-mode='split'] .bytemd-preview) {
    flex: 1;
    border-left: none;
    border-top: 1px solid var(--van-cell-border-color, #ebedf0);
  }
}

[data-theme='dark'] .md-editor :deep(.bytemd) {
  background: var(--van-background-2, #1c1c1e);
  color: var(--van-text-color, #f5f5f5);
}

[data-theme='dark'] .md-editor :deep(.bytemd-toolbar) {
  background: var(--van-background-2, #1c1c1e);
  border-color: var(--van-cell-border-color, #3a3a3c);
}

[data-theme='dark'] .md-editor :deep(.CodeMirror) {
  background: var(--van-background-2, #1c1c1e);
  color: var(--van-text-color, #f5f5f5);
}
</style>
