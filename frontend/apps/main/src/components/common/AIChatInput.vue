<template>
  <div class="input-shell" @click.self="closePanel">
    <!-- Slash command palette -->
    <transition name="panel">
      <div
        v-if="slashPaletteOpen"
        id="slash-palette-list"
        class="plus-panel slash-palette"
        role="menu"
        :aria-label="t('aiChat.slashPaletteHint')"
      >
        <div v-if="capabilityStore.capabilities.length === 0" class="panel-item slash-palette__empty" role="menuitem" aria-disabled="true">
          {{ t('aiChat.slashPaletteEmpty') }}
        </div>
        <button
          v-for="(cap, idx) in capabilityStore.capabilities"
          :id="`slash-cap-${cap.id}`"
          :key="cap.id"
          class="panel-item slash-palette__item"
          :class="{ 'slash-palette__item--selected': idx === selectedIndex }"
          role="menuitem"
          :aria-current="idx === selectedIndex ? true : undefined"
          @mousedown.prevent="selectCapability(cap)"
        >
          <span class="slash-palette__name">{{ cap.name }}</span>
          <span class="slash-palette__desc">{{ cap.description }}</span>
        </button>
      </div>
    </transition>

    <!-- Text input row with bottom-left controls -->
    <div class="input-row" :class="{ 'is-focused': focused, 'is-expanded': expanded }">
      <!-- Attachments preview area (above textarea) -->
      <div v-if="attachments && attachments.length > 0" class="attachments-row">
        <div
          v-for="(att, idx) in attachments"
          :key="idx"
          class="attachment-item"
          :class="`attachment-item--${att.type}`"
        >
          <span class="attachment-icon" aria-hidden="true">
            <svg v-if="att.type === 'image'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
              <circle cx="8.5" cy="8.5" r="1.5"/>
              <polyline points="21 15 16 10 5 21"/>
            </svg>
            <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
            </svg>
          </span>
          <span class="attachment-name">{{ att.name }}</span>
          <button
            class="attachment-remove"
            :aria-label="t('common.remove')"
            @click="removeAttachment(idx)"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"/>
              <line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
      </div>
      <textarea
        ref="inputRef"
        v-model="internalValue"
        class="chat-textarea"
        :placeholder="placeholder || t('aiChat.inputPlaceholder')"
        :aria-label="t('aiChat.inputAriaLabel')"
        aria-haspopup="menu"
        :aria-expanded="slashPaletteOpen"
        aria-controls="slash-palette-list"
        rows="3"
        :disabled="disabled || loading"
        @input="onInput"
        @focus="focused = true"
        @blur="focused = false"
        @keydown="onKeydown"
      />
      <!-- Expand button (top-right) -->
      <button
        class="expand-btn"
        :aria-label="expanded ? t('aiChat.collapse') : t('aiChat.expand')"
        :title="expanded ? t('aiChat.collapse') : t('aiChat.expand')"
        @click="toggleExpand"
      >
        <svg v-if="!expanded" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <polyline points="15 3 21 3 21 9"/><polyline points="9 21 3 21 3 15"/>
          <line x1="21" y1="3" x2="14" y2="10"/><line x1="3" y1="21" x2="10" y2="14"/>
        </svg>
        <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <polyline points="4 14 10 14 10 20"/><polyline points="20 10 14 10 14 4"/>
          <line x1="10" y1="14" x2="3" y2="21"/><line x1="21" y1="3" x2="14" y2="10"/>
        </svg>
      </button>
      <!-- Bottom-left controls row -->
      <div class="input-controls">
        <!-- Plus panel (positioned relative to controls) -->
        <transition name="panel">
          <div v-if="panelOpen" class="plus-panel plus-panel--up" role="menu" :aria-label="t('aiChat.moreFeatures')">
            <button
              v-for="item in panelItems"
              :key="item.action"
              class="panel-item"
              role="menuitem"
              @click="onPanelItem(item.action)"
            >
              <span class="panel-item-icon" aria-hidden="true">
                <svg :viewBox="item.icon.viewBox" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                  <path v-for="(d, i) in item.icon.paths" :key="i" :d="d" />
                </svg>
              </span>
              <span class="panel-item-label">{{ item.label }}</span>
            </button>
          </div>
        </transition>
        <!-- Optional agent selector (when agents list provided) -->
        <button
          v-if="agents && agents.length > 0"
          class="control-btn control-btn--agent"
          :aria-label="t('aiHub.selectAgent')"
          :title="t('aiHub.selectAgent')"
          @click="emit('selectAgent')"
        >
          <span v-if="agentIcon" class="agent-emoji" aria-hidden="true">{{ agentIcon }}</span>
          <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <rect x="3" y="3" width="18" height="18" rx="4"/>
            <circle cx="8.5" cy="10" r="1.5" fill="currentColor"/>
            <circle cx="15.5" cy="10" r="1.5" fill="currentColor"/>
            <path d="M8 15c1 1.2 2.4 1.8 4 1.8s3-.6 4-1.8"/>
          </svg>
        </button>
        <!-- Two-state deep-think toggle -->
        <button
          class="control-btn control-btn--think"
          :class="{ 'control-btn--active': mode === 'smart' }"
          :aria-pressed="mode === 'smart'"
          :aria-label="t('aiChat.modeSmart')"
          :title="t('aiChat.modeSmart')"
          @click="toggleMode"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M9.663 17h4.673M12 3a6 6 0 0 1 6 6c0 2.22-1.2 4.16-3 5.2V16a1 1 0 0 1-1 1H10a1 1 0 0 1-1-1v-1.8A6 6 0 0 1 12 3z"/>
            <path d="M9 21h6"/>
          </svg>
          <span class="control-indicator" v-if="mode === 'smart'" aria-hidden="true"></span>
        </button>
        <!-- Independent web-search toggle -->
        <button
          class="control-btn control-btn--search"
          :class="{ 'control-btn--active': webSearch }"
          :aria-pressed="webSearch"
          :aria-label="t('aiChat.webSearch')"
          :title="t('aiChat.webSearch')"
          @click="toggleWebSearch"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <circle cx="12" cy="12" r="10"/>
            <path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
          </svg>
          <span class="control-indicator" v-if="webSearch" aria-hidden="true"></span>
        </button>
        <!-- Plus button -->
        <button
          class="control-btn control-btn--plus"
          :class="{ 'control-btn--open': panelOpen }"
          :aria-label="t('aiChat.moreFeatures')"
          :aria-expanded="panelOpen"
          @click.stop="panelOpen = !panelOpen"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <line x1="12" y1="5" x2="12" y2="19"/>
            <line x1="5" y1="12" x2="19" y2="12"/>
          </svg>
        </button>
      </div>
      <!-- Abort button (bottom-right) -->
      <button
        v-if="loading"
        class="send-btn send-btn--abort"
        :aria-label="t('aiChat.stopGeneration')"
        @click="emit('abort')"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
          <rect x="4" y="4" width="16" height="16" rx="2"/>
        </svg>
      </button>
      <!-- Send button (bottom-right) -->
      <button
        v-else
        class="send-btn"
        :class="{ 'send-btn--active': internalValue.trim() }"
        :disabled="disabled || !internalValue.trim()"
        :aria-label="t('common.send')"
        @click="onSubmit"
      >
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <line x1="22" y1="2" x2="11" y2="13"/>
          <polygon points="22 2 15 22 11 13 2 9 22 2"/>
        </svg>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { showToast } from 'vant'
