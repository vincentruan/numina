import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { createI18n } from 'vue-i18n'
import KnowledgeOcean from './KnowledgeOcean.vue'
import type { OceanSubject, OceanDomain, OceanTopic, OceanDependencyEdge } from './KnowledgeOcean.vue'
import { getContinentTheme } from '@/data/continentThemes'

// --- Mocks ---

vi.mock('@/api/learning', () => ({
  getTopicIndex: vi.fn(),
  getSubjectDependencies: vi.fn(),
}))



// --- i18n ---

const i18n = createI18n({
  legacy: false,
  locale: 'en',
  messages: {
    en: {
      learning: {
        subject: {
          mathematics: 'Mathematics',
          science: 'Science',
          chinese: 'Chinese',
        },
        ocean: {
          backToOcean: 'Back to ocean',
          backToSubject: 'Back to {subject}',
          zoomHint: 'Pinch or double-tap to explore',
          topics: '{count} topics',
          domains: '{count} regions',
          exploreSubject: 'Explore {subject}',
          previewTitle: '{subject}',
          previewMastered: '{mastered}/{total} mastered',
          previewExplore: 'Explore this land',
        },
      },
    },
  },
})

// --- Fixtures ---

function makeSubject(id: string, overrides: Partial<OceanSubject> = {}): OceanSubject {
  return {
    id,
    terrain: getContinentTheme(id).terrain,
    displayName: id,
    icon: getContinentTheme(id).icon,
    topicCount: 10,
    masteryRatio: 0,
    ...overrides,
  }
}

function makeDomain(subject: string, domain: string, overrides: Partial<OceanDomain> = {}): OceanDomain {
  return {
    id: `${subject}:${domain}`,
    subject,
    domain,
    displayName: domain,
    topicCount: 5,
    masteryRatio: 0,
    ...overrides,
  }
}

function makeTopic(id: string, subject: string, domain: string, overrides: Partial<OceanTopic> = {}): OceanTopic {
  return {
    id,
    subject,
    domain,
    displayName: id,
    masteryLevel: 'available',
    ...overrides,
  }
}

function baseProps() {
  return {
    subjects: [
      makeSubject('mathematics', { topicCount: 12, masteryRatio: 0.9 }),
      makeSubject('science', { topicCount: 8, masteryRatio: 0 }),
      makeSubject('chinese', { topicCount: 9, masteryRatio: 0.3 }),
    ],
    domains: [
      makeDomain('mathematics', 'Addition'),
      makeDomain('mathematics', 'Subtraction'),
      makeDomain('science', 'Forces'),
      makeDomain('chinese', 'Literacy'),
    ],
    topics: [
      makeTopic('t-math-1', 'mathematics', 'Addition', { masteryLevel: 'mastered' }),
      makeTopic('t-math-2', 'mathematics', 'Addition'),
      makeTopic('t-math-3', 'mathematics', 'Subtraction'),
      makeTopic('t-sci-1', 'science', 'Forces'),
      makeTopic('t-ch-1', 'chinese', 'Literacy'),
    ],
    edges: [] as OceanDependencyEdge[],
    selectedSubject: '',
    selectedDomain: '',
  }
}

function mountOcean(props = baseProps()) {
  return mount(KnowledgeOcean, {
    props,
    global: { plugins: [i18n] },
    attachTo: document.body,
  })
}

// --- Helpers ---

function fireTouchEvent(
  el: Element,
  type: 'touchstart' | 'touchmove' | 'touchend',
  touchPoints: Array<{ id: number; x: number; y: number }>,
) {
  const touches = touchPoints.map(
    (p) => new Touch({ identifier: p.id, target: el, clientX: p.x, clientY: p.y }),
  )
  el.dispatchEvent(new TouchEvent(type, { touches, cancelable: true, bubbles: true }))
}

