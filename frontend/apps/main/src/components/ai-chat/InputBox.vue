<script setup lang="ts">
/**
 * Unified AI Chat InputBox — merged from AIChatInput.vue (hub) + InputBox.vue (chat)
 *
 * Features:
 * - AIChatInput custom CSS variable styling (dark/light)
 * - DeerFlow 4-mode selector (Flash/Thinking/Pro/Ultra)
 * - Web search toggle with provider pre-check
 * - Plus panel (camera/file/image)
 * - Attachment preview row
 * - Expand button for full-screen textarea
 * - Welcome mode (hero + examples)
 * - Chat mode (bottom-sticky)
 * - Agent picker in welcome mode, static icon in chat mode
 * - Model selector popup
 * - Tenant resource isolation (useTenantAiResources)
 */
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { showToast, showSuccessToast, showFailToast } from 'vant'
import { useI18n } from 'vue-i18n'
import ModeSelector from './ModeSelector.vue'
import VoiceInputButton from './VoiceInputButton.vue'
import SlashPalette from './SlashPalette.vue'
import IIcon from '@/components/IIcon.vue'
import AIBrainIcon from '@/components/common/AIBrainIcon.vue'
import { getAgentIcon, isEmoji } from '@/utils/agent'
import { useTenantAiResources, INPUT_MODE_CONFIGS, getResolvedMode } from '@/composables/ai-chat/useTenantAiResources'
import { useSlashCommands } from '@/composables/ai-chat/useSlashCommands'
import type { SlashCommand } from '@/composables/ai-chat/useSlashCommands'
import { useSlashSkills } from '@/composables/ai-chat/useSlashSkills'
import { getWebSearchStatus } from '@/api/webSearch'
import { polishInputDraft } from '@/api/ai-chat'
import { uploadChatAttachment } from '@/api/ai'
import type { InputMode, SubmitPayload, InputContext } from '@/types/ai-chat/input-mode'

const NUMINA_AGENT_NAME = 'numina'

interface AgentOption {
  id: string
  display_name: string
  agent_name?: string
  icon?: string
  color?: string | null
  description?: string | null
}

interface Attachment {
  type: 'file' | 'image'
  name: string
  path?: string
}

const { t } = useI18n()

// ── Props ──
const props = defineProps<{
  status: 'ready' | 'streaming' | 'submitted' | 'error' | 'reconnecting'
  isWelcomeMode?: boolean
  threadId?: string
  initialMode?: InputMode
  initialModelName?: string
  agentId?: string
  agents?: AgentOption[]
  agentIcon?: string
  agentLabel?: string
  /** When true, agent icon shows info popup instead of triggering selection */
  readonly?: boolean
  disabled?: boolean
  modelValue?: string
  webSearch?: boolean
  attachments?: Attachment[]
}>()

// ── Emits ──
const emit = defineEmits<{
  submit: [payload: SubmitPayload]
  stop: []
  'update:modelValue': [value: string]
  'update:webSearch': [value: boolean]
  selectAgent: []
  addAttachment: [attachment: Attachment]
  removeAttachment: [index: number]
  contextChange: [context: InputContext]
}>()

// ── Tenant resources ──
const {
  models,
  tenantConfig: _tenantConfig,
  supportsThinking: _supportsThinking,
  supportsSubagent,
  loading: _resourcesLoading,
  webSearchAvailable,
} = useTenantAiResources()

// ── Input state ──
const internalValue = ref(props.modelValue ?? '')
const focused = ref(false)
const expanded = ref(false)
const panelOpen = ref(false)
const panelTriggerRef = ref<HTMLElement | null>(null)
const panelRef = ref<HTMLElement | null>(null)
const webSearchEnabled = ref(props.webSearch ?? false)
const inputRef = ref<HTMLTextAreaElement | null>(null)
const fileInputRef = ref<HTMLInputElement | null>(null)
const imageInputRef = ref<HTMLInputElement | null>(null)
const cameraInputRef = ref<HTMLInputElement | null>(null)
const uploading = ref(false)

// ── Vision model detection ──
// When the user uploads an image, we need a model that supports vision.
// If the currently selected model doesn't support vision, we'll auto-switch
// to the first vision-capable model for this session.
const visionModel = computed(() =>
  models.value.find(m => m.supports_vision) ?? null,
)
const hasVisionModel = computed(() => visionModel.value !== null)

// ── Input polish (D3 DeerFlow sync) ──
// Stateless single-LLM-call draft rewrite. Abortable + staleness-guarded so a
// thread switch or rapid re-click cannot land a stale rewrite. Undo restores
// the original draft while the textarea still shows the rewritten text.
const polishingInput = ref(false)
const inputPolishUndo = ref<{ originalText: string; rewrittenText: string } | null>(null)
let polishAbort: AbortController | null = null

const inputPolishUndoAvailable = computed(
  () => !polishingInput.value
    && inputPolishUndo.value !== null
    && internalValue.value === inputPolishUndo.value.rewrittenText,
)

const canPolishInput = computed(
  () => !polishingInput.value
    && props.status !== 'streaming'
    && props.status !== 'submitted'
    && internalValue.value.trim().length > 0
    && !internalValue.value.trim().startsWith('/'),
)

async function onPolishInput() {
  const originalText = internalValue.value
  if (!originalText.trim() || polishingInput.value) return
  if (polishAbort) polishAbort.abort()
  polishAbort = new AbortController()
  polishingInput.value = true
  try {
    const result = await polishInputDraft(originalText, polishAbort.signal)
    // Staleness guard: textarea changed mid-flight → discard.
    if (internalValue.value !== originalText) return
    if (!result.changed) {
      showToast(t('aiChat.inputPolishNoChanges'))
      return
    }
    internalValue.value = result.rewritten_text
    inputPolishUndo.value = { originalText, rewrittenText: result.rewritten_text }
    await nextTick()
    inputRef.value?.focus()
  } catch (err) {
    // AbortError is expected on cancel/thread-switch — not a user-facing failure.
    if (err instanceof DOMException && err.name === 'AbortError') return
    showToast(t('aiChat.inputPolishFailed'))
  } finally {
    polishingInput.value = false
    polishAbort = null
  }
}

