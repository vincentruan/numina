import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import type { ProgressWithTopic, TopicResponse, ClusterResponse, BridgeResponse } from '@/api/learning'
import zhCN from '@/i18n/locales/zh-CN'
import enUS from '@/i18n/locales/en-US'
import ClusterTerritory from './ClusterTerritory.vue'

function makeTopic(overrides: Partial<TopicResponse> = {}): TopicResponse {
  return {
    id: 't1',
    topic_key: 'math.add.01',
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

function makeBridge(overrides: Partial<BridgeResponse> = {}): BridgeResponse {
  return {
    from_cluster_domain: 'Addition',
    from_subject: 'mathematics',
    to_cluster_domain: 'Units',
    to_subject: 'science',
    edge_count: 1,
    ...overrides,
  }
}

function mountTerritory(
  cluster: ClusterResponse,
  items: ProgressWithTopic[] = [],
  bridges: BridgeResponse[] = [],
  extra: {
    isFrontierCluster?: boolean
    frontierTopicId?: string | null
    hideTitle?: boolean
  } = {},
) {
  const i18n = createI18n({
    legacy: false,
    locale: 'zh-CN',
    messages: { 'zh-CN': zhCN, 'en-US': enUS },
  })
  return mount(ClusterTerritory, {
    props: {
      cluster,
      items,
      bridges,
      isFrontierCluster: extra.isFrontierCluster ?? false,
      frontierTopicId: extra.frontierTopicId ?? null,
      hideTitle: extra.hideTitle ?? false,
    },
    global: { plugins: [i18n] },
  })
}

describe('ClusterTerritory', () => {
  it('renders the domain label and item count', () => {
    const wrapper = mountTerritory(
      makeCluster({ domain: 'Addition' }),
      [makeItem(), makeItem({ id: 'p2', topic_id: 't2' })],
    )

    expect(wrapper.find('.cluster-territory__title').text()).toContain('Addition')
    expect(wrapper.find('.cluster-territory__count').text()).toBe('(2)')
  })

  it('suppresses the domain title when an enclosing section shows it', () => {
    // ClusterMap wraps every card in a DomainSection header carrying the same
    // domain name, so the card must not repeat it.
    const wrapper = mountTerritory(makeCluster({ domain: 'Addition' }), [makeItem()], [], {
      hideTitle: true,
    })

    expect(wrapper.find('.cluster-territory__title').exists()).toBe(false)
  })

  it('keeps the frontier badge when the title is hidden', () => {
    // The badge is the card's own signal — suppressing the title must not
    // strip it along with the header row.
    const wrapper = mountTerritory(makeCluster(), [], [], {
      hideTitle: true,
      isFrontierCluster: true,
    })

    expect(wrapper.find('.cluster-territory__title').exists()).toBe(false)
    expect(wrapper.find('.cluster-territory__frontier-badge').exists()).toBe(true)
  })

  it('renders one TopicNode per item', () => {
    const wrapper = mountTerritory(
      makeCluster(),
      [
        makeItem({ id: 'p1', topic: makeTopic({ id: 't1' }) }),
        makeItem({ id: 'p2', topic: makeTopic({ id: 't2' }) }),
      ],
    )

    expect(wrapper.findAll('.topic-node-wrapper')).toHaveLength(2)
  })

  it('shows frontier class when isFrontierCluster is true', () => {
    const wrapper = mountTerritory(makeCluster(), [], [], { isFrontierCluster: true })
    expect(wrapper.find('.cluster-territory').classes()).toContain('cluster-territory--frontier')
    expect(wrapper.find('.cluster-territory__frontier-badge').exists()).toBe(true)
  })

  it('hides frontier badge when not a frontier cluster', () => {
    const wrapper = mountTerritory(makeCluster(), [], [], { isFrontierCluster: false })
    expect(wrapper.find('.cluster-territory--frontier').exists()).toBe(false)
    expect(wrapper.find('.cluster-territory__frontier-badge').exists()).toBe(false)
  })

  it('marks the frontier topic with is-frontier prop', () => {
    const items = [
      makeItem({ id: 'p1', topic: makeTopic({ id: 't1' }) }),
      makeItem({ id: 'p2', topic: makeTopic({ id: 't2' }) }),
    ]
    const wrapper = mountTerritory(makeCluster(), items, [], {
      isFrontierCluster: true,
      frontierTopicId: 't2',
    })

    // The second TopicNode should receive isFrontier=true
    const nodes = wrapper.findAllComponents({ name: 'TopicNode' })
    expect(nodes[0].props('isFrontier')).toBe(false)
    expect(nodes[1].props('isFrontier')).toBe(true)
  })

  it('shows cluster summary when present', () => {
    const wrapper = mountTerritory(
      makeCluster({ summary: 'Learn basic addition' }),
    )

    expect(wrapper.find('.cluster-territory__summary').text()).toBe('Learn basic addition')
  })

  it('hides summary when empty', () => {
    const wrapper = mountTerritory(makeCluster({ summary: '' }))
    expect(wrapper.find('.cluster-territory__summary').exists()).toBe(false)
  })

  it('renders bridge badges up to 2, with overflow count', () => {
    const bridges = [
      makeBridge({ to_subject: 'science', to_cluster_domain: 'Units' }),
      makeBridge({ to_subject: 'english', to_cluster_domain: 'Grammar' }),
      makeBridge({ to_subject: 'chinese', to_cluster_domain: 'Poetry' }),
    ]
    const wrapper = mountTerritory(makeCluster(), [], bridges)

    const badges = wrapper.findAll('.bridge-badge')
    expect(badges).toHaveLength(2) // capped at 2
    expect(wrapper.find('.bridge-badge__overflow').text()).toBe('+1')
  })

  it('renders all bridge badges when 2 or fewer', () => {
    const bridges = [
      makeBridge({ to_subject: 'science', to_cluster_domain: 'Units' }),
    ]
    const wrapper = mountTerritory(makeCluster(), [], bridges)

    expect(wrapper.findAll('.bridge-badge')).toHaveLength(1)
    expect(wrapper.find('.bridge-badge__overflow').exists()).toBe(false)
  })

  it('emits bridgeTap when a bridge badge is clicked', async () => {
    const bridge = makeBridge({ to_subject: 'science', to_cluster_domain: 'Units' })
    const wrapper = mountTerritory(makeCluster(), [], [bridge])

    await wrapper.find('.bridge-badge').trigger('click')
    expect(wrapper.emitted('bridgeTap')).toBeTruthy()
    expect(wrapper.emitted('bridgeTap')![0]).toEqual([bridge])
  })

  it('emits topicTap when a TopicNode is tapped', async () => {
    const item = makeItem()
    const wrapper = mountTerritory(makeCluster(), [item])

    await wrapper.find('.topic-node-wrapper').trigger('click')
    expect(wrapper.emitted('topicTap')).toBeTruthy()
    expect(wrapper.emitted('topicTap')![0]).toEqual([item])
  })

  it('labels __other__ domain with translated name', () => {
    const wrapper = mountTerritory(
      makeCluster({ domain: '__other__' }),
      [makeItem()],
    )

    expect(wrapper.text()).toContain('其他')
    expect(wrapper.text()).not.toContain('__other__')
  })

  it('sets data-cluster-domain attribute', () => {
    const wrapper = mountTerritory(makeCluster({ domain: 'Fractions' }))
    expect(wrapper.find('.cluster-territory').attributes('data-cluster-domain')).toBe('Fractions')
  })
})
