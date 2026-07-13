<script setup lang="ts">
/**
 * SelectionToolbar - Floating toolbar that appears when user selects text in AI messages.
 * Shows a "Quote to conversation" button near the selection.
 * Auto-hides after 500ms or on click outside.
 */
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const visible = ref(false)
const selectedText = ref('')
const posX = ref(0)
const posY = ref(0)

let hideTimer: ReturnType<typeof setTimeout> | null = null

const positionStyle = computed(() => ({
  position: 'fixed' as const,
  left: `${posX.value}px`,
  top: `${posY.value}px`,
  zIndex: 1000,
}))

function show(text: string, rect: DOMRect) {
  selectedText.value = text
  // Position toolbar above the selection, centered
  const toolbarWidth = 140
  let left = rect.left + rect.width / 2 - toolbarWidth / 2
  // Clamp to viewport
  left = Math.max(8, Math.min(left, window.innerWidth - toolbarWidth - 8))
  const top = rect.top - 40
  posX.value = left
  posY.value = Math.max(8, top)
  visible.value = true

  // Auto-hide after 3 seconds (generous timeout for mobile)
  clearHideTimer()
  hideTimer = setTimeout(() => {
    visible.value = false
  }, 3000)
}

function hide() {
  visible.value = false
  clearHideTimer()
}

function clearHideTimer() {
  if (hideTimer !== null) {
    clearTimeout(hideTimer)
    hideTimer = null
  }
}

function handleQuote() {
  if (!selectedText.value) return
  // Dispatch custom event that InputBox listens for
  window.dispatchEvent(new CustomEvent('ai-chat:quote', {
    detail: { text: selectedText.value },
  }))
  hide()
}

function onDocMouseDown(e: MouseEvent) {
  if (!visible.value) return
  const target = e.target as HTMLElement
  // Don't hide if clicking inside the toolbar
  if (target.closest('.selection-toolbar')) return
  hide()
}

onMounted(() => {
  document.addEventListener('mousedown', onDocMouseDown, true)
})

onUnmounted(() => {
  document.removeEventListener('mousedown', onDocMouseDown, true)
  clearHideTimer()
})

defineExpose({ show, hide })
</script>

<template>
  <Teleport to="body">
    <Transition name="selection-toolbar">
      <div v-if="visible" class="selection-toolbar" :style="positionStyle">
        <button class="quote-btn" @click="handleQuote">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M3 21c3 0 7-1 7-8V5c0-1.25-.756-2.017-2-2H4c-1.25 0-2 .75-2 1.972V11c0 1.25.75 2 2 2 1 0 1 0 1 1v1c0 1-1 2-2 2s-1 .008-1 1.031V21z"/>
            <path d="M15 21c3 0 7-1 7-8V5c0-1.25-.757-2.017-2-2h-4c-1.25 0-2 .75-2 1.972V11c0 1.25.75 2 2 2h.75c0 2.25.25 4-2.75 4v3z"/>
          </svg>
          <span>{{ t('aiChat.quoteButton') }}</span>
        </button>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.selection-toolbar {
  display: flex;
  align-items: center;
  padding: 4px;
  background: var(--card-bg, #ffffff);
  border: 1px solid var(--border-color, rgba(0, 0, 0, 0.08));
  border-radius: 8px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
  pointer-events: auto;
}

:global([data-theme='dark']) .selection-toolbar {
  background: var(--card-bg, #12122a);
  border-color: var(--border-color, rgba(255, 255, 255, 0.1));
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
}

.quote-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--text-primary, #0a0a0a);
  font-size: 13px;
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.15s ease;
}

.quote-btn:hover {
  background: rgba(99, 102, 241, 0.1);
  color: var(--van-primary-color, #6366f1);
}

.quote-btn:active {
  transform: scale(0.95);
}

:global([data-theme='dark']) .quote-btn {
  color: var(--text-primary, #f5f5f5);
}

:global([data-theme='dark']) .quote-btn:hover {
  background: rgba(99, 102, 241, 0.15);
  color: #bdbbff;
}

/* Transition */
.selection-toolbar-enter-active,
.selection-toolbar-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}

.selection-toolbar-enter-from,
.selection-toolbar-leave-to {
  opacity: 0;
  transform: translateY(4px);
}
</style>