function onUndoPolishInput() {
  if (!inputPolishUndoAvailable.value || !inputPolishUndo.value) return
  internalValue.value = inputPolishUndo.value.originalText
  inputPolishUndo.value = null
  nextTick(() => inputRef.value?.focus())
}

function abortInputPolish() {
  if (polishAbort) {
    polishAbort.abort()
    polishAbort = null
  }
  polishingInput.value = false
}

// Track whether web search state was explicitly set (by the user toggling it,
// or by the parent passing a definite webSearch prop e.g. inherited from the
// AI hub page). The auto-default logic below never overrides an explicit value.
let webSearchExplicitlySet = props.webSearch !== undefined

// Auto-enable web search by default when the family tenant has AI enabled
// (models loaded) AND has web search available (enabled provider or websearch
// MCP). Only fires once on first resource load; never overrides explicit user
// or parent-driven choices.
watch(webSearchAvailable, (available) => {
  if (webSearchExplicitlySet) return
  // AI enabled = at least one model is available to the tenant
  const aiEnabled = models.value.length > 0
  if (available && aiEnabled && !webSearchEnabled.value) {
    webSearchEnabled.value = true
  }
})

// ── Mode context (DeerFlow 4-mode) ──
const LAST_MODE_KEY = 'ai-chat:last-mode'

function getLastSelectedMode(): InputMode {
  try {
    const saved = localStorage.getItem(LAST_MODE_KEY)
    if (saved && ['flash', 'thinking', 'pro', 'ultra'].includes(saved)) {
      return saved as InputMode
    }
  } catch { /* ignore */ }
  return 'thinking'
}

const selectedModel = computed(() =>
  models.value.find(m => m.name === context.value.model_name) ?? models.value[0],
)

const context = ref<InputContext>({
  model_name: props.initialModelName ?? '',
  mode: props.initialMode ?? getLastSelectedMode(),
  reasoning_effort: 'medium',
})

const currentModelSupportsThinking = computed(() =>
  selectedModel.value?.supports_thinking ?? false,
)

const isUltraDisabled = computed(() => !supportsSubagent.value)

const finalPayload = computed(() => {
  const config = INPUT_MODE_CONFIGS[context.value.mode]
  return {
    thinking_enabled: config.thinking_enabled,
    is_plan_mode: config.is_plan_mode,
    subagent_enabled: config.subagent_enabled,
    reasoning_effort: config.reasoning_effort,
  }
})

// ── Agent display ──
const selectedAgent = computed(() =>
  props.agents?.find((a) => a.id === props.agentId) ?? props.agents?.[0] ?? null,
)
const displayAgentIcon = computed(() => props.agentIcon || selectedAgent.value?.icon || undefined)
const displayAgentLabel = computed(() => props.agentLabel || selectedAgent.value?.display_name || '')
const isNuminaAgent = computed(() => selectedAgent.value?.agent_name === NUMINA_AGENT_NAME)

// Agent info popup state (for chat mode)
const showAgentInfo = ref(false)

function onToggleAgentInfo() {
  showAgentInfo.value = !showAgentInfo.value
}

// ── Slash command palette (U1 — D1/D2 shared entry) ──
// Local static registry (/goal + /compact); NOT useCapabilityStore (those are
// routable features from /ai/capabilities, not chat commands — plan risk #4).
// Plumbed from the deprecated components/common/AIChatInput.vue
// onInput/onKeydown/selectCapability logic.
const { filteredCommands, query: slashQuery } = useSlashCommands()
const { skills, fetchSkills } = useSlashSkills()
const slashPaletteOpen = ref(false)
const slashSelectedIndex = ref(0)

// Merge static commands with custom skills for slash palette
const slashCommands = computed(() => {
  const staticCommands = filteredCommands.value
  const skillCommands: SlashCommand[] = skills.value.map(skill => ({
    name: `/${skill.id}`,
    description: skill.description || skill.name,
    insertText: `/${skill.id} `,
    apply: (ctx) => {
      // Insert skill command and leave for user to type arguments
      if (!ctx.value.startsWith(`/${skill.id}`)) {
        ctx.setValue(`/${skill.id} `)
      }
      return false
    },
  }))
  return [...staticCommands, ...skillCommands]
})

// Fetch skills on mount for slash autocomplete
onMounted(() => {
  fetchSkills()
})

// ── Watchers ──
watch(internalValue, (val) => {
  emit('update:modelValue', val)
  syncSlashState(val)
})
watch(() => props.modelValue, (val) => {
  if (val !== undefined && val !== internalValue.value) {
    internalValue.value = val
  }
})
watch(webSearchEnabled, (val) => emit('update:webSearch', val))
watch(() => props.webSearch, (val) => {
  if (val !== undefined && val !== webSearchEnabled.value) {
    webSearchEnabled.value = val
    // Parent-driven changes are treated as explicit intent
    webSearchExplicitlySet = true
  }
})

const showExpandIcon = computed(() => {
  if (expanded.value) return true
  const newlines = (internalValue.value.match(/\n/g) || []).length
  return newlines >= 2 || internalValue.value.length > 36
})

function emitContextChange() {
  emit('contextChange', {
    ...context.value,
    reasoning_effort: INPUT_MODE_CONFIGS[context.value.mode].reasoning_effort,
  })
}

