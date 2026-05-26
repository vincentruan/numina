// Vitest global setup for child frontend tests
import { vi } from 'vitest'
import { config } from '@vue/test-utils'

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
  VanPopup: { template: '<div class="van-popup"><slot /></div>', props: ['show', 'position', 'round'] },
  VanDialog: {
    template: '<div class="van-dialog"><slot /></div>',
    props: ['show', 'title', 'message', 'showCancelButton', 'showConfirmButton'],
  },

  // Buttons & Icons
  VanButton: {
    template: '<button class="van-button" :disabled="disabled"><slot /></button>',
    props: ['type', 'size', 'disabled', 'loading', 'icon'],
  },
  VanIcon: { template: '<i class="van-icon" />', props: ['name', 'size', 'color'] },

  // Feedback
  VanLoading: { template: '<div class="van-loading"><slot /></div>', props: ['size', 'color', 'type'] },
  VanEmpty: { template: '<div class="van-empty"><slot /></div>', props: ['description', 'image', 'imageSize'] },
  VanToast: { template: '<div class="van-toast" />', props: ['type', 'message', 'position'] },

  // Lists
  VanList: {
    template: '<div class="van-list"><slot /></div>',
    props: ['loading', 'finished', 'finishedText'],
    emits: ['load'],
  },
  VanPullRefresh: {
    template: '<div class="van-pull-refresh"><slot /></div>',
    props: ['modelValue'],
    emits: ['update:modelValue', 'refresh'],
  },
  VanSwipe: { template: '<div class="van-swipe"><slot /></div>', props: ['autoplay', 'loop'] },
  VanSwipeItem: { template: '<div class="van-swipe-item"><slot /></div>' },
  VanGrid: { template: '<div class="van-grid"><slot /></div>', props: ['columnNum', 'border'] },
  VanGridItem: { template: '<div class="van-grid-item"><slot /></div>', props: ['icon', 'text'] },

  // Form inputs
  VanField: {
    template: '<input class="van-field" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
    props: ['modelValue', 'placeholder', 'type', 'label', 'disabled'],
    emits: ['update:modelValue'],
  },

  // Overlays
  VanOverlay: { template: '<div class="van-overlay"><slot /></div>', props: ['show', 'zIndex'] },
  VanImage: { template: '<img class="van-image" />', props: ['src', 'alt', 'width', 'height'] },
}

// ─────────────────────────────────────────────────────────────────────────────
// Suppress console output in tests for machine-friendly logs
// ─────────────────────────────────────────────────────────────────────────────
vi.spyOn(console, 'log').mockImplementation(() => {})
vi.spyOn(console, 'info').mockImplementation(() => {})
vi.spyOn(console, 'debug').mockImplementation(() => {})