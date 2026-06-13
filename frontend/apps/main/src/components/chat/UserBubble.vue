<script setup lang="ts">
/**
 * UserBubble — User message bubble following DeerFlow pattern
 *
 * DeerFlow reference: frontend/src/components/workspace/messages/message-list-item.tsx
 *
 * Key patterns:
 * - w-fit (narrow bubble that fits content)
 * - max-width 70% (prevents overly wide bubbles)
 * - Right-aligned within message-row
 * - Rounded corners, proper padding
 * - Copy, edit, retry actions
 */
import { useI18n } from 'vue-i18n'

interface Props {
  content: string
  displayTime: string
  sendStatus?: 'sending' | 'sent' | 'failed'
  isEditing?: boolean
  editInput?: string
}

const props = defineProps<Props>()

const emit = defineEmits<{
  copy: []
  edit: []
  retry: []
  sendEdit: []
  cancelEdit: []
  'update:editInput': [value: string]
}>()

const { t } = useI18n()

function onCopy() {
  navigator.clipboard.writeText(props.content)
  emit('copy')
}
</script>

<template>
  <div class="user-bubble">
    <!-- Normal display mode -->
    <div v-if="!isEditing" class="bubble-content">
      <p class="bubble-text">{{ content }}</p>

      <!-- Send status indicator -->
      <div v-if="sendStatus === 'sending'" class="send-status sending" aria-live="polite">
        <span class="status-dot" aria-hidden="true" />
        <span>{{ t('aiChat.sendingMessage') }}</span>
      </div>
      <div v-if="sendStatus === 'failed'" class="send-status failed" aria-live="polite">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true">
          <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
        </svg>
        <span>{{ t('aiChat.sendFailed') }}</span>
        <button class="retry-btn" @click="emit('retry')">{{ t('aiChat.resend') }}</button>
      </div>

      <!-- Footer: actions left, time right -->
      <div class="bubble-footer">
        <div class="bubble-actions">
          <button class="action-btn" :aria-label="t('aiChat.copyAria')" @click="onCopy">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
              <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
              <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
            </svg>
          </button>
          <button class="action-btn" :aria-label="t('aiChat.editAria')" @click="emit('edit')">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
              <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
              <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
            </svg>
          </button>
        </div>
        <span class="bubble-time">{{ displayTime }}</span>
      </div>
    </div>

    <!-- Edit mode: replace bubble with input -->
    <div v-if="isEditing" class="edit-mode">
      <van-field
        :model-value="editInput"
        type="textarea"
        :rows="2"
        autosize
        :placeholder="t('aiChat.editPlaceholder')"
        class="edit-input"
        @update:model-value="$emit('update:editInput', $event)"
      />
      <div class="edit-actions">
        <button class="cancel-btn" @click="emit('cancelEdit')">{{ t('common.cancel') }}</button>
        <button class="send-btn" :disabled="!editInput?.trim()" @click="emit('sendEdit')">{{ t('aiChat.sendEdit') }}</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* DeerFlow pattern: w-fit + max-width constraint */
.user-bubble {
  width: fit-content;
  max-width: 70%;
  min-width: 60px;
}

.bubble-content {
  background: var(--bubble-user-bg, rgba(99, 102, 241, 0.22));
  color: var(--bubble-user-color, #ffffff);
  border-radius: 16px 16px 4px 16px;
  padding: 10px 14px;
  word-break: break-word;
}

.bubble-text {
  margin: 0;
  font-size: 15px;
  line-height: 1.5;
}

/* Light theme adjustments */
@media (prefers-color-scheme: light) {
  :global(.theme-light) .bubble-content {
    background: var(--bubble-user-bg-light, #e8e8f4);
    color: var(--bubble-user-color-light, #1a1a2e);
  }
}

/* Send status */
.send-status {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 6px;
  font-size: 12px;
  opacity: 0.8;
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
  padding: 2px 6px;
  font-size: 12px;
  background: rgba(248, 113, 113, 0.2);
  border-radius: 4px;
  border: none;
  color: inherit;
  cursor: pointer;
}

/* Footer */
.bubble-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 6px;
  gap: 8px;
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