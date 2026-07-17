<script setup lang="ts">
/**
 * CodeBlock 组件
 *
 * 用于代码高亮展示（Artifact 预览、工具调用结果）
 *
 * DeerFlow pattern (message-group.tsx bash tool):
 *   <CodeBlock className="mx-0 cursor-pointer border-none px-0"
 *              showLineNumbers={false} language="bash" code={command} />
 * - No header, no border, no padding when `bare` mode is used
 */
import { computed } from 'vue'
import IIcon from '@/components/IIcon.vue'
import CopyButton from '@/components/ai-chat/CopyButton.vue'

const props = defineProps<{
  language: string
  code: string
  showLineNumbers?: boolean
  /** DeerFlow "border-none px-0" mode: no header, no border, minimal padding */
  bare?: boolean
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
</script>

<template>
  <div class="code-block" :class="{ bare }">
    <!-- 语言标签 + 复制按钮（bare 模式下隐藏） -->
    <div v-if="!bare" class="code-header">
      <span class="language-label">{{ languageLabel }}</span>
      <CopyButton v-slot="{ copy }" :content="code">
        <button class="copy-btn" @click="copy">
          <IIcon icon="copy" />
        </button>
      </CopyButton>
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

/* DeerFlow bare mode: mx-0 border-none px-0 - no background, no border, no radius */
.code-block.bare {
  background: transparent;
  border: none;
  border-radius: 0;
  overflow: visible;
  cursor: pointer;
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

/* DeerFlow bare mode: px-0 = no padding */
.code-block.bare .code-content {
  padding: 0;
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