describe('KnowledgeOcean — subject level (R1, R2, R3, R5, R7)', () => {
  it('renders every subject as an island (R2)', () => {
    const wrapper = mountOcean()
    const islands = wrapper.findAll('.ocean-island')
    expect(islands).toHaveLength(3)
  })

  it('renders a sea element behind the islands', () => {
    const wrapper = mountOcean()
    expect(wrapper.find('.ocean-sea').exists()).toBe(true)
  })

  it('renders island labels above the fog (R7 — labels legible at every ratio)', () => {
    const wrapper = mountOcean()
    const labels = wrapper.findAll('.ocean-island__label')
    expect(labels).toHaveLength(3)
    // Label renders even for a 0%-mastery island
    const sci = wrapper.findAll('.ocean-island').find((w) => w.attributes('data-island-id') === 'science')!
    expect(sci.find('.ocean-island__label').exists()).toBe(true)
  })

  it('renders island silhouettes (landmass paths) regardless of mastery (R7)', () => {
    const wrapper = mountOcean()
    const silhouettes = wrapper.findAll('.ocean-island__land')
    expect(silhouettes).toHaveLength(3)
  })

  it('applies fog opacity from mastery ratio (R5)', async () => {
    const wrapper = mountOcean()
    const fogs = wrapper.findAll('.ocean-island__fog')
    expect(fogs).toHaveLength(3)
    // mathematics at 0.9 → 0; science at 0 → 0.7; chinese at 0.3 → 0.4
    const opacities = fogs.map((f) => f.attributes('style'))
    expect(opacities.some((s) => s?.includes('opacity: 0.7'))).toBe(true)
    expect(opacities.some((s) => s?.includes('opacity: 0.4'))).toBe(true)
  })

  it('gives islands organic (non-grid) positions (R3)', () => {
    const wrapper = mountOcean()
    const groups = wrapper.findAll('.ocean-island')
    const xs = new Set<string>()
    const ys = new Set<string>()
    for (const g of groups) {
      const transform = g.attributes('transform') ?? ''
      const m = transform.match(/translate\(([\d.]+),\s*([\d.]+)\)/)
      expect(m).not.toBeNull()
      xs.add(m![1])
      ys.add(m![2])
    }
    expect(xs.size).toBe(3) // all x different
    expect(ys.size).toBe(3) // all y different
  })

  it('island positions are stable across re-renders (F3 — layout never moves)', async () => {
    const wrapper = mountOcean()
    const before = wrapper.findAll('.ocean-island').map((g) => g.attributes('transform'))
    await wrapper.setProps({
      subjects: baseProps().subjects.map((s) =>
        s.id === 'science' ? { ...s, masteryRatio: 0.6 } : s,
      ),
    })
    const after = wrapper.findAll('.ocean-island').map((g) => g.attributes('transform'))
    expect(after).toEqual(before)
  })
})

describe('KnowledgeOcean — fog tap yields preview, never refusal (R6, AE2)', () => {
  it('emits a preview event when a fogged (0% mastery) island is tapped', async () => {
    const wrapper = mountOcean()
    const sci = wrapper
      .findAll('.ocean-island')
      .find((w) => w.attributes('data-island-id') === 'science')!
    await sci.trigger('click')
    const emitted = wrapper.emitted('previewSubject')
    expect(emitted).toBeTruthy()
    expect(emitted![0]).toEqual(['science'])
  })

  it('tap on island with topicCount 0 also yields a preview (never disabled/locked)', async () => {
    const props = baseProps()
    props.subjects = props.subjects.map((s) =>
      s.id === 'science' ? { ...s, topicCount: 0 } : s,
    )
    const wrapper = mountOcean(props)
    const sci = wrapper
      .findAll('.ocean-island')
      .find((w) => w.attributes('data-island-id') === 'science')!
    expect(sci.attributes('disabled')).toBeUndefined()
    await sci.trigger('click')
    expect(wrapper.emitted('previewSubject')).toBeTruthy()
  })
})

describe('KnowledgeOcean — three zoom levels (R4, R8)', () => {
  it('starts at subject level showing islands', () => {
    const wrapper = mountOcean()
    expect(wrapper.findAll('.ocean-island').length).toBe(3)
    expect(wrapper.find('.topic-constellation').exists()).toBe(false)
  })

  it('double-tap on an island descends to that subject (R8)', async () => {
    const wrapper = mountOcean()
    const math = wrapper
      .findAll('.ocean-island')
      .find((w) => w.attributes('data-island-id') === 'mathematics')!
    // First tap → preview
    await math.trigger('click')
    expect(wrapper.emitted('previewSubject')).toBeTruthy()
    // Double-tap → zoom in (second tap within the window)
    await math.trigger('click')
    await math.trigger('click')
    // The component emits selectSubject after a true double tap
    const selects = wrapper.emitted('selectSubject')
    expect(selects).toBeTruthy()
    expect(selects![0]).toEqual(['mathematics'])
  })

  it('pinch-in on an island descends to it (R8)', async () => {
    const wrapper = mountOcean()
    const math = wrapper
      .findAll('.ocean-island')
      .find((w) => w.attributes('data-island-id') === 'mathematics')!
    const rect = math.element as SVGElement
    // Two-finger pinch-in on the island
    fireTouchEvent(rect, 'touchstart', [
      { id: 1, x: 100, y: 100 },
      { id: 2, x: 160, y: 100 },
    ])
    fireTouchEvent(rect, 'touchmove', [
      { id: 1, x: 120, y: 100 },
      { id: 2, x: 140, y: 100 },
    ])
    fireTouchEvent(rect, 'touchend', [])
    await nextTick()
    const selects = wrapper.emitted('selectSubject')
    expect(selects).toBeTruthy()
    expect(selects![0]).toEqual(['mathematics'])
  })

  it('zoom-out gesture at domain level returns to subject level (R8)', async () => {
    const wrapper = mountOcean()
    // Enter subject level 2 via props
    await wrapper.setProps({ selectedSubject: 'mathematics' })
    // Pinch out
    const svg = wrapper.find('.knowledge-ocean')
    fireTouchEvent(svg.element, 'touchstart', [
      { id: 1, x: 100, y: 100 },
      { id: 2, x: 120, y: 100 },
    ])
    fireTouchEvent(svg.element, 'touchmove', [
      { id: 1, x: 80, y: 100 },
      { id: 2, x: 140, y: 100 },
    ])
    fireTouchEvent(svg.element, 'touchend', [])
    await nextTick()
    const zoomOut = wrapper.emitted('zoomOut')
    expect(zoomOut).toBeTruthy()
  })
})

