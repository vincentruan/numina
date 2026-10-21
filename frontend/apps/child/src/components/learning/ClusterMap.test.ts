import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'
import { createI18n } from 'vue-i18n'
import type {
  ProgressWithTopic,
  TopicResponse,
  ClusterResponse,
  BridgeResponse,
} from '@/api/learning'
import zhCN from '@/i18n/locales/zh-CN'
import enUS from '@/i18n/locales/en-US'

// --- Mocks ---

vi.mock('@/api/learning', () => ({
  getClusters: vi.fn(),
  getBridges: vi.fn(),
}))

const mockRouterPush = vi.fn()
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mockRouterPush }),
}))

import { getClusters, getBridges } from '@/api/learning'
import ClusterMap from './ClusterMap.vue'

const mockGetClusters = vi.mocked(getClusters)
const mockGetBridges = vi.mocked(getBridges)

// --- Fixtures ---

function makeTopic(overrides: Partial<TopicResponse> = {}): TopicResponse {
  return {
    id: 't1',
    topic_key: 't1',
    topic_type: 'CONCEPTUAL',
    subject: 'mathematics',
    domain: 'Addition',
    name: 'Addition',
    name_zh: '加法',
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
    ...overrides,
  }
}

function makeItem(overrides: Partial<ProgressWithTopic> = {}): ProgressWithTopic {
  return {
    id: 'p1',
    child_id: 'c1',
    topic_id: 't1',
    mastery_level: 'available',
    mastery_score: null,
    completed_via: null,
    attempts: 0,
    xp_earned: 0,
    last_practice_at: null,
    first_mastered_at: null,
    stability: null,
    next_review_at: null,
    ability_dimensions_score: null,
    topic: makeTopic(),
    ...overrides,
  }
}

function makeCluster(overrides: Partial<ClusterResponse> = {}): ClusterResponse {
  return {
    id: 'cl1',
    subject: 'mathematics',
    domain: 'Addition',
    age_range_start: 6,
    age_group: 'mid',
    summary: '',
    topic_count: 1,
    ...overrides,
  }
}

// Mounted hosts are attached to the document (the scroll path resolves its
// target with document.querySelector), so they must be torn down between
// tests — otherwise stale territory nodes from earlier mounts leak into
// every later query.
const hosts: HTMLElement[] = []

afterEach(() => {
  for (const host of hosts.splice(0)) host.remove()
})

function mountMap(items: ProgressWithTopic[], subject = 'mathematics') {
  const i18n = createI18n({
    legacy: false,
    locale: 'zh-CN',
    messages: { 'zh-CN': zhCN, 'en-US': enUS },
  })
  // attachTo: the bridge/frontier scroll resolves its target with
  // document.querySelector, which needs the tree in the document.
  const host = document.createElement('div')
  document.body.appendChild(host)
  hosts.push(host)
  return mount(ClusterMap, {
    attachTo: host,
    props: { items, selectedSubject: subject },
    global: { plugins: [i18n] },
  })
}

beforeEach(() => {
  vi.clearAllMocks()
  mockGetClusters.mockResolvedValue([makeCluster()])
  mockGetBridges.mockResolvedValue([])
})

// --- Tests ---