import { useCapabilityStore } from '@/stores/capability'
import { getWebSearchStatus } from '@/api/webSearch'
import type { AICapability } from '@/api/ai'

interface AgentOption {
  id: string
  display_name: string
  agent_name?: string
  icon?: string
}

interface Attachment {
  type: 'file' | 'image'
  name: string
  path?: string
}

const props = defineProps<{
  modelValue: string
  placeholder?: string
  disabled?: boolean
  loading?: boolean
  showClear?: boolean
  mode?: 'normal' | 'smart'
  webSearch?: boolean
  agents?: AgentOption[]
  selectedAgentId?: string
  attachments?: Attachment[]
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
  (e: 'submit', value: string): void
  (e: 'abort'): void
  (e: 'action', type: 'file' | 'image' | 'link' | 'clear' | 'camera' | 'ocr' | 'webpage' | 'history'): void
  (e: 'update:mode', value: 'normal' | 'smart'): void
  (e: 'update:webSearch', value: boolean): void
  (e: 'selectAgent'): void
  (e: 'removeAttachment', index: number): void
}>()

const internalValue = ref(props.modelValue)
const expanded = ref(false)
const focused = ref(false)
const panelOpen = ref(false)
const mode = ref<'normal' | 'smart'>(props.mode ?? 'normal')
const webSearch = ref<boolean>(props.webSearch ?? false)
const inputRef = ref<HTMLTextAreaElement | null>(null)

