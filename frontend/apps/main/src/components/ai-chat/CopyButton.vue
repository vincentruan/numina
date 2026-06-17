<script setup lang="ts">
/**
 * CopyButton 组件
 *
 * 简化的复制按钮，用于复制文本内容
 */
import { showToast, showSuccessToast } from 'vant'
import i18n from '@/i18n'
import IIcon from '@/components/IIcon.vue'

const props = defineProps<{
  content: string
}>()

function handleCopy() {
  navigator.clipboard.writeText(props.content)
  showSuccessToast(i18n.global.t('aiChat.copiedSuccess'))
}
</script>

<template>
  <button class="copy-button" @click="handleCopy">
    <IIcon icon="copy" class="copy-icon" />
  </button>
</template>

<style scoped>
.copy-button {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 6px;
  background: transparent;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}

.copy-button:hover {
  background: var(--bg-primary);
  border-color: var(--van-primary-color);
}

.copy-icon {
  width: 14px;
  height: 14px;
  color: var(--text-secondary);
}

.copy-button:hover .copy-icon {
  color: var(--van-primary-color);
}
</style>