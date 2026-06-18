// Vitest global setup for HMR mocks and Vant stubs
import { vi } from 'vitest'
import { config } from '@vue/test-utils'

// Mock import.meta.hot before any modules load
const mockHotData: Record<string, unknown> = {}

if (!globalThis.importMetaHotMocked) {
  Object.defineProperty(globalThis, 'importMetaHotMocked', {
    value: true,
    writable: false,
  })

  const originalImportMeta = globalThis.importMeta

  globalThis.importMeta = {
    ...originalImportMeta,
    hot: {
      data: mockHotData,
      accept: vi.fn(),
      dispose: vi.fn(),
      invalidate: vi.fn(),
      on: vi.fn(),
    },
  }

  // Also stub for vitest
  vi.stubGlobal('import.meta', globalThis.importMeta)
}

// Mock NProgress for router loading indicator
vi.mock('nprogress', () => ({
  default: {
    start: vi.fn(),
    done: vi.fn(),
    configure: vi.fn(),
  },
}))
vi.mock('nprogress/nprogress.css', () => ({ default: {} }))

// Mock the loading composable to prevent import.meta.hot initialization issues
vi.mock('../../packages/auth/src/composables/loading', () => ({
  useLoadingOverlay: () => ({
    isLoading: { value: false },
    isDismissing: { value: false },
    increment: vi.fn(),
    decrement: vi.fn(),
    show: vi.fn(),
    hide: vi.fn(),
  }),
}))

// Mock the page loading composable
vi.mock('@/composables/usePageLoading', () => ({
  usePageLoading: () => ({
    increment: vi.fn(),
    decrement: vi.fn(),
    complete: vi.fn(),
    isGlobalLoading: { value: false },
  }),
  globalLoadingCount: { value: 0 },
  completeGlobalLoading: vi.fn(),
}))