const router = useRouter()
const { t } = useI18n()
const capabilityStore = useCapabilityStore()
const slashPaletteOpen = ref(false)
const selectedIndex = ref(0)

const selectedAgent = computed(() =>
  props.agents?.find((a) => a.id === props.selectedAgentId) ?? props.agents?.[0] ?? null,
)
const agentIcon = computed(() => selectedAgent.value?.icon || null)
const agentLabel = computed(() => selectedAgent.value?.display_name ?? t('aiHub.selectAgent'))

function toggleMode() {
  mode.value = mode.value === 'normal' ? 'smart' : 'normal'
}

async function toggleWebSearch() {
  if (!webSearch.value) {
    // Pre-check: verify at least one provider is enabled before turning on
    try {
      const status = await getWebSearchStatus()
      if (!status.has_web_search) {
        showToast(t('webSearch.noProviderToast'))
        return
      }
    } catch {
      showToast(t('webSearch.noProviderToast'))
      return
    }
  }
  webSearch.value = !webSearch.value
}

const panelItems = computed(() => [
  {
    action: 'camera' as const,
    label: t('aiChat.panelCamera'),
    icon: { viewBox: '0 0 24 24', paths: ['M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z', 'M12 17a4 4 0 1 0 0-8 4 4 0 0 0 0 8z'] },
  },
  {
    action: 'file' as const,
    label: t('aiChat.panelFile'),
    icon: { viewBox: '0 0 24 24', paths: ['M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z', 'M14 2v6h6', 'M12 18v-6', 'M9 15h6'] },
  },
  {
    action: 'image' as const,
    label: t('aiChat.panelImage'),
    icon: { viewBox: '0 0 24 24', paths: ['M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4', 'M17 8l-5-5-5 5', 'M12 3v12'] },
  },
])

watch(
  () => props.modelValue,
  (val) => {
    if (val !== internalValue.value) {
      internalValue.value = val
      nextTick(adjustHeight)
    }
  },
)

watch(internalValue, (val) => emit('update:modelValue', val))
watch(mode, (val) => emit('update:mode', val))
watch(() => props.mode, (val) => { if (val !== undefined && val !== mode.value) mode.value = val })
watch(webSearch, (val) => emit('update:webSearch', val))
watch(() => props.webSearch, (val) => { if (val !== undefined && val !== webSearch.value) webSearch.value = val })

function onInput() {
  adjustHeight()
  const val = internalValue.value
  const shouldOpen = val.startsWith('/')
  if (shouldOpen && !slashPaletteOpen.value) {
    if (capabilityStore.capabilities.length === 0) {
      capabilityStore.loadCapabilities().catch(() => {
        // silently ignore — palette shows empty state
      })
    }
    selectedIndex.value = 0
    panelOpen.value = false
  }
  slashPaletteOpen.value = shouldOpen
}

function onKeydown(e: KeyboardEvent) {
  // Handle Enter for normal submit (replaces @keydown.enter.exact.prevent)
  if (e.key === 'Enter' && !e.shiftKey && !e.ctrlKey && !e.altKey && !e.metaKey) {
    if (slashPaletteOpen.value) {
      e.preventDefault()
      const caps = capabilityStore.capabilities
      if (caps.length > 0 && caps[selectedIndex.value]) selectCapability(caps[selectedIndex.value])
      return
    }
    e.preventDefault()
    onSubmit()
    return
  }

  if (!slashPaletteOpen.value) return
  const caps = capabilityStore.capabilities
  if (caps.length === 0) return
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    selectedIndex.value = (selectedIndex.value + 1) % caps.length
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    selectedIndex.value = (selectedIndex.value - 1 + caps.length) % caps.length
  } else if (e.key === 'Escape') {
    e.preventDefault()
    slashPaletteOpen.value = false
  } else if (e.key === 'Tab') {
    if (caps[selectedIndex.value]) {
      e.preventDefault()
      selectCapability(caps[selectedIndex.value])
    }
  }
}