describe('KnowledgeOcean — domain level (R4)', () => {
  it('shows the selected subject\'s domains as regions', async () => {
    const wrapper = mountOcean()
    await wrapper.setProps({ selectedSubject: 'mathematics' })
    const regions = wrapper.findAll('.ocean-region')
    expect(regions).toHaveLength(2) // Addition, Subtraction
  })

  it('region tap emits previewDomain (R6 — preview, never refusal)', async () => {
    const wrapper = mountOcean()
    await wrapper.setProps({ selectedSubject: 'mathematics' })
    const region = wrapper.findAll('.ocean-region')[0]
    await region.trigger('click')
    expect(wrapper.emitted('previewDomain')).toBeTruthy()
  })

  it('double-tap on a region descends to topic level (R8)', async () => {
    const wrapper = mountOcean()
    await wrapper.setProps({ selectedSubject: 'mathematics' })
    const region = wrapper.findAll('.ocean-region')[0]
    await region.trigger('click')
    await region.trigger('click')
    const selects = wrapper.emitted('selectDomain')
    expect(selects).toBeTruthy()
    expect(selects![0]).toEqual([expect.objectContaining({ subject: 'mathematics' })])
  })
})

describe('KnowledgeOcean — topic level constellation (R9, R10, AE3)', () => {
  it('renders topics as nodes with prerequisite edges as lines, on arrival', async () => {
    const props = baseProps()
    props.edges = [
      { topic_id: 't-math-1', prerequisite_id: 't-math-2', strength: null },
    ]
    const wrapper = mountOcean(props)
    await wrapper.setProps({ selectedSubject: 'mathematics', selectedDomain: 'Addition' })
    expect(wrapper.find('.topic-constellation').exists()).toBe(true)
    // Both topics of the Addition domain render as nodes
    const nodes = wrapper.findAll('.topic-constellation__node')
    expect(nodes).toHaveLength(2)
    // The prerequisite edge renders as a line
    const lines = wrapper.findAll('.topic-constellation__edge')
    expect(lines).toHaveLength(1)
  })

  it('isolated topics (no edges) still render as unconnected points (R10, AE3)', async () => {
    const wrapper = mountOcean()
    await wrapper.setProps({ selectedSubject: 'science', selectedDomain: 'Forces' })
    const nodes = wrapper.findAll('.topic-constellation__node')
    expect(nodes).toHaveLength(1)
    expect(wrapper.findAll('.topic-constellation__edge')).toHaveLength(0)
    expect(nodes[0].classes()).toContain('topic-constellation__node--isolated')
  })

  it('topic node tap emits selectTopic', async () => {
    const wrapper = mountOcean()
    await wrapper.setProps({ selectedSubject: 'mathematics', selectedDomain: 'Addition' })
    const node = wrapper.findAll('.topic-constellation__node')[0]
    await node.trigger('click')
    const emitted = wrapper.emitted('selectTopic')
    expect(emitted).toBeTruthy()
    expect(emitted![0]).toEqual([expect.objectContaining({ id: expect.any(String) })])
  })
})

describe('KnowledgeOcean — analytics events (R11, R12)', () => {
  it('emits interaction events for zoom gestures', async () => {
    const wrapper = mountOcean()
    const math = wrapper
      .findAll('.ocean-island')
      .find((w) => w.attributes('data-island-id') === 'mathematics')!
    await math.trigger('click')
    await math.trigger('click')
    // zoomed events reported via emits (page layer wires them to useMapExploration)
    expect(wrapper.emitted('zoomed')).toBeTruthy()
    expect(wrapper.emitted('zoomed')![0]).toEqual([1])
  })

  it('emits interaction events for island taps', async () => {
    const wrapper = mountOcean()
    const math = wrapper
      .findAll('.ocean-island')
      .find((w) => w.attributes('data-island-id') === 'mathematics')!
    await math.trigger('click')
    expect(wrapper.emitted('interacted')).toBeTruthy()
  })
})
