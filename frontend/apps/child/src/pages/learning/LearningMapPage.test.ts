import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import zhCN from '@/i18n/locales/zh-CN'
import enUS from '@/i18n/locales/en-US'

// --- Mocks ---

type IndexRow = {
  topic_id: string
  mastery_level: string
  next_review_at: string | null
  subject?: string | null
  domain?: string | null
  age_group?: string | null
}

const rows: IndexRow[] = []

vi.mock('@/api/learning', () => ({
  getMyLearningMapIndex: vi.fn(),
  getTopicsBatch: vi.fn(),
  getClusters: vi.fn().mockResolvedValue([]),
  getBridges: vi.fn().mockResolvedValue([]),
  getTopicIndex: vi.fn().mockResolvedValue([]),
  getSubjectDependencies: vi.fn().mockResolvedValue([]),
  recordMapExploration: vi.fn().mockResolvedValue({}),
}))

const mockRouterPush = vi.fn()
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mockRouterPush }),
}))

vi.mock('@/composables/usePageLoading', () => ({
  usePageLoading: () => ({ increment: vi.fn(), decrement: vi.fn() }),
}))

const showToastMock = vi.fn()
vi.mock('vant', () => ({
  showToast: (...args: unknown[]) => showToastMock(...args),
  showFailToast: (...args: unknown[]) => showToastMock(...args),
  showSuccessToast: (...args: unknown[]) => showToastMock(...args),
}))

import {
  getMyLearningMapIndex,
  getTopicsBatch,
  getTopicIndex,
  getSubjectDependencies,
} from '@/api/learning'
import LearningMapPage from './LearningMapPage.vue'

const mockIndex = vi.mocked(getMyLearningMapIndex)
const mockBatch = vi.mocked(getTopicsBatch)
const mockGetTopicIndex = vi.mocked(getTopicIndex)
const mockGetSubjectDependencies = vi.mocked(getSubjectDependencies)

// --- Fixtures ---

function batchTopic(id: string, subject: string, domain: string) {
  return {
    id,
    topic_key: `key-${id}`,
    topic_type: 'CONCEPTUAL',
    subject,
    domain,
    name: `Topic ${id}`,
    name_zh: `主题 ${id}`,
    description: '',
    description_zh: null,
    age_range_start: 6,
    age_range_end: 8,
    age_group: 'mid',
    centrality: null,
    evidence: [],
    evidence_zh: null,
    assessment_prompt: null,
    assessment_prompt_zh: null,
    standards: [],
    ability_dimensions: null,
    deprecated: false,
    source_taxonomy: 'beijing',
    curriculum_standards: null,
  }
}

function mountPage() {
  const i18n = createI18n({
    legacy: false,
    locale: 'zh-CN',
    messages: { 'zh-CN': zhCN, 'en-US': enUS },
  })
  return mount(LearningMapPage, { global: { plugins: [i18n] } })
}

/** Click the "list" view toggle so ClusterMap renders (default is continent view). */
async function switchToListView(wrapper: ReturnType<typeof mountPage>) {
  const listBtn = wrapper.findAll('.view-mode-btn').find((b) => b.text().includes('列表') || b.text().includes('List'))
  if (listBtn) await listBtn.trigger('click')
  await flushPromises()
}

beforeEach(() => {
  vi.clearAllMocks()
  rows.length = 0
  mockIndex.mockImplementation(async () => rows.map((r) => ({ ...r })))
  mockBatch.mockImplementation(async (ids: string[]) =>
    ids.map((id) => {
      const row = rows.find((r) => r.topic_id === id)!
      return batchTopic(id, row.subject ?? 'mathematics', row.domain ?? 'Addition')
    }),
  )
})

// --- Tests ---

