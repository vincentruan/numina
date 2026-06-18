<script setup lang="ts">
/**
 * CodeBlock 组件
 *
 * 用于代码高亮展示（Artifact 预览、工具调用结果）
 */
import { computed } from 'vue'
import IIcon from '@/components/IIcon.vue'

const props = defineProps<{
  language: string
  code: string
  showLineNumbers?: boolean
}>()

// 简化的代码展示（无 external highlighting library）
const formattedCode = computed(() => {
  if (!props.showLineNumbers) return props.code

  const lines = props.code.split('\n')
  return lines
    .map((line, index) => `${index + 1}  ${line}`)
    .join('\n')
})

const languageLabel = computed(() => props.language || 'text')

// 复制代码到剪贴板
function copyCode() {
  navigator.clipboard.writeText(props.code)
}
</script>

<template>
  <div class="code-block">
    <!-- 语言标签 -->
    <div class="code-header">
      <span class="language-label">{{ languageLabel }}</span>
      <button class="copy-btn" @click="copyCode">
        <IIcon icon="copy" />
      </button>
    </div>

    <!-- 代码内容 -->
    <pre class="code-content" :class="{ 'with-line-numbers': showLineNumbers }">
      <code>{{ formattedCode }}</code>
    </pre>
  </div>
</template>

<style scoped>
.code-block {
  background: var(--bg-primary);
  border-radius: 8px;
  overflow: hidden;
}

.code-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: var(--card-bg);
  border-bottom: 1px solid var(--border-color);
}

.language-label {
  font-size: 12px;
  color: var(--text-secondary);
  font-family: monospace;
}

.copy-btn {
  display: flex;
  align-items: center;
  padding: 4px;
  background: transparent;
  border: none;
  cursor: pointer;
  color: var(--text-secondary);
}

.copy-btn:hover {
  color: var(--van-primary-color);
}

.code-content {
  padding: 12px;
  margin: 0;
  font-size: 13px;
  font-family: 'Menlo', 'Monaco', 'Courier New', monospace;
  line-height: 1.5;
  overflow-x: auto;
  white-space: pre;
  color: var(--text-primary);
}

.with-line-numbers {
  padding-left: 8px;
}

/* 375px */
@media (max-width: 375px) {
  .code-content {
    font-size: 11px;
    padding: 8px;
  }
}
</style>