function selectCapability(cap: AICapability) {
  slashPaletteOpen.value = false
  if (cap.ui.input_mode === 'free_text') {
    internalValue.value = cap.ui.example_questions[0] ?? cap.ui.placeholder ?? cap.name
    emit('update:modelValue', internalValue.value)
    nextTick(() => inputRef.value?.focus())
  } else {
    if (cap.ui.route) router.push(cap.ui.route)
  }
}

function onSubmit() {
  if (slashPaletteOpen.value) return
  if (props.disabled || props.loading || !internalValue.value.trim()) return
  emit('submit', internalValue.value.trim())
}

function toggleExpand() {
  expanded.value = !expanded.value
  nextTick(adjustHeight)
}

function adjustHeight() {
  const el = inputRef.value
  if (!el) return
  if (expanded.value) {
    el.style.height = '75vh'
    return
  }
  // Default 3-row height (~60px), auto-grow up to 120px
  el.style.height = '60px'
  el.style.height = `${Math.max(60, Math.min(el.scrollHeight, 120))}px`
}

function closePanel() {
  panelOpen.value = false
}

function removeAttachment(index: number) {
  emit('removeAttachment', index)
}

function onPanelItem(action: 'file' | 'image' | 'link' | 'clear' | 'camera' | 'ocr' | 'webpage' | 'history') {
  panelOpen.value = false
  emit('action', action)
}

function onDocClick(e: MouseEvent) {
  const el = e.target as HTMLElement
  if (!el.closest('.input-shell')) {
    panelOpen.value = false
    slashPaletteOpen.value = false
  }
}

onMounted(() => {
  nextTick(adjustHeight)
  document.addEventListener('click', onDocClick)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', onDocClick)
})
</script>

<style scoped>
.input-shell {
  display: flex;
  flex-direction: column;
  gap: 6px;
  position: relative;
  /* Dark mode defaults */
  --ai-btn-border: rgba(255, 255, 255, 0.1);
  --ai-btn-color: var(--text-tertiary);
  --ai-btn-hover-bg: rgba(255, 255, 255, 0.06);
  --ai-btn-hover-color: rgba(255, 255, 255, 0.7);
  --ai-panel-bg: #1e1e2e;
  --ai-panel-border: rgba(255, 255, 255, 0.1);
  --ai-panel-item-color: rgba(255, 255, 255, 0.6);
  --ai-panel-item-hover-bg: rgba(255, 255, 255, 0.08);
  --ai-panel-item-hover-color: rgba(255, 255, 255, 0.9);
  --ai-input-bg: rgba(255, 255, 255, 0.07);
  --ai-input-border: rgba(255, 255, 255, 0.1);
  --ai-text-color: rgba(255, 255, 255, 0.9);
  --ai-placeholder-color: rgba(255, 255, 255, 0.3);
  --ai-scrollbar-thumb: rgba(255, 255, 255, 0.15);
  --ai-expand-color: rgba(255, 255, 255, 0.3);
  --ai-expand-hover-bg: rgba(255, 255, 255, 0.08);
  --ai-expand-hover-color: rgba(255, 255, 255, 0.6);
}

/* Light mode overrides.
 * Must use :global() for the entire selector — Vue scoped CSS only adds the
 * scoped attribute to the last simple selector outside :global(), so
 * `:global(.theme-light) .input-shell` compiles to `.theme-light .input-shell`
 * (no scoped attr) and never matches `.input-shell[data-v-xxx]`.
 * Wrapping the full selector in :global() bypasses scoping entirely. */