describe('LearningMapPage — cluster map integration', () => {
  it('renders subject tabs from the slim index before any topic detail loads', async () => {
    rows.push(
      { topic_id: 't1', mastery_level: 'available', next_review_at: null, subject: 'mathematics', domain: 'Addition', age_group: 'mid' },
      { topic_id: 't2', mastery_level: 'available', next_review_at: null, subject: 'science', domain: 'Units', age_group: 'mid' },
    )
    const wrapper = mountPage()
    await flushPromises()
    await switchToListView(wrapper)

    // Tabs come from the index alone — getClusters is not what builds them.
    const tabs = wrapper.findAll('.subject-tab')
    expect(tabs.length).toBe(2)
    expect(wrapper.findAll('.cluster-territory').length).toBeGreaterThan(0)
  })

  it('loads topic detail only for the selected subject (R10)', async () => {
    rows.push(
      { topic_id: 't1', mastery_level: 'available', next_review_at: null, subject: 'mathematics', domain: 'Addition', age_group: 'mid' },
      { topic_id: 't2', mastery_level: 'available', next_review_at: null, subject: 'science', domain: 'Units', age_group: 'mid' },
    )
    mountPage()
    await flushPromises()

    expect(mockBatch).toHaveBeenCalledTimes(1)
    const firstCallIds = mockBatch.mock.calls[0][0]
    // "mathematics" sorts before "science", so it is the default tab.
    expect(firstCallIds).toEqual(['t1'])
  })

  it('fetches the newly selected subject when the tab changes', async () => {
    rows.push(
      { topic_id: 't1', mastery_level: 'available', next_review_at: null, subject: 'mathematics', domain: 'Addition', age_group: 'mid' },
      { topic_id: 't2', mastery_level: 'available', next_review_at: null, subject: 'science', domain: 'Units', age_group: 'mid' },
    )
    const wrapper = mountPage()
    await flushPromises()

    const tabs = wrapper.findAll('.subject-tab')
    await tabs[1].trigger('click')
    await flushPromises()

    expect(mockBatch).toHaveBeenCalledTimes(2)
    expect(mockBatch.mock.calls[1][0]).toEqual(['t2'])
  })

  it('does not refetch a subject already loaded', async () => {
    rows.push(
      { topic_id: 't1', mastery_level: 'available', next_review_at: null, subject: 'mathematics', domain: 'Addition', age_group: 'mid' },
      { topic_id: 't2', mastery_level: 'available', next_review_at: null, subject: 'science', domain: 'Units', age_group: 'mid' },
    )
    const wrapper = mountPage()
    await flushPromises()
    expect(mockBatch).toHaveBeenCalledTimes(1)

    const tabs = wrapper.findAll('.subject-tab')
    await tabs[1].trigger('click')
    await flushPromises()
    await tabs[0].trigger('click')
    await flushPromises()

    // Back to mathematics — cached, so still only the two initial fetches.
    expect(mockBatch).toHaveBeenCalledTimes(2)
  })

  it('does not fire a duplicate batch request for the initially selected subject', async () => {
    rows.push({
      topic_id: 't1',
      mastery_level: 'available',
      next_review_at: null,
      subject: 'mathematics',
      domain: 'Addition',
      age_group: 'mid',
    })
    // Hold the batch open so the selectedSubject watcher runs while the first
    // fetch is still in flight — that interleaving is what produced the
    // duplicate request on a real (slow) network.
    let release!: () => void
    const gate = new Promise<void>((resolve) => {
      release = resolve
    })
    mockBatch.mockImplementationOnce(async (ids: string[]) => {
      await gate
      return ids.map((id) => batchTopic(id, 'mathematics', 'Addition'))
    })

    const wrapper = mountPage()
    await flushPromises()
    // Both load() and the watcher have now had a chance to start a fetch.
    expect(mockBatch).toHaveBeenCalledTimes(1)

    release()
    await flushPromises()
    wrapper.unmount()
  })

  it('keeps an active subject tab when a bridge targets a subject with no progress', async () => {
    rows.push({
      topic_id: 't1',
      mastery_level: 'available',
      next_review_at: null,
      subject: 'mathematics',
      domain: 'Addition',
      age_group: 'mid',
    })
    const wrapper = mountPage()
    await flushPromises()
    await switchToListView(wrapper)

    // A bridge to a subject the child has no progress in — no tab exists for it.
    wrapper.findComponent({ name: 'ClusterMap' }).vm.$emit('switchSubject', 'personal_social')
    await flushPromises()

    expect(wrapper.findAll('.subject-tab.active')).toHaveLength(1)
    expect(showToastMock).toHaveBeenCalled()
  })

  it('shows the empty state when the child has no progress at all', async () => {
    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.find('.learning-map-page').exists()).toBe(true)
    expect(wrapper.findAll('.subject-tab')).toHaveLength(0)
    expect(mockBatch).not.toHaveBeenCalled()
  })

  it('surfaces an error message when the index request fails', async () => {
    mockIndex.mockRejectedValue(new Error('boom'))
    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.find('.error-msg').exists()).toBe(true)
  })
})