// Auto-downgrade mode when model doesn't support thinking
watch(currentModelSupportsThinking, (supports) => {
  const resolved = getResolvedMode(context.value.mode, supports, supportsSubagent.value)
  if (resolved !== context.value.mode) {
    context.value.mode = resolved
    emitContextChange()
  }
})

// Initialize default model
watch(() => models.value, (newModels) => {
  if (newModels.length > 0 && !context.value.model_name) {
    const defaultModel = newModels.find(m => m.is_default) ?? newModels[0]
    context.value.model_name = defaultModel.name
    const resolved = getResolvedMode(context.value.mode, defaultModel.supports_thinking ?? false, supportsSubagent.value)
    if (resolved !== context.value.mode) {
      context.value.mode = resolved
    }
    emitContextChange()
  }
}, { immediate: true })

// ── Methods ──
// PC (fine-pointer / keyboard) devices: Enter submits, Shift+Enter inserts
// a newline. Mobile falls back to the Send button.
const isDesktop = ref(false)
function syncDesktop() {
  isDesktop.value = window.matchMedia?.('(pointer: fine)').matches ?? false
}

// Slash palette: open whenever the textarea starts with `/`; close otherwise.
function syncSlashState(val: string) {
  const shouldOpen = val.startsWith('/')
  slashQuery.value = val
  if (shouldOpen) {
    if (!slashPaletteOpen.value) {
      slashSelectedIndex.value = 0
      panelOpen.value = false
    }
  }
  slashPaletteOpen.value = shouldOpen
}

function closeSlashPalette() {
  slashPaletteOpen.value = false
  slashQuery.value = ''
}

function selectSlashCommand(command?: SlashCommand) {
  if (!command) return
  const currentValue = internalValue.value.trim()
  const handled = command.apply({
    value: currentValue,
    setValue: (next: string) => {
      internalValue.value = next
    },
  })
  closeSlashPalette()
  nextTick(() => inputRef.value?.focus())
  // When the apply callback reports "fully handled" (e.g. /compact triggers
  // its own flow), proceed to submit so U5/U6 can wire the real flows on top
  // of a normal submit. Otherwise (e.g. /goal fills the prefix) leave the
  // textarea focused for the user to finish typing.
  if (handled) {
    onSubmit()
  }
}

function onKeydownEnter(e: KeyboardEvent) {
  if (!isDesktop.value) return
  if (e.shiftKey) {
    // Let the textarea insert a newline (default behavior)
    return
  }
  // When the slash palette is open, Enter selects instead of submitting.
  if (slashPaletteOpen.value) {
    e.preventDefault()
    const cmds = slashCommands.value
    if (cmds.length > 0) {
      selectSlashCommand(cmds[slashSelectedIndex.value])
    }
    return
  }
  e.preventDefault()
  onSubmit()
}

function onSubmit() {
  if (props.status === 'streaming') {
    emit('stop')
    return
  }
  const text = internalValue.value.trim()
  if (!text) return

  // Models not loaded yet (e.g. /ai/models still in flight on first entry to
  // welcome mode). Previously this returned silently, making the send button
  // appear broken. Toast so the user knows to wait, and keep their text
  // intact so they can retry once models resolve.
  if (!context.value.model_name) {
    showToast(t('aiChat.modelsLoading'))
    return
  }

  const files = (props.attachments ?? [])
    .filter(a => a.path)
    .map(a => ({
      path: a.path!,
      filename: a.name,
      mime_type: _guessMime(a.name),
    }))

  emit('submit', {
    text,
    model_name: context.value.model_name,
    mode: context.value.mode,
    websearch_enabled: webSearchEnabled.value,
    ...(files.length > 0 ? { files } : {}),
    ...finalPayload.value,
    thread_id: props.threadId,
  })
  internalValue.value = ''
  expanded.value = false
  closeSlashPalette()
}

// Slash palette keyboard navigation (ArrowUp/Down/Tab/Esc). Enter is handled
// by onKeydownEnter above. Only active while the palette is open.
function onKeydownNav(e: KeyboardEvent) {
  if (!slashPaletteOpen.value) return
  const cmds = slashCommands.value
  if (e.key === 'ArrowDown') {
    if (cmds.length === 0) return
    e.preventDefault()
    slashSelectedIndex.value = (slashSelectedIndex.value + 1) % cmds.length
  } else if (e.key === 'ArrowUp') {
    if (cmds.length === 0) return
    e.preventDefault()
    slashSelectedIndex.value = (slashSelectedIndex.value - 1 + cmds.length) % cmds.length
  } else if (e.key === 'Escape') {
    e.preventDefault()
    closeSlashPalette()
  } else if (e.key === 'Tab') {
    if (cmds[slashSelectedIndex.value]) {
      e.preventDefault()
      selectSlashCommand(cmds[slashSelectedIndex.value])
    }
  }
}

function onModeSelect(mode: InputMode) {
  if (mode === 'ultra' && !supportsSubagent.value) {
    showToast(t('aiChat.tenantUltraDisabled'))
    return
  }
  context.value.mode = mode
  context.value.reasoning_effort = INPUT_MODE_CONFIGS[mode].reasoning_effort
  try {
    localStorage.setItem(LAST_MODE_KEY, mode)
  } catch { /* ignore */ }
  emitContextChange()
}