:global(.theme-light .input-shell),
:global([data-theme='light'] .input-shell) {
  --ai-btn-border: rgba(0, 0, 0, 0.4);
  --ai-btn-color: rgba(0, 0, 0, 0.75);
  --ai-btn-hover-bg: rgba(0, 0, 0, 0.1);
  --ai-btn-hover-color: rgba(0, 0, 0, 0.9);
  --ai-panel-bg: #ffffff;
  --ai-panel-border: rgba(0, 0, 0, 0.25);
  --ai-panel-item-color: rgba(0, 0, 0, 0.75);
  --ai-panel-item-hover-bg: rgba(0, 0, 0, 0.08);
  --ai-panel-item-hover-color: rgba(0, 0, 0, 0.9);
  --ai-input-bg: #ffffff;
  --ai-input-border: rgba(0, 0, 0, 0.35);
  --ai-text-color: rgba(0, 0, 0, 0.9);
  --ai-placeholder-color: rgba(0, 0, 0, 0.6);
  --ai-scrollbar-thumb: rgba(0, 0, 0, 0.25);
  --ai-expand-color: rgba(0, 0, 0, 0.55);
  --ai-expand-hover-bg: rgba(0, 0, 0, 0.1);
  --ai-expand-hover-color: rgba(0, 0, 0, 0.8);
}

/* ── Input controls (bottom-left inside input-row) ── */
.input-controls {
  position: absolute;
  bottom: 8px;
  left: 10px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.control-btn {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: none;
  background: rgba(99, 102, 241, 0.08);
  color: var(--ai-btn-color);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background 0.2s, color 0.2s, transform 0.15s, box-shadow 0.2s;
  position: relative;
}

.control-btn:hover {
  background: rgba(99, 102, 241, 0.15);
  color: var(--ai-btn-hover-color);
}

.control-btn:active {
  transform: scale(0.92);
}

/* Active state: solid colored background + bright icon + ring indicator */
.control-btn--active {
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  color: #ffffff;
  box-shadow: 0 2px 8px rgba(99, 102, 241, 0.4), 0 0 0 2px rgba(99, 102, 241, 0.2);
}

.control-btn--active:hover {
  background: linear-gradient(135deg, #7c3aed 0%, #a78bfa 100%);
  box-shadow: 0 3px 12px rgba(99, 102, 241, 0.5), 0 0 0 2px rgba(99, 102, 241, 0.3);
}

/* Small indicator dot on active buttons (alternative visual cue) */
.control-indicator {
  position: absolute;
  top: 2px;
  right: 2px;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #10b981;
  box-shadow: 0 0 4px rgba(16, 185, 129, 0.6);
}

.control-btn--agent {
  background: rgba(99, 102, 241, 0.12);
}

.control-btn--plus {
  transition: background 0.2s, color 0.2s, transform 0.2s;
  position: relative;
}

.control-btn--open {
  transform: rotate(45deg);
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  color: #ffffff;
  box-shadow: 0 2px 8px rgba(99, 102, 241, 0.4);
}

.agent-emoji {
  font-size: 14px;
  line-height: 1;
}

/* ── Attachments row (above textarea) ── */
.attachments-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 6px 0 4px;
  margin-bottom: 4px;
  border-bottom: 1px dashed rgba(99, 102, 241, 0.2);
}

.attachment-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  border-radius: 6px;
  background: rgba(99, 102, 241, 0.12);
  border: 1px solid rgba(99, 102, 241, 0.25);
  font-size: 12px;
  color: var(--ai-text-color);
  max-width: 180px;
}

.attachment-icon {
  color: #818cf8;
  flex-shrink: 0;
}

.attachment-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.attachment-remove {
  width: 16px;
  height: 16px;
  border: none;
  border-radius: 4px;
  background: transparent;
  color: rgba(255, 255, 255, 0.5);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: color 0.15s, background 0.15s;
}

.attachment-remove:hover {
  background: rgba(248, 113, 113, 0.2);
  color: #f87171;
}

.attachment-item--image {
  background: rgba(16, 185, 129, 0.12);
  border-color: rgba(16, 185, 129, 0.25);
}

.attachment-item--image .attachment-icon {
  color: #10b981;
}

/* ── Plus panel (positioned relative to + button in input-controls) ── */
.plus-panel {
  position: absolute;
  background: var(--ai-panel-bg);
  border: 1px solid var(--ai-panel-border);
  border-radius: 14px;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
  z-index: 100;
  min-width: 160px;
}

/* Plus panel positioned above the + button (last item in input-controls) */
.plus-panel--up {
  bottom: calc(100% + 8px);
  right: 0;
}

.panel-item {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border: none;
  border-radius: 10px;
  background: transparent;
  color: var(--ai-panel-item-color);
  font-size: 13px;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
  white-space: nowrap;
}

.panel-item:hover {
  background: var(--ai-panel-item-hover-bg);
  color: var(--ai-panel-item-hover-color);
}

