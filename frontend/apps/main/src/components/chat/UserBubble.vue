<script setup lang="ts">
/**
 * UserBubble — User message bubble following DeerFlow pattern
 *
 * DeerFlow reference: frontend/src/components/workspace/messages/message-list-item.tsx
 *
 * Key patterns:
 * - ml-auto (right-aligned within message-row)
 * - flex flex-col gap-2 (column layout, bubble + toolbar below)
 * - w-fit (narrow bubble that fits content)
 * - max-width 70% (prevents overly wide bubbles)
 * - Bubble contains ONLY user text; copy + time are below the bubble
 *
 * Markdown rendering:
 * User content is rendered as markdown (like AI responses) so formatted
 * input (lists, code, links) displays properly.
 */
import { useI18n } from 'vue-i18n'
import MarkdownContent from '@/components/ai-chat/MarkdownContent.vue'
import CopyButton from '@/components/ai-chat/CopyButton.vue'

interface Props {
  content: string
  displayTime: string
  sendStatus?: 'sending' | 'sent' | 'failed'
}

const props = defineProps<Props>()

const emit = defineEmits<{
  copy: []
  retry: []
}>()

const { t } = useI18n()
</script>

<template>
  <div class="user-bubble">
    <!-- Bubble: only the user's text content (DeerFlow: w-fit, right-aligned) -->
    <div class="bubble-content">
      <MarkdownContent :content="content" class="bubble-markdown" />
    </div>

    <!-- Send status indicator (below bubble) -->
    <div v-if="sendStatus === 'sending'" class="send-status sending" aria-live="polite">
      <span class="status-dot" aria-hidden="true" />
      <span>{{ t('aiChat.sendingMessage') }}</span>
    </div>
    <div v-if="sendStatus === 'failed'" class="send-status failed" aria-live="polite">
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true">
        <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
      </svg>
      <span>{{ t('aiChat.sendFailed') }}</span>
      <button class="retry-btn" :aria-label="t('aiChat.retry')" @click="emit('retry')">
        {{ t('aiChat.retry') }}
      </button>
    </div>

    <!-- Footer: copy + time (below bubble, right-aligned) -->
    <div class="bubble-footer">
      <div class="bubble-actions">
        <CopyButton v-slot="{ copy }" :content="content">
          <button class="action-btn" :aria-label="t('aiChat.copyAria')" @click="copy(); emit('copy')">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
              <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
              <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
            </svg>
          </button>
        </CopyButton>
      </div>
      <span class="bubble-time">{{ displayTime }}</span>
    </div>
  </div>
</template>

<style scoped>
/* DeerFlow pattern: ml-auto + flex column → right-aligned bubble with toolbar below */
.user-bubble {
  margin-left: auto;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
  max-width: 70%;
  min-width: 60px;
}

.bubble-content {
  /* DeerFlow-style: neutral gray bg + theme-aware text (black in light, white in dark). */
  background: #e8e8ec;
  color: var(--text-primary);
  border-radius: 16px 16px 4px 16px;
  padding: 10px 14px;
  word-break: break-word;
  max-width: 100%;
}

/* Wrap FULL selector in :global() - `:global([data-theme='dark']) .x` compiles
 * without the [data-v-xxx] scoping attr and never matches. See AIChatInput.vue:472. */
:global([data-theme='dark'] .bubble-content) {
  background: #27272a;
}

/* Markdown content inside user bubble */
.bubble-markdown {
  font-size: 15px;
  line-height: 1.5;
}

.bubble-markdown :deep(p) {
  margin: 0;
}

.bubble-markdown :deep(p + p) {
  margin-top: 0.5em;
}

.bubble-markdown :deep(pre) {
  margin: 6px 0;
  border-radius: 8px;
}

.bubble-markdown :deep(code) {
  font-size: 0.9em;
}

.bubble-markdown :deep(ul),
.bubble-markdown :deep(ol) {
  margin: 4px 0;
  padding-left: 1.5em;
}

.bubble-markdown :deep(a) {
  color: var(--van-primary-color);
}

/* Send status (below bubble) */
.send-status {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  opacity: 0.8;
  padding: 0 4px;
}

.send-status.sending .status-dot {
  width: 6px;
  height: 6px;
  background: currentColor;
  border-radius: 50%;
  animation: pulse 1.5s ease-in-out infinite;
}

.send-status.failed {
  color: #f87171;
}

.retry-btn {
  margin-left: 4px;
  padding: 2px 8px;
  font-size: 12px;
  color: #f87171;
  background: rgba(248, 113, 113, 0.1);
  border: 1px solid rgba(248, 113, 113, 0.3);
  border-radius: 4px;
  cursor: pointer;
  transition: background 0.15s;
}

.retry-btn:hover {
  background: rgba(248, 113, 113, 0.2);
}

/* Footer (below bubble, right-aligned) */
.bubble-footer {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 4px;
}

.bubble-actions {
  display: flex;
  gap: 4px;
  opacity: 0;
  transition: opacity 0.2s;
}

.user-bubble:hover .bubble-actions,
.user-bubble:focus-within .bubble-actions {
  opacity: 1;
}

.action-btn {
  padding: 4px;
  background: transparent;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  color: inherit;
  opacity: 0.7;
  transition: opacity 0.15s;
}

.action-btn:hover {
  opacity: 1;
}

.bubble-time {
  font-size: 11px;
  opacity: 0.6;
}

/* Edit mode */
.edit-mode {
  background: var(--bubble-user-bg, rgba(99, 102, 241, 0.22));
  border-radius: 16px;
  padding: 8px;
}

.edit-input {
  background: transparent;
  border: none;
}

.edit-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 8px;
}

.cancel-btn,
.send-btn {
  padding: 6px 12px;
  font-size: 13px;
  border-radius: 6px;
  border: none;
  cursor: pointer;
}

.cancel-btn {
  background: rgba(255, 255, 255, 0.1);
  color: inherit;
}

.send-btn {
  background: var(--van-primary-color);
  color: #fff;
}

.send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

@keyframes pulse {
  0%, 100% { opacity: 0.4; }
  50% { opacity: 1; }
}
</style>