// Web search
async function toggleWebSearch() {
  if (!webSearchEnabled.value) {
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
  webSearchEnabled.value = !webSearchEnabled.value
  webSearchExplicitlySet = true
}

// Expand
function toggleExpand() {
  expanded.value = !expanded.value
}

// Panel
function closePanel() {
  panelOpen.value = false
}

function onPanelItem(action: 'file' | 'image' | 'camera') {
  panelOpen.value = false
  // Directly trigger the corresponding file input
  if (action === 'file') {
    fileInputRef.value?.click()
  } else if (action === 'image') {
    imageInputRef.value?.click()
  } else if (action === 'camera') {
    cameraInputRef.value?.click()
  }
}

// ── File / Image / Camera upload handlers ──
const _ALLOWED_IMAGE_EXTS = ['.jpg', '.jpeg', '.png', '.webp', '.gif']
const _ALLOWED_FILE_EXTS = [
  '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
  '.txt', '.csv', '.md', '.json', '.yaml', '.yml',
  ..._ALLOWED_IMAGE_EXTS,
]

function _guessMime(filename: string): string {
  const ext = filename.slice(filename.lastIndexOf('.')).toLowerCase()
  const map: Record<string, string> = {
    '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png',
    '.webp': 'image/webp', '.gif': 'image/gif',
    '.pdf': 'application/pdf', '.doc': 'application/msword',
    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    '.xls': 'application/vnd.ms-excel',
    '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    '.txt': 'text/plain', '.csv': 'text/csv', '.md': 'text/markdown',
    '.json': 'application/json', '.yaml': 'text/yaml', '.yml': 'text/yaml',
  }
  return map[ext] || 'application/octet-stream'
}

async function _handleUpload(file: File, isImage: boolean) {
  const ext = file.name.slice(file.name.lastIndexOf('.')).toLowerCase()

  if (isImage && !hasVisionModel.value) {
    showFailToast(t('toast.noVisionModel'))
    return
  }

  if (isImage && !_ALLOWED_IMAGE_EXTS.includes(ext)) {
    showFailToast(t('toast.invalidImageType'))
    return
  }
  if (!isImage && !_ALLOWED_FILE_EXTS.includes(ext)) {
    showFailToast(t('toast.invalidFileType'))
    return
  }

  uploading.value = true
  try {
    const result = await uploadChatAttachment(file)
    emit('addAttachment', {
      type: isImage ? 'image' : 'file',
      name: result.filename,
      path: result.url,
    })
    // Auto-switch to vision-capable model when an image is uploaded
    // and the current model doesn't support vision.
    if (isImage && visionModel.value && !selectedModel.value?.supports_vision) {
      context.value.model_name = visionModel.value.name
    }
    showSuccessToast(t('toast.uploadSuccess', { name: file.name }))
  } catch {
    showFailToast(t('toast.uploadFailed'))
  } finally {
    uploading.value = false
  }
}

function handleFileSelect(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (file) _handleUpload(file, false)
  ;(e.target as HTMLInputElement).value = ''
}

function handleImageSelect(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (file) _handleUpload(file, true)
  ;(e.target as HTMLInputElement).value = ''
}

function handleCameraSelect(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (file) _handleUpload(file, true)
  ;(e.target as HTMLInputElement).value = ''
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

function removeAttachment(index: number) {
  emit('removeAttachment', index)
}

// Voice input
function onVoiceResult(text: string) {
  internalValue.value = internalValue.value
    ? internalValue.value + ' ' + text
    : text
}

function onVoiceError(message: string) {
  showToast(t('aiChat.voiceErrorPermission'))
}

// Plus panel position: left-aligned with the + button, shown above it
// Uses ref updated on open + scroll/resize for reactive positioning
const panelPosition = ref<Record<string, string>>({})

function updatePanelPosition() {
  if (!panelTriggerRef.value || !panelOpen.value) return
  const rect = panelTriggerRef.value.getBoundingClientRect()
  nextTick(() => {
    const panelEl = panelRef.value
    const panelHeight = panelEl ? panelEl.offsetHeight : 162
    const gap = 8
    const panelTop = rect.top - panelHeight - gap
    const panelLeft = rect.left
    const panelWidth = panelEl ? panelEl.offsetWidth : 160
    let left = panelLeft
    if (left + panelWidth > window.innerWidth - 16) {
      left = Math.max(16, window.innerWidth - panelWidth - 16)
    }
    panelPosition.value = {
      position: 'fixed',
      top: `${Math.max(0, panelTop)}px`,
      left: `${left}px`,
      maxWidth: `calc(100vw - 32px)`,
    }
  })
}

function togglePanel() {
  panelOpen.value = !panelOpen.value
  if (panelOpen.value) {
    nextTick(() => updatePanelPosition())
  }
}

// Click outside handler (for plus panel)
function onDocClick(e: MouseEvent) {
  const target = e.target as HTMLElement
  // Close slash palette on any outside click (palette items use
  // @mousedown.prevent so they handle their own selection before this fires).
  if (slashPaletteOpen.value && !target.closest('.slash-palette') && !target.closest('.chat-textarea')) {
    closeSlashPalette()
  }
  if (!panelOpen.value) return
  // Don't close if clicking the trigger button or the panel itself
  if (panelTriggerRef.value?.contains(target)) return
  if (target.closest('.plus-panel')) return
  panelOpen.value = false
}

// Scroll/resize listener for reactive panel positioning
function onScrollOrResize() {
  updatePanelPosition()
}

onMounted(() => {
  syncDesktop()
  document.addEventListener('click', onDocClick, true)
  window.addEventListener('scroll', onScrollOrResize, true)
  window.addEventListener('resize', onScrollOrResize)
  // Listen for visualViewport changes (mobile Safari address bar show/hide)
  window.visualViewport?.addEventListener('resize', onScrollOrResize)
  // Re-evaluate desktop pointer media query changes
  window.matchMedia?.('(pointer: fine)').addEventListener('change', syncDesktop)
  // Listen for text selection quote events from SelectionToolbar
  window.addEventListener('ai-chat:quote', onQuoteEvent)
})

function onQuoteEvent(e: Event) {
  const detail = (e as CustomEvent).detail as { text: string }
  if (!detail?.text) return
  const quote = `> ${detail.text}\n\n`
  internalValue.value = internalValue.value + quote
  nextTick(() => inputRef.value?.focus())
}

onUnmounted(() => {
  document.removeEventListener('click', onDocClick, true)
  window.removeEventListener('scroll', onScrollOrResize, true)
  window.removeEventListener('resize', onScrollOrResize)
  window.visualViewport?.removeEventListener('resize', onScrollOrResize)
  window.matchMedia?.('(pointer: fine)').removeEventListener('change', syncDesktop)
  window.removeEventListener('ai-chat:quote', onQuoteEvent)
  abortInputPolish()
})
</script>

<template>
  <div
    class="input-box"
    :class="[
      status,
      { 'is-focused': focused, 'is-expanded': expanded, 'welcome-mode': isWelcomeMode }
    ]"
    @click.self="closePanel"
  >
    <div class="input-card-border">
      <div class="input-card-inner">
        <!-- Attachments preview row (above textarea) -->
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
            <button class="attachment-remove" :aria-label="t('common.delete')" @click="removeAttachment(idx)">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <line x1="18" y1="6" x2="6" y2="18"/>
                <line x1="6" y1="6" x2="18" y2="18"/>
              </svg>
            </button>
          </div>
        </div>

        <!-- Textarea container -->
        <div class="textarea-container">
          <!-- Slash command palette (U1) -->
          <SlashPalette
            :open="slashPaletteOpen"
            :commands="slashCommands"
            :selected-index="slashSelectedIndex"
            @select="selectSlashCommand"
          />
          <textarea
            ref="inputRef"
            v-model="internalValue"
            class="chat-textarea"
            :placeholder="isWelcomeMode ? t('aiChat.inputPlaceholder') : t('aiChat.continuePlaceholder')"
            :disabled="disabled || status === 'submitted'"
            aria-haspopup="menu"
            :aria-expanded="slashPaletteOpen"
            aria-controls="slash-palette-list"
            rows="4"
            @keydown.enter="onKeydownEnter"
            @keydown="onKeydownNav"
            @focus="focused = true"
            @blur="focused = false"
          />

          <!-- Expand button (top-right of textarea) -->
          <button
            v-if="showExpandIcon"
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
        </div>

        <!-- Bottom actions row (flexbox) -->
        <div class="bottom-actions-row">
          <!-- Left: Bottom toolbar controls -->
          <div class="input-controls">
            <!-- Plus panel (teleported, positioned relative to + button) -->
            <Teleport to="body">
              <Transition name="panel">
                <div v-if="panelOpen" ref="panelRef" class="plus-panel" role="menu" :aria-label="t('aiChat.moreFeatures')" :style="panelPosition">
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
              </Transition>
            </Teleport>

            <!-- [1] Agent button in welcome mode: readonly -> info popup, else -> agent picker -->
            <button
              v-if="agents && agents.length > 0 && isWelcomeMode"
              class="control-btn control-btn--agent"
              :class="{ 'agent-chat-icon': readonly }"
              :aria-label="readonly ? t('aiChat.agentInfoAria') : t('aiHub.selectAgent')"
              :title="readonly ? displayAgentLabel : t('aiHub.selectAgent')"
              @click="readonly ? onToggleAgentInfo() : emit('selectAgent')"
            >
              <!-- 小鸣 agent uses the colorful AIBrainIcon to match the agent picker -->
              <AIBrainIcon v-if="isNuminaAgent" :active="true" />
              <template v-else>
                <span v-if="displayAgentIcon && isEmoji(getAgentIcon(displayAgentIcon))" class="agent-emoji" aria-hidden="true">
                  {{ getAgentIcon(displayAgentIcon) }}
                </span>
                <IIcon v-else-if="displayAgentIcon" :icon="getAgentIcon(displayAgentIcon)" size="20" :color="selectedAgent?.color || 'var(--van-primary-color)'" />
                <svg v-else width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <rect x="3" y="3" width="18" height="18" rx="4"/>
                  <circle cx="8.5" cy="10" r="1.5" fill="currentColor"/>
                  <circle cx="15.5" cy="10" r="1.5" fill="currentColor"/>
                  <path d="M8 15c1 1.2 2.4 1.8 4 1.8s3-.6 4-1.8"/>
                </svg>
              </template>
            </button>
            <!-- Agent icon in chat mode: clickable to show info popup -->
            <button
              v-else-if="(displayAgentIcon || isNuminaAgent) && !isWelcomeMode"
              class="control-btn control-btn--agent agent-chat-icon"
              :aria-label="t('aiChat.agentInfoAria')"
              :title="displayAgentLabel"
              @click="onToggleAgentInfo"
            >
              <!-- 小鸣 agent uses the colorful AIBrainIcon to match the agent picker -->
              <AIBrainIcon v-if="isNuminaAgent" :active="true" />
              <template v-else>
                <span v-if="isEmoji(getAgentIcon(displayAgentIcon))" class="agent-emoji" aria-hidden="true">
                  {{ getAgentIcon(displayAgentIcon) }}
                </span>
                <IIcon v-else :icon="getAgentIcon(displayAgentIcon)" size="20" :color="selectedAgent?.color || 'var(--van-primary-color)'" />
              </template>
            </button>

            <!-- [2] Mode selector (4-mode DeerFlow) -->
            <ModeSelector
              :current-mode="context.mode"
              :supports-thinking="currentModelSupportsThinking"
              :ultra-disabled="isUltraDisabled"
              @select="onModeSelect"
            />

            <!-- [3] Web search toggle -->
            <button
              class="control-btn control-btn--search"
              :class="{ 'control-btn--active': webSearchEnabled }"
              :aria-pressed="webSearchEnabled"
              :aria-label="t('aiChat.webSearch')"
              :title="t('aiChat.webSearch')"
              @click="toggleWebSearch"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <circle cx="12" cy="12" r="10"/>
                <path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
              </svg>
              <span v-if="webSearchEnabled" class="control-indicator" aria-hidden="true"></span>
            </button>

            <!-- [4] Plus button -->
            <button
              ref="panelTriggerRef"
              class="control-btn control-btn--plus"
              :class="{ 'control-btn--open': panelOpen }"
              :aria-label="t('aiChat.moreFeatures')"
              :aria-expanded="panelOpen"
              @click.stop="togglePanel"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <line x1="12" y1="5" x2="12" y2="19"/>
                <line x1="5" y1="12" x2="19" y2="12"/>
              </svg>
            </button>
          </div>

          <!-- Right: Send/Stop button -->
          <div class="send-actions">
            <!-- Voice input button -->
            <VoiceInputButton @result="onVoiceResult" @error="onVoiceError" />

            <!-- Input polish (D3 DeerFlow sync) — rewrite draft via LLM -->
            <button
              v-if="inputPolishUndoAvailable"
              class="control-btn control-btn--polish-undo"
              :aria-label="t('aiChat.inputPolishUndo')"
              :title="t('aiChat.inputPolishUndo')"
              @click="onUndoPolishInput"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M3 7v6h6"/>
                <path d="M3 13a9 9 0 1 0 3-7.7L3 8"/>
              </svg>
            </button>
            <button
              v-else
              class="control-btn control-btn--polish"
              :class="{ 'control-btn--polishing': polishingInput }"
              :disabled="!canPolishInput"
              :aria-label="t('aiChat.inputPolish')"
              :title="t('aiChat.inputPolish')"
              @click="onPolishInput"
            >
              <svg v-if="!polishingInput" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M12 3l1.9 5.8L20 10.7l-5.1 1.9L12 18l-1.9-5.4L5 10.7l6.1-1.9z"/>
                <path d="M19 3v4M21 5h-4"/>
              </svg>
              <span v-else class="polish-spinner" aria-hidden="true"></span>
            </button>

            <!-- Send/Stop button -->
            <button
              v-if="status === 'streaming' || status === 'submitted'"
              class="send-btn send-btn--abort"
              :aria-label="t('aiChat.stopGeneration')"
              @click="emit('stop')"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <rect x="4" y="4" width="16" height="16" rx="2"/>
              </svg>
            </button>
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
      </div>
    </div>
    <!-- Agent info popup - teleported to body to escape stacking context -->
    <Teleport v-if="showAgentInfo && selectedAgent" to="body">
      <div
        class="agent-info-backdrop"
        @click="showAgentInfo = false"
      />
      <div
        class="agent-info-popup"
        role="dialog"
        aria-label="Agent information"
        @click.stop
      >
        <div class="agent-info-header">
          <span class="agent-info-icon" aria-hidden="true">
            <AIBrainIcon v-if="isNuminaAgent" :active="true" />
            <span v-else-if="displayAgentIcon && isEmoji(getAgentIcon(displayAgentIcon))">
              {{ getAgentIcon(displayAgentIcon) || '🤖' }}
            </span>
            <IIcon v-else-if="displayAgentIcon" :icon="getAgentIcon(displayAgentIcon)" size="24" :color="selectedAgent?.color || 'var(--van-primary-color)'" />
            <svg v-else width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <rect x="3" y="3" width="18" height="18" rx="4"/>
              <circle cx="8.5" cy="10" r="1.5" fill="currentColor"/>
              <circle cx="15.5" cy="10" r="1.5" fill="currentColor"/>
              <path d="M8 15c1 1.2 2.4 1.8 4 1.8s3-.6 4-1.8"/>
            </svg>
          </span>
          <span class="agent-info-name">{{ displayAgentLabel }}</span>
        </div>
        <p class="agent-info-description">{{ selectedAgent.description || t('aiChat.agentNoDescription') }}</p>
      </div>
    </Teleport>
    <!-- Hidden file inputs for panel actions -->
    <input ref="fileInputRef" type="file" accept=".pdf,.doc,.docx,.txt,.md" hidden @change="handleFileSelect" />
    <input ref="imageInputRef" type="file" accept="image/*" hidden @change="handleImageSelect" />
    <input ref="cameraInputRef" type="file" accept="image/*" capture="environment" hidden @change="handleCameraSelect" />
  </div>
</template>

<style scoped>
/* ── Theme variables override ── */
:global([data-theme='light'] .input-box),
.input-box {
  --ai-btn-border: rgba(0, 0, 0, 0.08);
  --ai-btn-color: var(--text-secondary, #666666);
  --ai-btn-hover-bg: rgba(0, 0, 0, 0.04);
  --ai-btn-hover-color: var(--text-primary, #111111);
  --ai-panel-bg: #ffffff;
  --ai-panel-border: rgba(0, 0, 0, 0.08);
  --ai-panel-item-color: var(--text-secondary, #666666);
  --ai-panel-item-hover-bg: rgba(0, 0, 0, 0.03);
  --ai-panel-item-hover-color: var(--text-primary, #111111);
  --ai-text-color: var(--text-primary, #111111);
  --ai-placeholder-color: var(--text-tertiary, #999999);
  --ai-scrollbar-thumb: rgba(0, 0, 0, 0.1);
  --ai-expand-color: var(--text-tertiary, #999999);
  --ai-expand-hover-bg: rgba(0, 0, 0, 0.04);
  --ai-expand-hover-color: var(--text-primary, #111111);
}

:global([data-theme='dark'] .input-box) {
  --ai-btn-border: rgba(255, 255, 255, 0.1);
  --ai-btn-color: var(--text-secondary, #c8c8d0);
  --ai-btn-hover-bg: rgba(255, 255, 255, 0.06);
  --ai-btn-hover-color: rgba(255, 255, 255, 0.9);
  --ai-panel-bg: #12122a;
  --ai-panel-border: rgba(255, 255, 255, 0.1);
  --ai-panel-item-color: rgba(255, 255, 255, 0.6);
  --ai-panel-item-hover-bg: rgba(255, 255, 255, 0.08);
  --ai-panel-item-hover-color: rgba(255, 255, 255, 0.9);
  --ai-text-color: rgba(255, 255, 255, 0.9);
  --ai-placeholder-color: rgba(255, 255, 255, 0.3);
  --ai-scrollbar-thumb: rgba(255, 255, 255, 0.15);
  --ai-expand-color: rgba(255, 255, 255, 0.3);
  --ai-expand-hover-bg: rgba(255, 255, 255, 0.08);
  --ai-expand-hover-color: rgba(255, 255, 255, 0.6);
}

.input-box {
  position: fixed;
  bottom: calc(50px + env(safe-area-inset-bottom));
  left: 0;
  right: 0;
  width: 100%;
  z-index: 100;
  display: flex;
  flex-direction: column;
  background: transparent;
  padding: 8px 16px;
  box-sizing: border-box;
  transition: all 0.2s ease;
}

/* Chat mode: participate in the flex column so MessageList can allocate space
   and content never overlaps the input. Welcome mode keeps fixed positioning
   (floats over the scrolling hub page). */
.input-box:not(.welcome-mode) {
  position: relative;
  bottom: auto;
  left: auto;
  right: auto;
  width: auto;
}

/* ── Premium Gradient Border wrapper ── */
.input-card-border {
  background: linear-gradient(135deg, #4040ff, #ff49fd, #d763fc, #3cc4fa);
  border-radius: 16px;
  padding: 1.5px; /* Border thickness */
  box-shadow: 0 8px 30px rgba(64, 64, 255, 0.05), 0 2px 8px rgba(0, 0, 0, 0.05);
  transition: box-shadow 0.25s ease, transform 0.25s ease;
  width: 100%;
  box-sizing: border-box;
}

.input-box.is-focused .input-card-border {
  box-shadow: 0 12px 32px rgba(64, 64, 255, 0.15), 0 4px 16px rgba(215, 99, 252, 0.08);
}

.input-card-inner {
  background: var(--bg-primary, #ffffff);
  border-radius: 14.5px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
  width: 100%;
  position: relative;
  transition: background-color 0.2s ease;
}

:global([data-theme='dark'] .input-card-inner) {
  background: var(--bg-primary, #010120);
}

/* ── Textarea container ── */
.textarea-container {
  position: relative;
  width: 100%;
  display: flex;
  flex-direction: column;
}

.chat-textarea {
  width: 100%;
  border: none;
  background: transparent;
  font-size: 14px;
  color: var(--ai-text-color);
  outline: none;
  resize: none;
  overflow-y: auto;
  line-height: 20px;
  height: 80px; /* Fixed height for 4 lines */
  min-height: 80px;
  padding: 0;
  padding-right: 36px; /* Avoid overlapping expand button */
  margin: 0;
  box-sizing: border-box;
  transition: height 0.2s ease;
  caret-color: #6366f1;
}

.input-box.is-expanded .chat-textarea {
  height: calc(66vh - 120px - env(safe-area-inset-bottom));
  min-height: 150px;
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

/* ── Expand button (top-right of textarea) ── */
.expand-btn {
  position: absolute;
  top: 0;
  right: 0;
  width: 32px;
  height: 32px;
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

/* ── Bottom actions row ── */
.bottom-actions-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 10px;
  width: 100%;
  box-sizing: border-box;
  position: relative;
}

.input-controls {
  display: flex;
  align-items: center;
  gap: 6px;
  position: relative;
}

.control-btn {
  width: 36px;
  height: 36px;
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
  min-width: 44px;
  min-height: 44px;
}

.control-btn :deep(svg),
.control-btn :deep(.iconify) {
  width: 20px;
  height: 20px;
}

/* Scale down AIBrainIcon to fit the control button and match other 20px icons */
.control-btn :deep(.ai-button-3d),
.agent-static-icon :deep(.ai-button-3d) {
  width: 32px;
  height: 32px;
  padding: 0;
  box-shadow: none;
  background: transparent;
  border: none;
  transform: none !important;
}

.control-btn :deep(.ai-button-wrapper),
.agent-static-icon :deep(.ai-button-wrapper) {
  transform: none !important;
}

.control-btn :deep(.fg-icon),
.agent-static-icon :deep(.fg-icon) {
  width: 20px;
  height: 20px;
}

.control-btn :deep(.bg-icon),
.agent-static-icon :deep(.bg-icon) {
  width: 18px;
  height: 18px;
}

.control-btn:hover {
  background: rgba(99, 102, 241, 0.15);
  color: var(--ai-btn-hover-color);
}

.control-btn:active {
  transform: scale(0.92);
}

.control-btn--active {
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  color: #ffffff;
  box-shadow: 0 2px 8px rgba(99, 102, 241, 0.4), 0 0 0 2px rgba(99, 102, 241, 0.2);
}

.control-btn--active:hover {
  background: linear-gradient(135deg, #7c3aed 0%, #a78bfa 100%);
  box-shadow: 0 3px 12px rgba(99, 102, 241, 0.5), 0 0 0 2px rgba(99, 102, 241, 0.3);
}

.control-btn--plus {
  transition: background 0.2s, color 0.2s, transform 0.2s;
}

.control-btn--open {
  transform: rotate(45deg);
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  color: #ffffff;
  box-shadow: 0 2px 8px rgba(99, 102, 241, 0.4);
}

/* Input polish (D3) */
.control-btn--polish:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.control-btn--polish:not(:disabled):hover {
  background: rgba(99, 102, 241, 0.16);
}

.control-btn--polishing {
  background: rgba(99, 102, 241, 0.16);
  cursor: progress;
}

.control-btn--polish-undo {
  background: rgba(99, 102, 241, 0.12);
  color: var(--ai-btn-color);
}

.control-btn--polish-undo:hover {
  background: rgba(99, 102, 241, 0.2);
}

.polish-spinner {
  width: 18px;
  height: 18px;
  border: 2px solid currentColor;
  border-top-color: transparent;
  border-radius: 50%;
  animation: polish-spin 0.7s linear infinite;
}

@keyframes polish-spin {
  to {
    transform: rotate(360deg);
  }
}

.control-indicator {
  position: absolute;
  top: 4px;
  right: 4px;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #10b981;
  box-shadow: 0 0 4px rgba(16, 185, 129, 0.6);
}

.agent-emoji {
  font-size: 18px;
  line-height: 1;
}

.agent-static-icon {
  font-size: 18px;
  line-height: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  min-width: 44px;
  min-height: 44px;
  border-radius: 50%;
  background: rgba(99, 102, 241, 0.12);
  cursor: default;
}



/* ── Attachments row ── */
.attachments-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 6px 0 8px;
  margin-bottom: 8px;
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

/* ── Plus panel ── */
.plus-panel {
  position: fixed;
  background: var(--ai-panel-bg);
  border: 1px solid var(--ai-panel-border);
  border-radius: 14px;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.15);
  z-index: 999;
  min-width: 160px;
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

/* ── Send Actions & Send Button ── */
.send-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.send-btn {
  width: 36px;
  height: 36px;
  min-width: 44px;
  min-height: 44px;
  border-radius: 50%;
  border: none;
  background: rgba(99, 102, 241, 0.15);
  color: rgba(99, 102, 241, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background 0.2s, color 0.2s, transform 0.15s;
  position: relative;
}

:global([data-theme='dark'] .send-btn) {
  background: rgba(255, 255, 255, 0.08);
  color: rgba(255, 255, 255, 0.4);
}

.send-btn--active {
  background: linear-gradient(135deg, #6366f1, #7c3aed);
  color: #fff !important;
  box-shadow: 0 2px 12px rgba(99, 102, 241, 0.3);
}

/* ── Pulse ripple on active send button ── */
.send-btn--active::after {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  width: 100%;
  height: 100%;
  border-radius: 50%;
  transform: translate(-50%, -50%) scale(1);
  opacity: 0;
  pointer-events: none;
  box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.6);
  animation: send-pulse-ripple 2.4s ease-out infinite;
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
  color: #fff !important;
  box-shadow: 0 2px 12px rgba(255, 59, 48, 0.4);
  cursor: pointer;
}

/* ── Pulse ripple on abort button ── */
.send-btn--abort::after {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  width: 100%;
  height: 100%;
  border-radius: 50%;
  transform: translate(-50%, -50%) scale(1);
  opacity: 0;
  pointer-events: none;
  box-shadow: 0 0 0 2px rgba(255, 59, 48, 0.6);
  animation: send-pulse-ripple 2.4s ease-out infinite;
}

.send-btn--abort:hover {
  transform: scale(1.05);
  background: #ff2d20;
}

.send-btn--abort:active {
  transform: scale(0.95);
}

@keyframes send-pulse-ripple {
  0% {
    transform: translate(-50%, -50%) scale(1);
    opacity: 0.6;
  }
  100% {
    transform: translate(-50%, -50%) scale(2.2);
    opacity: 0;
  }
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

/* ── Animations ── */
.animate-spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@media (prefers-reduced-motion: reduce) {
  .send-btn,
  .control-btn,
  .panel-enter-active,
  .panel-leave-active {
    transition: none;
  }
}

/* ── Responsive (375px) ── */
@media (max-width: 375px) {
  .input-box {
    padding: 8px 12px calc(8px + env(safe-area-inset-bottom)) 12px;
  }

  .input-box.welcome-mode {
    max-width: 95%;
  }

  .chat-textarea {
    font-size: 13px;
  }
}

/* ── Agent info popup (chat mode) ── */
.agent-info-backdrop {
  position: fixed;
  inset: 0;
  z-index: 2000;
}

.agent-info-popup {
  position: fixed;
  bottom: calc(120px + env(safe-area-inset-bottom));
  left: 20px;
  z-index: 2001;
  background: #ffffff;
  border: 1px solid rgba(0, 0, 0, 0.06);
  border-radius: 12px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
  min-width: 160px;
  max-width: 220px;
  padding: 12px 14px;
}

.agent-info-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.agent-info-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  line-height: 1;
}

.agent-info-icon :deep(.ai-button-wrapper) {
  transform: none !important;
}

.agent-info-icon :deep(.ai-button-3d) {
  width: 32px !important;
  height: 32px !important;
  padding: 0;
  box-shadow: none;
  background: transparent;
  border: none;
  transform: none !important;
}

.agent-info-icon :deep(.fg-icon) {
  width: 20px !important;
  height: 20px !important;
}

.agent-info-icon :deep(.bg-icon) {
  width: 18px !important;
  height: 18px !important;
}

.agent-info-name {
  font-size: 15px;
  font-weight: 600;
  color: rgba(0, 0, 0, 0.9);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.agent-info-description {
  font-size: 13px;
  color: rgba(0, 0, 0, 0.6);
  line-height: 1.5;
  margin: 0;
  word-break: break-word;
}

:global([data-theme='dark'] .agent-info-popup) {
  background: var(--bg-tertiary);
  border-color: rgba(255, 255, 255, 0.06);
  box-shadow: 0 8px 24px rgba(1, 1, 32, 0.2);
}

:global([data-theme='dark'] .agent-info-name) {
  color: var(--text-primary);
}

:global([data-theme='dark'] .agent-info-description) {
  color: var(--text-secondary);
}
</style>