.panel-item:active {
  transform: scale(0.95);
}

.panel-item-icon {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  background: rgba(99, 102, 241, 0.12);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #818cf8;
  flex-shrink: 0;
}

.panel-item-label {
  line-height: 1.2;
}

/* ── Slash command palette ── */
.slash-palette {
  right: 0;
  left: 0;
  bottom: calc(100% + 8px);
  min-width: unset;
  padding: 6px;
  max-height: 60vh;
  overflow-y: auto;
}

.slash-palette__empty {
  flex-direction: row;
  font-size: 13px;
  padding: 10px 12px;
  color: var(--ai-panel-item-color);
  cursor: default;
}

.slash-palette__item {
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  padding: 8px 12px;
  border-radius: 8px;
  font-size: 13px;
  text-align: left;
}

.slash-palette__item--selected {
  background: var(--ai-panel-item-hover-bg);
  color: var(--ai-panel-item-hover-color);
}

.slash-palette__name {
  font-weight: 500;
  color: var(--ai-text-color);
}

.slash-palette__desc {
  font-size: 11px;
  color: var(--ai-panel-item-color);
  line-height: 1.3;
}

/* ── Panel transition ── */
.panel-enter-active,
.panel-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}

.panel-enter-from,
.panel-leave-to {
  opacity: 0;
  transform: scale(0.92) translateY(4px);
}

/* ── Input row ── */
.input-row {
  position: relative;
  display: flex;
  align-items: flex-end;
  background: var(--ai-input-bg);
  border: 1px solid var(--ai-input-border);
  border-radius: 18px;
  padding: 10px 48px 44px 14px;
  min-height: 100px;
  transition: border-color 0.2s, box-shadow 0.2s, border-radius 0.2s, min-height 0.2s;
}

.input-row.is-focused {
  border-color: rgba(99, 102, 241, 0.6);
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.15);
}

.input-row.is-expanded {
  border-radius: 14px;
  min-height: 75vh;
}

.chat-textarea {
  flex: 1;
  border: none;
  background: transparent;
  font-size: 14px;
  color: var(--ai-text-color);
  outline: none;
  resize: none;
  overflow-y: auto;
  line-height: 20px;
  height: 60px;
  padding: 0;
  margin: 0;
  transition: height 0.12s ease;
  caret-color: #6366f1;
}

.chat-textarea::placeholder {
  color: var(--ai-placeholder-color);
}

.chat-textarea:disabled {
  opacity: 0.5;
}

.chat-textarea::-webkit-scrollbar {
  width: 3px;
}

.chat-textarea::-webkit-scrollbar-thumb {
  background: var(--ai-scrollbar-thumb);
  border-radius: 2px;
}

/* ── Expand button ── */
.expand-btn {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 30px;
  height: 30px;
  background: transparent;
  border: none;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: var(--ai-expand-color);
  transition: background 0.15s, color 0.15s;
}

.expand-btn:hover {
  background: var(--ai-expand-hover-bg);
  color: var(--ai-expand-hover-color);
}

/* ── Send / Abort button ── */
.send-btn {
  position: absolute;
  bottom: 8px;
  right: 8px;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: none;
  background: rgba(99, 102, 241, 0.2);
  color: rgba(99, 102, 241, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background 0.2s, color 0.2s, transform 0.15s;
}

.send-btn--active {
  background: linear-gradient(135deg, #6366f1, #7c3aed);
  color: #fff;
  box-shadow: 0 2px 12px rgba(99, 102, 241, 0.4);
}

.send-btn--active:hover {
  transform: scale(1.05);
}

.send-btn--active:active {
  transform: scale(0.95);
}

.send-btn:disabled {
  cursor: default;
}

.send-btn--abort {
  background: #ff3b30;
  color: #fff;
  box-shadow: 0 2px 12px rgba(255, 59, 48, 0.4);
  cursor: pointer;
}

.send-btn--abort:hover {
  transform: scale(1.05);
  background: #ff2d20;
}

.send-btn--abort:active {
  transform: scale(0.95);
}

@media (prefers-reduced-motion: reduce) {
  .send-btn,
  .control-btn,
  .input-row,
  .panel-enter-active,
  .panel-leave-active {
    transition: none;
  }
}
</style>