// --- Knowledge ocean (#208) ---

describe('LearningMapPage — knowledge ocean default view (R1)', () => {
  beforeEach(() => {
    mockGetTopicIndex.mockImplementation(async () => [
      { id: 't1', subject: 'mathematics', domain: 'Addition', name: 'Add', name_zh: '加', age_group: 'mid' },
      { id: 't2', subject: 'mathematics', domain: 'Addition', name: 'Add more', name_zh: '再加', age_group: 'mid' },
      { id: 't3', subject: 'science', domain: 'Forces', name: 'Push', name_zh: '推', age_group: 'mid' },
    ])
    mockGetSubjectDependencies.mockImplementation(async () => [
      { topic_id: 't2', prerequisite_id: 't1', strength: 'hard' },
    ])
  })

  it('renders the knowledge ocean as the default view (R1)', async () => {
    rows.push(
      { topic_id: 't1', mastery_level: 'mastered', next_review_at: null, subject: 'mathematics', domain: 'Addition', age_group: 'mid' },
      { topic_id: 't2', mastery_level: 'available', next_review_at: null, subject: 'mathematics', domain: 'Addition', age_group: 'mid' },
      { topic_id: 't3', mastery_level: 'available', next_review_at: null, subject: 'science', domain: 'Forces', age_group: 'mid' },
    )
    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.findComponent({ name: 'KnowledgeOcean' }).exists()).toBe(true)
    // No view-mode toggle needed to see it — ocean is the default.
    expect(wrapper.find('.view-mode-btn--active').text()).toContain('大陆')
  })

  it('shows ocean islands for subjects the child has zero progress in (R2, AE1)', async () => {
    // Zero progress rows — only the topic index exists.
    const wrapper = mountPage()
    await flushPromises()

    const ocean = wrapper.findComponent({ name: 'KnowledgeOcean' })
    expect(ocean.exists()).toBe(true)
    const props = ocean.props() as unknown as { subjects: Array<{ id: string; masteryRatio: number }> }
    // Islands from the topic index, not progress
    expect(props.subjects.map((s) => s.id).sort()).toEqual(['mathematics', 'science'])
    // All heavily veiled (AE1)
    for (const s of props.subjects) {
      expect(s.masteryRatio).toBe(0)
    }
  })

  it('renders no empty state when progress is empty but topics exist (R2)', async () => {
    const wrapper = mountPage()
    await flushPromises()
    expect(wrapper.find('.ocean-sea').exists()).toBe(true)
  })
})