describe('ClusterMap', () => {
  it('renders one territory per domain with its topic nodes', async () => {
    mockGetClusters.mockResolvedValue([
      makeCluster({ id: 'cl1', domain: 'Addition' }),
      makeCluster({ id: 'cl2', domain: 'Subtraction' }),
    ])
    const wrapper = mountMap([
      makeItem({ id: 'p1', topic: makeTopic({ id: 't1', domain: 'Addition' }) }),
      makeItem({ id: 'p2', topic: makeTopic({ id: 't2', domain: 'Subtraction' }) }),
    ])
    await flushPromises()

    const territories = wrapper.findAll('.cluster-territory')
    expect(territories).toHaveLength(2)
    expect(territories[0].attributes('data-cluster-domain')).toBe('Addition')
    expect(territories[1].attributes('data-cluster-domain')).toBe('Subtraction')
    expect(wrapper.findAll('.topic-node')).toHaveLength(2)
  })

  it('routes a learning node to practice', async () => {
    const wrapper = mountMap([makeItem({ mastery_level: 'learning' })])
    await flushPromises()

    await wrapper.find('.topic-node-wrapper').trigger('click')

    expect(mockRouterPush).toHaveBeenCalledWith('/learning/topic/t1?action=practice')
  })

  it('routes an available node to practice', async () => {
    const wrapper = mountMap([makeItem({ mastery_level: 'available' })])
    await flushPromises()

    await wrapper.find('.topic-node-wrapper').trigger('click')

    expect(mockRouterPush).toHaveBeenCalledWith('/learning/topic/t1?action=practice')
  })

  it('routes a mastered node to the topic page without an action', async () => {
    const wrapper = mountMap([makeItem({ mastery_level: 'mastered' })])
    await flushPromises()

    await wrapper.find('.topic-node-wrapper').trigger('click')

    expect(mockRouterPush).toHaveBeenCalledWith('/learning/topic/t1')
  })

  it('routes a review-due mastered node to review', async () => {
    const wrapper = mountMap([
      makeItem({
        mastery_level: 'mastered',
        next_review_at: new Date(Date.now() - 86_400_000).toISOString(),
      }),
    ])
    await flushPromises()

    await wrapper.find('.topic-node-wrapper').trigger('click')

    expect(mockRouterPush).toHaveBeenCalledWith('/learning/topic/t1?action=review')
  })

  it('opens prerequisite guidance instead of navigating for a locked node', async () => {
    const wrapper = mountMap([makeItem({ mastery_level: 'locked' })])
    await flushPromises()

    await wrapper.find('.topic-node-wrapper').trigger('click')

    expect(mockRouterPush).not.toHaveBeenCalled()
    expect(wrapper.find('.prereq-guidance').exists()).toBe(true)
  })

  it('colours nodes by mastery state', async () => {
    mockGetClusters.mockResolvedValue([makeCluster({ topic_count: 5 })])
    const wrapper = mountMap([
      makeItem({ id: 'p1', topic: makeTopic({ id: 't1' }), mastery_level: 'mastered' }),
      makeItem({ id: 'p2', topic: makeTopic({ id: 't2' }), mastery_level: 'learning' }),
      makeItem({ id: 'p3', topic: makeTopic({ id: 't3' }), mastery_level: 'available' }),
      makeItem({ id: 'p4', topic: makeTopic({ id: 't4' }), mastery_level: 'locked' }),
      makeItem({
        id: 'p5',
        topic: makeTopic({ id: 't5' }),
        mastery_level: 'mastered',
        next_review_at: new Date(Date.now() - 86_400_000).toISOString(),
      }),
    ])
    await flushPromises()

    const classes = wrapper.findAll('.topic-node').map((n) => n.classes().join(' '))
    for (const state of ['mastered', 'learning', 'available', 'locked', 'review']) {
      expect(classes.some((c) => c.includes(`topic-node--${state}`))).toBe(true)
    }
  })

  it('shows mastered/total in the progress bar', async () => {
    mockGetClusters.mockResolvedValue([makeCluster({ topic_count: 3 })])
    const wrapper = mountMap([
      makeItem({ id: 'p1', topic: makeTopic({ id: 't1' }), mastery_level: 'mastered' }),
      makeItem({ id: 'p2', topic: makeTopic({ id: 't2' }), mastery_level: 'available' }),
      makeItem({ id: 'p3', topic: makeTopic({ id: 't3' }), mastery_level: 'locked' }),
    ])
    await flushPromises()

    expect(wrapper.find('.cluster-map__progress-text').text()).toBe('1/3 已掌握')
  })

  it('marks the frontier topic when the subject is not fully mastered', async () => {
    mockGetClusters.mockResolvedValue([makeCluster({ topic_count: 3 })])
    const wrapper = mountMap([
      makeItem({
        id: 'p1',
        topic: makeTopic({ id: 't1', name_zh: '已掌握项' }),
        mastery_level: 'mastered',
      }),
      makeItem({
        id: 'p2',
        topic: makeTopic({ id: 't2', name_zh: '当前学习项' }),
        mastery_level: 'learning',
      }),
      makeItem({
        id: 'p3',
        topic: makeTopic({ id: 't3', name_zh: '未解锁项' }),
        mastery_level: 'locked',
      }),
    ])
    await flushPromises()

    const here = wrapper.findAll('.topic-node__here')
    expect(here).toHaveLength(1)
    // The frontier marker goes on the learning topic, not the mastered one.
    expect(wrapper.find('.topic-node--frontier').text()).toContain('当前学习项')
  })

  it('celebrates and drops the frontier marker when everything is mastered', async () => {
    mockGetClusters.mockResolvedValue([makeCluster({ topic_count: 2 })])
    const wrapper = mountMap([
      makeItem({ id: 'p1', topic: makeTopic({ id: 't1' }), mastery_level: 'mastered' }),
      makeItem({ id: 'p2', topic: makeTopic({ id: 't2' }), mastery_level: 'mastered' }),
    ])
    await flushPromises()

    expect(wrapper.find('.cluster-map__celebration').exists()).toBe(true)
    expect(wrapper.findAll('.topic-node__here')).toHaveLength(0)
  })

  it('renders a bridge badge and emits switchSubject on tap', async () => {
    const bridge: BridgeResponse = {
      from_cluster_domain: 'Addition',
      from_subject: 'mathematics',
      to_cluster_domain: 'Units',
      to_subject: 'science',
      edge_count: 1,
    }
    mockGetBridges.mockResolvedValue([bridge])
    const wrapper = mountMap([makeItem()])
    await flushPromises()

    const badge = wrapper.find('.bridge-badge')
    expect(badge.exists()).toBe(true)

    await badge.trigger('click')
    const emitted = wrapper.emitted('switchSubject')
    expect(emitted).toBeTruthy()
    expect(emitted![0]).toEqual(['science'])
  })

  it('scrolls to the bridge target after the new subject data lands', async () => {
    // Regression: the territories watcher was registered with `once: true`,
    // so it de-registered after the initial frontier scroll and the bridge
    // scroll never ran — the target territory only exists after the
    // subject-switch refetch resolves.
    const bridge: BridgeResponse = {
      from_cluster_domain: 'Addition',
      from_subject: 'mathematics',
      to_cluster_domain: 'Units',
      to_subject: 'science',
      edge_count: 1,
    }
    mockGetBridges.mockResolvedValue([bridge])
    const wrapper = mountMap([makeItem()])
    await flushPromises()

    // Drop anything the initial frontier scroll recorded.
    const scrollSpy = vi
      .spyOn(Element.prototype, 'scrollIntoView')
      .mockImplementation(() => {})
    scrollSpy.mockClear()

    await wrapper.find('.bridge-badge').trigger('click')
    await flushPromises()

    // Parent reacts to switchSubject by moving to the science tab; its data
    // resolves only now — the scroll has to wait for that territories update.
    mockGetClusters.mockResolvedValue([
      makeCluster({ id: 'cl2', subject: 'science', domain: 'Units', topic_count: 1 }),
    ])
    await wrapper.setProps({
      selectedSubject: 'science',
      items: [
        makeItem({
          id: 'p2',
          topic: makeTopic({ id: 't2', subject: 'science', domain: 'Units' }),
        }),
      ],
    })
    // Let the switch's getClusters/getBridges resolve, then the post-flush
    // watcher that scrolls once the new territory is actually rendered.
    await flushPromises()
    await nextTick()
    await flushPromises()

    // mock.contexts is the `this` of each call — the element scrollIntoView
    // was invoked on. (mock.instances only records `new`-style construction.)
    // The scroll anchors on the territory card; fall back to the section.
    const scrolledDomains = scrollSpy.mock.contexts.map(
      (c) =>
        (c as Element).getAttribute('data-cluster-domain') ??
        (c as Element).getAttribute('data-domain'),
    )
    expect(scrolledDomains).toContain('Units')
    scrollSpy.mockRestore()
  })

  it('auto-expands a collapsed bridge target before scrolling (R6)', async () => {
    const bridge: BridgeResponse = {
      from_cluster_domain: 'Addition',
      from_subject: 'mathematics',
      to_cluster_domain: 'Units',
      to_subject: 'science',
      edge_count: 1,
    }
    mockGetBridges.mockResolvedValue([bridge])
    const wrapper = mountMap([makeItem()])
    await flushPromises()

    // Capture the section's class list at the moment of the scroll — the
    // `--instant` marker is only present while the scroll is firing.
    const headersAtScrollTime: string[] = []
    const scrollSpy = vi
      .spyOn(Element.prototype, 'scrollIntoView')
      .mockImplementation(function (this: Element) {
        // The flag lives on the header, a sibling of the collapse wrapper;
        // find the enclosing section and read its header.
        const section = (this.closest?.('.domain-section[data-domain]') ?? null) as HTMLElement | null
        if (section) {
          const header = section.querySelector('.domain-section__header')
          if (header instanceof HTMLElement) {
            headersAtScrollTime.push(...header.classList)
          }
        }
        return undefined
      })
    scrollSpy.mockClear()

    await wrapper.find('.bridge-badge').trigger('click')
    await flushPromises()

    // The science target holds only locked topics, so it starts collapsed —
    // the auto-expand path, not the already-expanded one.
    mockGetClusters.mockResolvedValue([
      makeCluster({ id: 'cl2', subject: 'science', domain: 'Units' }),
    ])
    await wrapper.setProps({
      selectedSubject: 'science',
      items: [
        makeItem({
          id: 'p2',
          mastery_level: 'locked',
          topic: makeTopic({ id: 't2', subject: 'science', domain: 'Units' }),
        }),
      ],
    })
    await flushPromises()
    await nextTick()
    await flushPromises()

    const section = wrapper.find('.domain-section[data-domain="Units"]')
    expect(section.exists()).toBe(true)
    expect(
      section.find('.domain-section__header').attributes('aria-expanded'),
    ).toBe('true')
    // The section was at final geometry when the scroll happened: the
    // suppressed-transition class is only present during the scroll itself.
    expect(headersAtScrollTime).toContain('domain-section__header--instant')
    expect(scrollSpy.mock.contexts.length).toBeGreaterThan(0)
    scrollSpy.mockRestore()
  })

  it('never renders a territory card without nodes', async () => {
    // Regression: clusters.json stores 183 rows over only 82 distinct
    // (subject, domain, age_group) tuples, and every row of a colliding key
    // reported the same nonzero topic_count. Filtering on topic_count alone
    // therefore rendered ~100 titled "(0)" cards.
    mockGetClusters.mockResolvedValue([
      // Two rows sharing one match key — the API now collapses these, but
      // the UI must stay safe if a colliding row ever reappears.
      makeCluster({ id: 'cl1', domain: 'Addition', topic_count: 9 }),
      makeCluster({ id: 'cl2', domain: 'Addition', topic_count: 9 }),
      // A cluster this child has no progress in: topic_count is the
      // taxonomy's, not the child's.
      makeCluster({ id: 'cl3', domain: 'Fractions', topic_count: 7 }),
    ])
    const wrapper = mountMap([makeItem({ topic: makeTopic({ id: 't1', domain: 'Addition' }) })])
    await flushPromises()

    const territories = wrapper.findAll('.cluster-territory')
    expect(territories).toHaveLength(1)
    expect(territories[0].attributes('data-cluster-domain')).toBe('Addition')
    // Every rendered territory holds at least one node.
    for (const t of territories) {
      expect(t.findAll('.topic-node').length).toBeGreaterThan(0)
    }
    expect(wrapper.text()).not.toContain('(0)')
  })

  it('falls back to the domain when no cluster matches the age_group', async () => {
    mockGetClusters.mockResolvedValue([
      makeCluster({ id: 'cl1', domain: 'Addition', age_group: 'low', topic_count: 1 }),
    ])
    const wrapper = mountMap([
      makeItem({ topic: makeTopic({ id: 't1', domain: 'Addition', age_group: 'mid' }) }),
    ])
    await flushPromises()

    // Matched on subject+domain, so it belongs to Addition rather than the
    // "other" bucket.
    const territories = wrapper.findAll('.cluster-territory')
    expect(territories).toHaveLength(1)
    expect(territories[0].attributes('data-cluster-domain')).toBe('Addition')
    expect(wrapper.text()).not.toContain('__other__')
  })

  it('labels the synthetic bucket with a translated name, not its raw id', async () => {
    mockGetClusters.mockResolvedValue([])
    const wrapper = mountMap([
      makeItem({ topic: makeTopic({ id: 't1', domain: 'Unclustered Domain' }) }),
    ])
    await flushPromises()

    expect(wrapper.text()).toContain('其他')
    expect(wrapper.text()).not.toContain('__other__')
  })

  it('only matches topics of the selected subject', async () => {
    mockGetClusters.mockResolvedValue([makeCluster({ topic_count: 1 })])
    const wrapper = mountMap(
      [
        makeItem({
          id: 'p1',
          topic: makeTopic({ id: 't1', subject: 'mathematics', name_zh: '数学项' }),
        }),
        makeItem({
          id: 'p2',
          topic: makeTopic({ id: 't2', subject: 'science', name_zh: '科学项' }),
        }),
      ],
      'mathematics',
    )
    await flushPromises()

    expect(wrapper.findAll('.topic-node')).toHaveLength(1)
    expect(wrapper.text()).toContain('数学项')
    expect(wrapper.text()).not.toContain('科学项')
  })

  it('keeps topics in their own domain and sends unknown domains to "other"', async () => {
    mockGetClusters.mockResolvedValue([
      makeCluster({ id: 'cl1', domain: 'Addition', topic_count: 1 }),
      makeCluster({ id: 'cl2', domain: 'Fractions', topic_count: 1 }),
    ])
    const wrapper = mountMap([
      makeItem({ id: 'p1', topic: makeTopic({ id: 't1', domain: 'Addition' }) }),
      makeItem({ id: 'p2', topic: makeTopic({ id: 't2', domain: 'Fractions' }) }),
      // A domain with no cluster must not be attributed to a sibling domain.
      makeItem({ id: 'p3', topic: makeTopic({ id: 't3', domain: 'NoSuchDomain' }) }),
    ])
    await flushPromises()

    const domains = wrapper
      .findAll('.cluster-territory')
      .map((t) => t.attributes('data-cluster-domain'))
    expect(domains).toEqual(['Addition', 'Fractions', '__other__'])
  })

  it('merges the age groups of one domain into a single territory', async () => {
    // clusters.json stores one row per (domain, age_group); the map must still
    // show one card per domain.
    mockGetClusters.mockResolvedValue([
      makeCluster({ id: 'cl1', domain: 'Addition', age_group: 'low' }),
      makeCluster({ id: 'cl2', domain: 'Addition', age_group: 'mid' }),
      makeCluster({ id: 'cl3', domain: 'Fractions', age_group: 'mid' }),
    ])
    const wrapper = mountMap([
      makeItem({ topic: makeTopic({ id: 't1', domain: 'Addition', age_group: 'mid' }) }),
      makeItem({ topic: makeTopic({ id: 't2', domain: 'Addition', age_group: 'low' }) }),
      makeItem({ topic: makeTopic({ id: 't3', domain: 'Fractions', age_group: 'mid' }) }),
    ])
    await flushPromises()

    const territories = wrapper.findAll('.cluster-territory')
    expect(territories.map((t) => t.attributes('data-cluster-domain'))).toEqual([
      'Addition',
      'Fractions',
    ])
    expect(territories[0].findAll('.topic-node')).toHaveLength(2)
  })

  it('matches a null-domain topic by subject instead of dropping it', async () => {
    mockGetClusters.mockResolvedValue([
      makeCluster({ id: 'cl1', domain: 'Addition', age_group: 'mid', topic_count: 2 }),
    ])
    const wrapper = mountMap([
      makeItem({
        id: 'p1',
        topic: makeTopic({ id: 't1', domain: 'Addition', age_group: 'mid' }),
      }),
      makeItem({
        id: 'p2',
        topic: makeTopic({ id: 't2', domain: null, age_group: 'mid' }),
      }),
    ])
    await flushPromises()

    // The null-domain topic joined the Addition card instead of falling into
    // __other__. ClusterTerritory never renders the raw id, so assert on the
    // node count rather than on text that could not appear either way.
    const territories = wrapper.findAll('.cluster-territory')
    expect(territories).toHaveLength(1)
    expect(territories[0].attributes('data-cluster-domain')).toBe('Addition')
    expect(territories[0].findAll('.topic-node')).toHaveLength(2)
  })

  it('routes a null-domain topic to __other__ when the subject has no clusters', async () => {
    // Distinct from the empty-cluster case: a same-subject cluster exists, but
    // the topic carries no domain, so there is nothing to match it against.
    mockGetClusters.mockResolvedValue([
      makeCluster({ id: 'cl1', domain: 'Addition', topic_count: 1 }),
    ])
    const wrapper = mountMap(
      [
        makeItem({
          id: 'p1',
          topic: makeTopic({ id: 't1', subject: 'art', domain: null }),
        }),
      ],
      'art',
    )
    await flushPromises()

    const territories = wrapper.findAll('.cluster-territory')
    expect(territories).toHaveLength(1)
    expect(territories[0].attributes('data-cluster-domain')).toBe('__other__')
  })

  it('does not flash a transient "其他" section during a subject switch', async () => {
    // Use a deferred mock so we can inspect the tree mid-load, before clusters
    // for the new subject have landed.
    let resolveClusters!: (c: ClusterResponse[]) =>
      void
    let resolveBridges!: (b: BridgeResponse[]) => void
    mockGetClusters.mockReturnValue(
      new Promise<ClusterResponse[]>((r) => { resolveClusters = r }),
    )
    mockGetBridges.mockReturnValue(
      new Promise<BridgeResponse[]>((r) => { resolveBridges = r }),
    )
    const wrapper = mountMap([
      makeItem({ id: 'p1', topic: makeTopic({ id: 't1', domain: 'Addition' }) }),
    ])
    await flushPromises()

    // Now switch to science with its own item. Clusters for science are not
    // yet resolved — the "其他" bucket must NOT render in this window.
    await wrapper.setProps({
      selectedSubject: 'science',
      items: [
        makeItem({
          id: 'p2',
          topic: makeTopic({ id: 't2', subject: 'science', domain: 'Units' }),
        }),
      ],
    })
    await nextTick()

    const domains = wrapper
      .findAll('.cluster-territory')
      .map((t) => t.attributes('data-cluster-domain'))
    expect(domains).not.toContain('__other__')
    // And no sections at all until the new clusters land.
    expect(wrapper.find('.domain-section[data-domain="Units"]').exists()).toBe(false)

    // Land the science data; the real sections appear, no stale "其他".
    resolveClusters([makeCluster({ id: 'cl2', subject: 'science', domain: 'Units' })])
    resolveBridges([])
    await flushPromises()
    await nextTick()

    const after = wrapper
      .findAll('.cluster-territory')
      .map((t) => t.attributes('data-cluster-domain'))
    expect(after).toEqual(['Units'])
    expect(wrapper.find('.domain-section[data-domain="__other__"]').exists()).toBe(false)
  })

  // --- Domain grouping and collapse behaviour (U1-U4 / R1-R8) ---

  function headerFor(wrapper: ReturnType<typeof mountMap>, domain: string) {
    return wrapper.find(`.domain-section[data-domain="${domain}"] .domain-section__header`)
  }

  it('renders one section per domain and reports its own mastery progress', async () => {
    // #142 made the territory list one-card-per-domain already, so the
    // section is now a 1:1 wrapper around a card — the two age_group rows of
    // "Addition" collapse into a single card holding both topics.
    mockGetClusters.mockResolvedValue([
      makeCluster({ id: 'cl1', domain: 'Addition', age_group: 'low' }),
      makeCluster({ id: 'cl2', domain: 'Addition', age_group: 'mid' }),
      makeCluster({ id: 'cl3', domain: 'Multiplication' }),
    ])
    const wrapper = mountMap([
      makeItem({ id: 'p1', mastery_level: 'mastered', topic: makeTopic({ id: 't1', domain: 'Addition', age_group: 'low' }) }),
      makeItem({ id: 'p2', mastery_level: 'locked', topic: makeTopic({ id: 't2', domain: 'Addition', age_group: 'mid' }) }),
      makeItem({ id: 'p3', mastery_level: 'available', topic: makeTopic({ id: 't3', domain: 'Multiplication' }) }),
    ])
    await flushPromises()

    const sections = wrapper.findAll('.domain-section')
    expect(sections).toHaveLength(2)

    const addition = wrapper.find('.domain-section[data-domain="Addition"]')
    expect(addition.findAll('.cluster-territory')).toHaveLength(1)
    expect(addition.findAll('.topic-node')).toHaveLength(2)
    expect(addition.find('.domain-section__progress').text()).toBe('1/2 已掌握')
  })

  it('auto-expands a domain with active learning and collapses an all-locked one', async () => {
    mockGetClusters.mockResolvedValue([
      makeCluster({ id: 'cl1', domain: 'Addition' }),
      makeCluster({ id: 'cl2', domain: 'Multiplication' }),
    ])
    const wrapper = mountMap([
      makeItem({ id: 'p1', mastery_level: 'available', topic: makeTopic({ id: 't1', domain: 'Addition' }) }),
      makeItem({ id: 'p2', mastery_level: 'locked', topic: makeTopic({ id: 't2', domain: 'Multiplication' }) }),
    ])
    await flushPromises()

    expect(headerFor(wrapper, 'Addition').attributes('aria-expanded')).toBe('true')
    expect(headerFor(wrapper, 'Multiplication').attributes('aria-expanded')).toBe('false')
  })

  it('auto-expands a domain whose mastered topics are due for review', async () => {
    mockGetClusters.mockResolvedValue([makeCluster({ domain: 'Addition' })])
    const wrapper = mountMap([
      makeItem({
        mastery_level: 'mastered',
        next_review_at: new Date(Date.now() - 86_400_000).toISOString(),
        topic: makeTopic({ domain: 'Addition' }),
      }),
    ])
    await flushPromises()

    expect(headerFor(wrapper, 'Addition').attributes('aria-expanded')).toBe('true')
  })

  it('keeps a manual collapse after switching subject and back (R5 / AE3)', async () => {
    mockGetClusters.mockResolvedValue([makeCluster({ domain: 'Addition' })])
    const wrapper = mountMap([
      makeItem({ id: 'p1', mastery_level: 'available', topic: makeTopic({ id: 't1', domain: 'Addition' }) }),
    ])
    await flushPromises()
    expect(headerFor(wrapper, 'Addition').attributes('aria-expanded')).toBe('true')

    await headerFor(wrapper, 'Addition').trigger('click')
    expect(headerFor(wrapper, 'Addition').attributes('aria-expanded')).toBe('false')

    // away to a subject with its own data, then back
    mockGetClusters.mockResolvedValue([makeCluster({ id: 'cl2', subject: 'science', domain: 'Units' })])
    await wrapper.setProps({ selectedSubject: 'science', items: [] })
    await flushPromises()

    mockGetClusters.mockResolvedValue([makeCluster({ domain: 'Addition' })])
    await wrapper.setProps({
      selectedSubject: 'mathematics',
      items: [makeItem({ id: 'p1', mastery_level: 'available', topic: makeTopic({ id: 't1', domain: 'Addition' }) })],
    })
    await flushPromises()

    expect(headerFor(wrapper, 'Addition').attributes('aria-expanded')).toBe('false')
  })

  it('keeps a manual collapse when a data refresh recomputes the groups', async () => {
    mockGetClusters.mockResolvedValue([makeCluster({ domain: 'Addition' })])
    const wrapper = mountMap([
      makeItem({ id: 'p1', mastery_level: 'available', topic: makeTopic({ id: 't1', domain: 'Addition' }) }),
    ])
    await flushPromises()

    await headerFor(wrapper, 'Addition').trigger('click')
    expect(headerFor(wrapper, 'Addition').attributes('aria-expanded')).toBe('false')

    // a refetch lands with the same active topic
    mockGetClusters.mockResolvedValue([makeCluster({ domain: 'Addition' })])
    await wrapper.setProps({
      items: [makeItem({ id: 'p1b', mastery_level: 'available', topic: makeTopic({ id: 't1', domain: 'Addition' }) })],
    })
    await flushPromises()

    expect(headerFor(wrapper, 'Addition').attributes('aria-expanded')).toBe('false')
  })

  it('toggles a collapsed domain open on header tap', async () => {
    mockGetClusters.mockResolvedValue([makeCluster({ domain: 'Multiplication' })])
    const wrapper = mountMap([
      makeItem({ mastery_level: 'locked', topic: makeTopic({ domain: 'Multiplication' }) }),
    ])
    await flushPromises()
    expect(headerFor(wrapper, 'Multiplication').attributes('aria-expanded')).toBe('false')

    await headerFor(wrapper, 'Multiplication').trigger('click')
    expect(headerFor(wrapper, 'Multiplication').attributes('aria-expanded')).toBe('true')
  })
})
