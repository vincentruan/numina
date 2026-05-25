<template>
  <div class="ai-final-answer" :class="{ 'is-streaming': streaming, 'is-report': isReport }">
    <!-- Report header (spec §6.2) — only when isReport -->
    <div v-if="isReport && reportTitle" class="answer-report-header">
      <span class="report-icon" aria-hidden="true">📊</span>
      <span class="report-title">{{ reportTitle }}</span>
      <span v-if="reportMeta?.generatedAt" class="report-meta">{{ reportMeta.generatedAt }}</span>
    </div>

    <!-- Streaming skeleton (spec §6.1): rendered when streaming and no content yet -->
    <div v-if="streaming && !content" class="answer-skeleton" aria-hidden="true">
      <van-skeleton :row="3" row-width="100%" animate />
      <van-skeleton :row="1" row-width="60%" animate />
    </div>

    <!-- Answer content -->
    <div v-else ref="contentRef" class="answer-content">
      <!-- eslint-disable-next-line vue/no-v-html -- sanitized via DOMPurify -->
      <div class="answer-markdown" v-html="renderedContent" />
      <span v-if="streaming" class="answer-cursor" aria-hidden="true">▋</span>
    </div>

    <!-- Artifact row (spec §3.0 / Bundle C C2) — only when artifacts exist -->
    <div v-if="!streaming && artifacts && artifacts.length > 0" class="answer-artifacts">
      <p class="artifacts-title">{{ t('aiProcess.artifactsTitle') }}</p>
      <div class="artifacts-list">
        <AiArtifactLink
          v-for="artifact in artifacts"
          :key="artifact.id"
          :artifact="artifact"
        />
      </div>
    </div>

    <!-- Actions -->
    <div v-if="!streaming && showActions" class="answer-actions">
      <button class="action-btn" @click="copyContent">
        <van-icon name="description" />
        <span>{{ t('aiProcess.copy') }}</span>
      </button>
      <button v-if="showRegenerate" class="action-btn" @click="emit('regenerate')">
        <van-icon name="refresh" />
        <span>{{ t('aiProcess.regenerate') }}</span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { showToast } from 'vant'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import AiArtifactLink from './AiArtifactLink.vue'
import type { Artifact } from '@/types/agent-stream'

const props = defineProps<{
  content: string
  streaming?: boolean
  showActions?: boolean
  showRegenerate?: boolean
  isReport?: boolean
  reportTitle?: string
  reportMeta?: { generatedAt?: string; itemCount?: number }
  artifacts?: Artifact[]
}>()

const emit = defineEmits<{
  (e: 'regenerate'): void
}>()

const { t } = useI18n()
const contentRef = ref<HTMLElement | null>(null)
let scrollRAF: number | null = null

const renderedContent = computed(() => {
  if (!props.content) return ''
  try {
    const html = marked.parse(props.content, { async: false }) as string
    return DOMPurify.sanitize(html)
  } catch {
    return DOMPurify.sanitize(props.content)
  }
})

// Auto-scroll during streaming
watch(
  () => props.content,
  () => {
    if (!props.streaming) return
    if (scrollRAF) return
    scrollRAF = requestAnimationFrame(() => {
      scrollRAF = null
      contentRef.value?.scrollIntoView({ behavior: 'smooth', block: 'end' })
    })
  },
)

async function copyContent() {
  try {
    await navigator.clipboard.writeText(props.content)
    showToast(t('aiProcess.copySuccess'))
  } catch {
    showToast(t('aiProcess.copyFailed'))
  }
}
</script>

<style scoped>
.ai-final-answer {
  background: var(--card-bg);
  border-radius: 8px;
  padding: 14px;
  box-shadow: var(--shadow-elevated);
}

.is-report {
  padding: 16px;
  box-shadow: 0 2px 8px rgba(1, 1, 32, 0.1);
}

.answer-report-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--separator);
  margin-bottom: 12px;
}

.report-icon {
  font-size: 18px;
  background: var(--color-success);
  color: #ffffff;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.report-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.report-meta {
  font-size: 12px;
  color: var(--text-tertiary);
  flex-shrink: 0;
}

.answer-skeleton {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 4px 0;
}

.answer-artifacts {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--separator);
}

.artifacts-title {
  margin: 0 0 8px;
  font-size: 12px;
  color: var(--text-secondary);
}

.artifacts-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.answer-content {
  font-size: 14px;
  color: var(--text-primary);
  line-height: 1.7;
}

.answer-markdown :deep(p) { margin: 0 0 8px; }
.answer-markdown :deep(p:last-child) { margin-bottom: 0; }
.answer-markdown :deep(ul), .answer-markdown :deep(ol) { padding-left: 18px; margin: 4px 0 8px; }
.answer-markdown :deep(li) { margin-bottom: 4px; }
.answer-markdown :deep(strong) { color: var(--text-primary); }
.answer-markdown :deep(code) { background: var(--bg-secondary); padding: 1px 4px; border-radius: 4px; font-size: 12px; }
.answer-markdown :deep(pre) { background: var(--bg-secondary); padding: 10px; border-radius: 4px; overflow-x: auto; }
.answer-markdown :deep(pre code) { background: none; padding: 0; }

.answer-cursor {
  display: inline-block;
  animation: blink 1s step-end infinite;
  color: var(--color-primary);
  margin-left: 1px;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

.answer-actions {
  display: flex;
  gap: 8px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--separator);
}

.action-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  font-size: 13px;
  color: var(--text-secondary);
  background: var(--bg-secondary);
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.action-btn:hover {
  background: var(--bg-tertiary);
}

/* Mobile responsive (spec §8 mobile risk mitigation) */
@media (max-width: 768px) {
  .ai-final-answer {
    padding: 10px 12px;
  }

  .is-report {
    padding: 12px;
  }

  .report-title {
    font-size: 14px;
  }

  .report-icon {
    width: 28px;
    height: 28px;
    font-size: 16px;
  }

  .answer-artifacts {
    margin-top: 10px;
    padding-top: 10px;
  }

  .answer-content {
    font-size: 13px;
    line-height: 1.6;
  }

  .answer-markdown :deep(pre) {
    padding: 8px;
    font-size: 11px;
  }

  .answer-markdown :deep(code) {
    font-size: 11px;
  }

  .answer-actions {
    gap: 6px;
    margin-top: 10px;
    padding-top: 10px;
  }

  .action-btn {
    padding: 6px 10px;
    font-size: 12px;
    flex: 1;
    justify-content: center;
  }
}
</style>