describe('LearningMapPage — ocean preview and exploration wiring (R6, R8, R11)', () => {
  beforeEach(() => {
    mockGetTopicIndex.mockImplementation(async () => [
      { id: 't1', subject: 'mathematics', domain: 'Addition', name: 'Add', name_zh: '加', age_group: 'mid' },
      { id: 't2', subject: 'mathematics', domain: 'Addition', name: 'Add more', name_zh: '再加', age_group: 'mid' },
      { id: 't3', subject: 'science', domain: 'Forces', name: 'Push', name_zh: '推', age_group: 'mid' },
    ])
    mockGetSubjectDependencies.mockImplementation(async () => [
      { topic_id: 't2', prerequisite_id: 't1', strength: 'hard' },
    ])
    rows.push(
      { topic_id: 't1', mastery_level: 'mastered', next_review_at: null, subject: 'mathematics', domain: 'Addition', age_group: 'mid' },
      { topic_id: 't2', mastery_level: 'available', next_review_at: null, subject: 'mathematics', domain: 'Addition', age_group: 'mid' },
      { topic_id: 't3', mastery_level: 'available', next_review_at: null, subject: 'science', domain: 'Forces', age_group: 'mid' },
    )
  })

  it('shows a preview popup when an island is tapped (R6, AE2)', async () => {
    const wrapper = mountPage()
    await flushPromises()

    const ocean = wrapper.findComponent({ name: 'KnowledgeOcean' })
    ocean.vm.$emit('previewSubject', 'science')
    await flushPromises()

    expect(wrapper.find('.ocean-preview').exists()).toBe(true)
    // Page mounts with locale zh-CN — display names follow the app language
    expect(wrapper.find('.ocean-preview__title').text()).toBe('科学')
  })

  it('preview continue button descends into the subject (AE2)', async () => {
    const wrapper = mountPage()
    await flushPromises()

    const ocean = wrapper.findComponent({ name: 'KnowledgeOcean' })
    ocean.vm.$emit('previewSubject', 'science')
    await flushPromises()

    await wrapper.find('.ocean-preview__btn').trigger('click')
    await flushPromises()

    // Descended: the ocean now receives the selected subject
    const props = ocean.props() as unknown as { selectedSubject: string }
    expect(props.selectedSubject).toBe('science')
    // Dependencies were loaded for the subject (R9)
    expect(mockGetSubjectDependencies).toHaveBeenCalledWith('science')
  })

  it('double-tap descend passes dependency edges down for the constellation (R9)', async () => {
    const wrapper = mountPage()
    await flushPromises()

    const ocean = wrapper.findComponent({ name: 'KnowledgeOcean' })
    ocean.vm.$emit('selectSubject', 'mathematics')
    await flushPromises()
    ocean.vm.$emit('selectDomain', { subject: 'mathematics', domain: 'Addition' })
    await flushPromises()

    const props = ocean.props() as unknown as {
      topics: Array<{ id: string }>
      edges: Array<{ topic_id: string }>
    }
    expect(props.topics.map((t) => t.id).sort()).toEqual(['t1', 't2'])
    expect(props.edges).toHaveLength(1)
  })

  it('topic selection navigates to the topic page (F2)', async () => {
    const wrapper = mountPage()
    await flushPromises()

    const ocean = wrapper.findComponent({ name: 'KnowledgeOcean' })
    ocean.vm.$emit('selectTopic', { id: 't2' })
    await flushPromises()

    expect(mockRouterPush).toHaveBeenCalledWith('/learning/topic/t2')
  })

  it('flushes exploration telemetry on unmount, even with no selection (R11, R12, AE4)', async () => {
    const { recordMapExploration } = await import('@/api/learning')
    const mockRecord = vi.mocked(recordMapExploration)
    mockRecord.mockClear()
    mockRecord.mockResolvedValue({} as never)

    const wrapper = mountPage()
    await flushPromises()
    oceanZoomViaEvents(wrapper, 1)
    wrapper.unmount()
    await flushPromises()

    expect(mockRecord).toHaveBeenCalledTimes(1)
    const payload = mockRecord.mock.calls[0][0]
    expect(payload.topic_selected).toBe(false)
    expect(payload.max_zoom_level).toBe(1)
  })

  function oceanZoomViaEvents(
    wrapper: ReturnType<typeof mountPage>,
    level: number,
  ) {
    const ocean = wrapper.findComponent({ name: 'KnowledgeOcean' })
    ocean.vm.$emit('zoomed', level)
    ocean.vm.$emit('interacted')
  }
})
