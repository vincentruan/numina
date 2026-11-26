/**
 * LearningCastle3DPage tests — route, fallback, layer switching.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import { createI18n } from 'vue-i18n'
import zhCN from '@/i18n/locales/zh-CN'

// Mock the API
vi.mock('@/api/learning', () => ({
  fetchCastle: vi.fn(),
  getTopicDetail: vi.fn(),
}))

// Mock WebGL detection — default available
vi.mock('@/composables/useWebGLAvailable', () => ({
  isWebGLAvailable: vi.fn(() => true),
  useWebGLAvailable: () => ({ available: { value: true } }),
  useReducedMotionCheck: () => ({ reduced: { value: false } }),
}))

// Stub heavy 3D components — no three.js in happy-dom
vi.mock('@/components/learning/castle3d/CastlePanorama.vue', () => ({
  default: {
    name: 'CastlePanorama',
    template: '<div class="stub-panorama" />',
    methods: {
      focusTower: vi.fn(() => Promise.resolve()),
      resetCamera: vi.fn(() => Promise.resolve()),
    },
  },
}))

import * as learningApi from '@/api/learning'
import * as webgl from '@/composables/useWebGLAvailable'
import LearningCastle3DPage from '../LearningCastle3DPage.vue'

const mockCastle = {
  towers: [
    {
      subject: 'mathematics',
      mastered_count: 4,
      learning_count: 2,
      review_due_count: 1,
      total_count: 10,
      floors: [
        { domain: 'fractions', mastered_count: 4, learning_count: 2, review_due_count: 1, total_count: 10 },
      ],
    },
  ],
  windows: [
    {
      topic_id: '123',
      topic_name: 'Fractions',
      topic_name_zh: '分数',
      reason: '复习到期',
      subject: 'mathematics',
      domain: 'fractions',
    },
  ],
  streak_days: 3,
}

function makeI18n() {
  return createI18n({
    legacy: false,
    locale: 'zh-CN',
    messages: { 'zh-CN': zhCN },
  })
}

async function mountPage() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/learning/castle-3d', component: LearningCastle3DPage },
      { path: '/learning/practice/:id', component: { template: '<div />' } },
    ],
  })
  await router.push('/learning/castle-3d')
  await router.isReady()

  return mount(LearningCastle3DPage, {
    global: {
      plugins: [router, makeI18n()],
      stubs: { RoleShimmer: true, KnowledgeCastle: true },
    },
  })
}

describe('LearningCastle3DPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(learningApi.fetchCastle).mockResolvedValue(mockCastle)
    vi.mocked(webgl.isWebGLAvailable).mockReturnValue(true)
  })

  it('renders error state when the castle request fails', async () => {
    vi.mocked(learningApi.fetchCastle).mockRejectedValue(new Error('boom'))
    const wrapper = await mountPage()
    await vi.waitFor(() => {
      expect(wrapper.find('[data-test="castle3d-error"]').exists()).toBe(true)
    })
  })

  it('renders 3D stage when WebGL is available', async () => {
    const wrapper = await mountPage()
    await vi.waitFor(() => {
      expect(wrapper.find('[data-test="castle3d-stage"]').exists()).toBe(true)
    })
  })

  it('falls back to 2D castle when WebGL is unavailable', async () => {
    vi.mocked(webgl.isWebGLAvailable).mockReturnValue(false)
    const wrapper = await mountPage()
    await vi.waitFor(() => {
      expect(wrapper.findComponent({ name: 'KnowledgeCastle' }).exists()).toBe(true)
    })
    expect(wrapper.find('[data-test="castle3d-stage"]').exists()).toBe(false)
  })

  it('does not render the tower layer in the panorama state', async () => {
    const wrapper = await mountPage()
    await vi.waitFor(() => {
      expect(wrapper.find('[data-test="castle3d-stage"]').exists()).toBe(true)
    })
    expect(wrapper.find('[data-test="castle3d-tower"]').exists()).toBe(false)
  })

  it('shows the streak when streak_days > 0', async () => {
    const wrapper = await mountPage()
    await vi.waitFor(() => {
      expect(wrapper.text()).toContain('3')
    })
  })

  it('navigates to practice when a window is selected', async () => {
    const wrapper = await mountPage()
    await vi.waitFor(() => {
      expect(wrapper.find('[data-test="castle3d-stage"]').exists()).toBe(true)
    })

    const panorama = wrapper.findComponent({ name: 'CastlePanorama' })
    panorama.vm.$emit('windowSelect', mockCastle.windows[0])
    await vi.waitFor(() => {
      expect(wrapper.vm.$route.path).toBe('/learning/practice/123')
    })
  })

  it('switches to the tower layer on towerSelect and back', async () => {
    const wrapper = await mountPage()
    await vi.waitFor(() => {
      expect(wrapper.find('[data-test="castle3d-stage"]').exists()).toBe(true)
    })

    const panorama = wrapper.findComponent({ name: 'CastlePanorama' })
    panorama.vm.$emit('towerSelect', 'mathematics')
    await vi.waitFor(() => {
      expect(wrapper.find('[data-test="castle3d-tower"]').exists()).toBe(true)
    })

    await wrapper.find('[data-test="castle3d-back"]').trigger('click')
    await vi.waitFor(() => {
      expect(wrapper.find('[data-test="castle3d-tower"]').exists()).toBe(false)
    })
  })
})