// ─────────────────────────────────────────────────────────────────────────────
// Global Vant component stubs — eliminates Vue warnings in tests
// ─────────────────────────────────────────────────────────────────────────────
config.global.stubs = {
  // Navigation & Layout
  VanNavBar: { template: '<header class="van-nav-bar"><slot /></header>' },
  VanTabBar: { template: '<nav class="van-tabbar"><slot /></nav>' },
  VanTabBarItem: { template: '<div class="van-tabbar-item"><slot /></div>' },
  VanTabs: {
    template: '<div class="van-tabs"><slot /></div>',
    props: ['active', 'animated', 'swipeable'],
  },
  VanTab: { template: '<div class="van-tab"><slot /></slot>', props: ['title', 'name'] },
  VanCollapse: { template: '<div class="van-collapse"><slot /></div>' },
  VanCollapseItem: {
    template: '<div class="van-collapse-item"><slot name="title" /><slot /></div>',
    props: ['title', 'name', 'icon'],
  },
  VanCellGroup: { template: '<div class="van-cell-group"><slot /></div>' },
  VanCell: {
    template: '<div class="van-cell"><slot name="title" /><slot name="value" /></div>',
    props: ['title', 'value', 'icon', 'isLink', 'clickable'],
  },
  VanPopup: { template: '<div class="van-popup"><slot /></div>', props: ['show', 'position', 'round'] },
  VanDialog: {
    template: '<div class="van-dialog"><slot /></div>',
    props: ['show', 'title', 'message', 'showCancelButton', 'showConfirmButton'],
  },
  VanActionSheet: {
    template: '<div class="van-action-sheet"><slot /></div>',
    props: ['show', 'actions', 'cancelText'],
  },

  // Form inputs
  VanField: {
    template: '<input class="van-field" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
    props: ['modelValue', 'placeholder', 'type', 'label', 'disabled', 'error', 'errorMessage', 'rows', 'autosize', 'maxlength', 'showWordLimit', 'clearable', 'autofocus'],
    emits: ['update:modelValue'],
  },
  VanCheckbox: {
    template: '<label class="van-checkbox"><input type="checkbox" :checked="modelValue" @change="$emit(\'update:modelValue\', $event.target.checked)" /><slot /></label>',
    props: ['modelValue', 'disabled', 'shape', 'labelDisabled'],
    emits: ['update:modelValue', 'change'],
  },
  VanRadio: { template: '<label class="van-radio"><slot /></label>', props: ['name', 'disabled'] },
  VanRadioGroup: { template: '<div class="van-radio-group"><slot /></div>', props: ['modelValue'] },
  VanSwitch: { template: '<button class="van-switch" />', props: ['modelValue', 'disabled', 'size', 'activeColor', 'inactiveColor'] },
  VanStepper: { template: '<div class="van-stepper" />', props: ['modelValue', 'min', 'max', 'step', 'disabled'] },
  VanPicker: { template: '<div class="van-picker"><slot /></div>', props: ['columns', 'showToolbar', 'title'] },
  VanDatetimePicker: { template: '<div class="van-datetime-picker" />', props: ['type', 'minDate', 'maxDate', 'modelValue'] },
  VanSearch: { template: '<div class="van-search"><slot /></div>', props: ['modelValue', 'placeholder', 'shape'] },

  // Buttons & Icons
  VanButton: {
    template: '<button class="van-button" :disabled="disabled" :loading="loading"><slot /></button>',
    props: ['type', 'size', 'block', 'plain', 'round', 'square', 'disabled', 'loading', 'icon', 'iconPosition'],
  },
  VanIcon: { template: '<i class="van-icon" />', props: ['name', 'size', 'color', 'dot', 'badge'] },

  // Feedback
  VanLoading: { template: '<div class="van-loading"><slot /></div>', props: ['size', 'color', 'type', 'vertical'] },
  VanToast: { template: '<div class="van-toast" />', props: ['type', 'message', 'position', 'duration', 'forbidClick'] },
  VanEmpty: { template: '<div class="van-empty"><slot /></div>', props: ['description', 'image', 'imageSize'] },
  VanSkeleton: { template: '<div class="van-skeleton"><slot /></div>', props: ['title', 'avatar', 'row', 'rowWidth', 'animate'] },
  VanNoticeBar: { template: '<div class="van-notice-bar"><slot /></div>', props: ['text', 'mode', 'wrapable', 'scrollable'] },
  VanBadge: { template: '<div class="van-badge"><slot /></div>', props: ['content', 'color', 'dot', 'max'] },

  // Lists
  VanList: {
    template: '<div class="van-list"><slot /></div>',
    props: ['loading', 'finished', 'finishedText', 'error', 'errorText', 'immediateCheck'],
    emits: ['load'],
  },
  VanPullRefresh: {
    template: '<div class="van-pull-refresh"><slot /></div>',
    props: ['modelValue', 'pullingText', 'loosingText', 'loadingText', 'successText', 'successDuration', 'animationDuration', 'headHeight', 'pullDistance'],
    emits: ['update:modelValue', 'refresh'],
  },
  VanSwipe: { template: '<div class="van-swipe"><slot /></div>', props: ['autoplay', 'duration', 'initialSwipe', 'loop', 'showIndicators'] },
  VanSwipeItem: { template: '<div class="van-swipe-item"><slot /></div>' },
  VanGrid: { template: '<div class="van-grid"><slot /></div>', props: ['columnNum', 'border', 'square', 'gutter', 'clickable', 'center'] },
  VanGridItem: { template: '<div class="van-grid-item"><slot /></div>', props: ['icon', 'text', 'badge', 'dot'] },

  // Overlay
  VanOverlay: { template: '<div class="van-overlay"><slot /></div>', props: ['show', 'zIndex', 'duration', 'className', 'customStyle'] },
  VanImage: { template: '<img class="van-image" />', props: ['src', 'alt', 'width', 'height', 'fit', 'round', 'radius', 'lazyLoad', 'showLoading', 'showError'] },
  VanTag: { template: '<span class="van-tag"><slot /></span>', props: ['type', 'size', 'color', 'plain', 'round', 'mark', 'textColor', 'closeable'] },
  VanDivider: { template: '<hr class="van-divider" />', props: ['dashed', 'hairline', 'contentPosition'] },
  VanSlider: { template: '<input type="range" class="van-slider" />', props: ['modelValue', 'min', 'max', 'step', 'barHeight', 'buttonSize', 'disabled'] },
  VanRate: { template: '<div class="van-rate" />', props: ['modelValue', 'count', 'size', 'icon', 'voidIcon', 'color', 'voidColor', 'disabled'] },
  VanProgress: { template: '<div class="van-progress" />', props: ['percentage', 'strokeWidth', 'color', 'trackColor', 'pivotText', 'pivotColor', 'showPivot'] },
  VanPopover: { template: '<div class="van-popover"><slot /></div>', props: ['show', 'placement', 'actions'] },

  // DeerFlow ai-chat component stubs
  TokenUsage: { template: '<div class="token-usage"></div>', props: ['threadId', 'refreshTrigger'] },
  MessageGroup: { template: '<div class="message-group"><slot /></div>', props: ['group', 'isLoading', 'threadId'] },
  ChainOfThought: { template: '<div class="chain-of-thought"><slot /></div>' },
  SubtaskCard: { template: '<div class="subtask-card"></div>', props: ['taskId', 'isLoading'] },
  ArtifactFileList: { template: '<div class="artifact-file-list"><slot /></div>', props: ['artifacts', 'sessionId'] },
  ArtifactPreviewPopup: { template: '<div class="artifact-preview"><slot /></div>', props: ['show', 'artifact', 'sessionId'] },
  Suggestions: { template: '<div class="suggestions"><slot /></div>', props: ['suggestions', 'loading', 'hidden'] },
  MarkdownContent: { template: '<div class="markdown-content"></div>', props: ['content', 'isLoading'] },
  AssistantMessage: { template: '<div class="assistant-message"><slot /></div>', props: ['id', 'content', 'phase', 'displayTime', 'suggestions', 'feedback'] },
  UserBubble: { template: '<div class="user-bubble"></div>', props: ['content', 'displayTime', 'sendStatus'] },
  InputBox: { template: '<div class="input-box"><slot /></div>', props: ['status', 'isWelcomeMode', 'threadId', 'initialMode', 'initialModelName'] },
  ModeSelector: { template: '<div class="mode-selector"></div>', props: ['currentMode', 'supportsThinking', 'ultraDisabled'] },
  ModelSelectorPopup: { template: '<div class="model-selector-popup"><slot /></div>', props: ['show', 'models', 'currentModel'] },
}

// ─────────────────────────────────────────────────────────────────────────────
// Suppress console output in tests for machine-friendly logs
// ─────────────────────────────────────────────────────────────────────────────
// Keep errors visible (for debugging) but suppress info/debug logs
vi.spyOn(console, 'log').mockImplementation(() => {})
vi.spyOn(console, 'info').mockImplementation(() => {})
vi.spyOn(console, 'debug').mockImplementation(() => {})
// Keep console.warn and console.error visible for test debugging
// vi.spyOn(console, 'warn').mockImplementation(() => {})
// vi.spyOn(console, 'error').mockImplementation(() => {})