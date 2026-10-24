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

import { getMyLearningMapIndex, getTopicsBatch } from '@/api/learning'
import LearningMapPage from './LearningMapPage.vue'

const mockIndex = vi.mocked(getMyLearningMapIndex)
const mockBatch = vi.mocked(getTopicsBatch)

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
