import { describe, it, expect } from 'vitest'
import { layoutConstellation, type TopicEdge } from './constellationLayout'

const TOPICS = ['t1', 't2', 't3', 't4', 't5']
const EDGES: TopicEdge[] = [
  { from: 't1', to: 't2' },
  { from: 't2', to: 't3' },
  { from: 't1', to: 't4' },
]

describe('layoutConstellation (R9, R10)', () => {
  it('places all topics as nodes', () => {
    const layout = layoutConstellation(TOPICS, EDGES)
    expect(layout.nodes).toHaveLength(TOPICS.length)
    const ids = layout.nodes.map((n) => n.id)
    for (const t of TOPICS) expect(ids).toContain(t)
  })

  it('renders all valid edges', () => {
    const layout = layoutConstellation(TOPICS, EDGES)
    expect(layout.edges).toHaveLength(EDGES.length)
    for (const e of layout.edges) {
      const fromNode = layout.nodes.find((n) => n.id === e.from)
      const toNode = layout.nodes.find((n) => n.id === e.to)
      expect(fromNode).toBeDefined()
      expect(toNode).toBeDefined()
    }
  })

  it('marks isolated nodes (no edges) as unconnected', () => {
    const topics = ['t1', 't2', 'isolated']
    const edges: TopicEdge[] = [{ from: 't1', to: 't2' }]
    const layout = layoutConstellation(topics, edges)
    const isolated = layout.nodes.find((n) => n.id === 'isolated')!
    expect(isolated.connected).toBe(false)
    const connected = layout.nodes.find((n) => n.id === 't1')!
    expect(connected.connected).toBe(true)
  })

  it('is deterministic', () => {
    const a = layoutConstellation(TOPICS, EDGES)
    const b = layoutConstellation(TOPICS, EDGES)
    expect(a.nodes).toEqual(b.nodes)
    expect(a.edges).toEqual(b.edges)
  })

  it('keeps all positions within [0, 1] bounds', () => {
    const layout = layoutConstellation(TOPICS, EDGES)
    for (const n of layout.nodes) {
      expect(n.x).toBeGreaterThanOrEqual(0)
      expect(n.x).toBeLessThanOrEqual(1)
      expect(n.y).toBeGreaterThanOrEqual(0)
      expect(n.y).toBeLessThanOrEqual(1)
    }
  })

  it('handles topics with no edges (all isolated)', () => {
    const layout = layoutConstellation(['a', 'b', 'c'], [])
    expect(layout.nodes).toHaveLength(3)
    expect(layout.edges).toHaveLength(0)
    for (const n of layout.nodes) expect(n.connected).toBe(false)
  })

  it('handles empty topic list', () => {
    const layout = layoutConstellation([], [])
    expect(layout.nodes).toHaveLength(0)
    expect(layout.edges).toHaveLength(0)
  })

  it('ignores edges with endpoints outside the topic set', () => {
    const layout = layoutConstellation(['t1', 't2'], [
      { from: 't1', to: 't2' },
      { from: 't1', to: 'external' },
    ])
    expect(layout.edges).toHaveLength(1)
    expect(layout.edges[0].from).toBe('t1')
    expect(layout.edges[0].to).toBe('t2')
  })
})
